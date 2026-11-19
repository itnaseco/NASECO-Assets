from __future__ import annotations

from collections.abc import Callable
from typing import Any
from html import escape as escape_html

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from .constants import (
	ROLE_ASSET_ADMINISTRATOR,
	ROLE_EXECUTIVE_VIEWER,
	ROLE_FINANCE_MANAGER,
	ROLE_INTERNAL_AUDITOR,
)
from .utils import days_until, send_role_mail
from .insurance import sync_assets_for_insurance_policy


def _format_rows(rows: list[dict[str, Any]], title: str) -> str:
	if not rows:
		return ""
	items = "".join(
		f"<li><strong>{escape_html(str(row.get('name') or row.get('asset') or row.get('policy_number') or ''))}</strong>"
		f"{' — ' + escape_html(str(row.get('days_remaining'))) if row.get('days_remaining') is not None else ''}</li>"
		for row in rows
	)
	return f"<p><strong>{escape_html(title)}</strong></p><ul>{items}</ul>"


def _send(subject: str, message: str, roles: list[str] | None = None) -> None:
	send_role_mail(roles or [ROLE_FINANCE_MANAGER, ROLE_ASSET_ADMINISTRATOR, ROLE_INTERNAL_AUDITOR], subject, message)


def send_insurance_expiry_notifications() -> None:
	refresh_insurance_policy_statuses()
	for threshold in (90, 60, 30, 14, 7):
		rows = frappe.get_all(
			"Asset Insurance Policy",
			filters={
				"docstatus": 1,
				"status": ["in", ["Active", "Expiring Soon"]],
			},
			fields=["name", "policy_number", "coverage_end_date"],
		)
		due = [
			{
				"name": row.name,
				"days_remaining": days_until(row.coverage_end_date),
				"policy_number": row.policy_number,
			}
			for row in rows
			if days_until(row.coverage_end_date) == threshold
		]
		if due:
			_send(
				_(f"Insurance expiring in {threshold} days"),
				_format_rows(due, f"Insurance policies expiring in {threshold} days"),
			)


def refresh_insurance_policy_statuses() -> None:
	policies = frappe.get_all(
		"Asset Insurance Policy",
		filters={"docstatus": 1},
		fields=["name", "coverage_start_date", "coverage_end_date", "status"],
	)
	today_date = getdate(nowdate())
	for policy in policies:
		if not policy.coverage_end_date:
			continue
		days_remaining = (getdate(policy.coverage_end_date) - today_date).days
		status = "Scheduled" if policy.coverage_start_date and getdate(policy.coverage_start_date) > today_date else "Expired" if days_remaining < 0 else "Expiring Soon" if days_remaining <= 30 else "Active"
		if policy.status != status:
			frappe.db.set_value("Asset Insurance Policy", policy.name, "status", status, update_modified=False)
			sync_assets_for_insurance_policy(policy.name)


def send_warranty_expiry_notifications() -> None:
	rows = frappe.get_all(
		"Asset",
		filters={"docstatus": ["<", 2]},
		fields=["name", "warranty_expiry_date", "asset_name"],
	)
	for threshold in (60, 30):
		due = [
			{"name": row.name, "days_remaining": days_until(row.warranty_expiry_date)}
			for row in rows
			if days_until(row.warranty_expiry_date) == threshold
		]
		if due:
			_send(_(f"Warranty expiring in {threshold} days"), _format_rows(due, f"Assets with warranty expiring in {threshold} days"))


def send_maintenance_due_notifications() -> None:
	rows = frappe.get_all(
		"Asset Maintenance Plan",
		filters={"docstatus": ["<", 2], "status": "Active"},
		fields=["name", "asset", "next_due_date"],
	)
	due = []
	for row in rows:
		remaining = days_until(row.next_due_date)
		if remaining is not None and remaining <= 7:
			due.append({"name": row.name, "days_remaining": remaining})
	if due:
		_send(_("Maintenance due or overdue"), _format_rows(due, "Maintenance plans due within 7 days or overdue"))


def send_uncapitalized_asset_notifications() -> None:
	rows = frappe.get_all(
		"Asset",
		filters={
			"docstatus": ["<", 2],
			"purchase_invoice": ["!=", ""],
		},
		fields=["name", "asset_name", "purchase_invoice", "capitalization_status"],
	)
	due = [row for row in rows if row.capitalization_status not in {"Capitalized"}]
	if due:
		_send(
			_("Assets received but not capitalized"),
			_format_rows(due, "Assets with purchase invoices but not yet capitalized"),
			roles=[ROLE_ASSET_ADMINISTRATOR],
		)


def send_assets_without_custodian_notifications() -> None:
	rows = frappe.get_all(
		"Asset",
		filters={"docstatus": ["<", 2], "status": ["in", ["Capitalized", "Work In Progress"]]},
		fields=["name", "asset_name", "current_custodian"],
	)
	due = [row for row in rows if not row.current_custodian]
	if due:
		_send(_("Assets without custodians"), _format_rows(due, "Active assets without a current custodian"))


def send_capex_over_budget_notifications() -> None:
	rows = frappe.get_all(
		"Fixed Asset CAPEX Plan",
		filters={"docstatus": ["<", 2]},
		fields=["name", "approved_budget", "remaining_budget"],
	)
	due = [row for row in rows if flt(row.remaining_budget) < 0]
	if due:
		_send(_("CAPEX plans over budget"), _format_rows(due, "CAPEX plans with negative remaining budget"))


def run_daily_asset_alerts() -> None:
	jobs: list[Callable[[], None]] = [
		send_insurance_expiry_notifications,
		send_warranty_expiry_notifications,
		send_maintenance_due_notifications,
		send_uncapitalized_asset_notifications,
		send_assets_without_custodian_notifications,
		send_capex_over_budget_notifications,
	]
	for job in jobs:
		try:
			job()
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"NASECO Assets alert job failed: {job.__name__}")
