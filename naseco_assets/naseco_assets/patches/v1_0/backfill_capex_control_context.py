from __future__ import annotations

from typing import Any

import frappe

from naseco_assets.naseco_assets.utils import (
	get_cost_center_company,
	get_current_fiscal_year,
	get_employee_company,
)


def _default_company(cost_center: str | None = None, employee: str | None = None) -> str | None:
	return (
		get_cost_center_company(cost_center)
		or get_employee_company(employee)
		or frappe.defaults.get_user_default("Company")
	)


def _set_values(doctype: str, name: str, values: dict[str, Any]) -> None:
	if values:
		frappe.db.set_value(doctype, name, values, update_modified=False)


def _select_fields(doctype: str, *fieldnames: str) -> list[str]:
	return [fieldname for fieldname in fieldnames if fieldname == "name" or frappe.db.has_column(doctype, fieldname)]


def execute() -> None:
	for plan in frappe.get_all(
		"Fixed Asset CAPEX Plan",
		fields=["name", "company", "cost_center", "fiscal_year"],
	):
		updates: dict[str, Any] = {}
		company = plan.company or _default_company(plan.cost_center)
		if company and company != plan.company:
			updates["company"] = company
		fiscal_year = plan.fiscal_year or get_current_fiscal_year(company)
		if fiscal_year and fiscal_year != plan.fiscal_year:
			updates["fiscal_year"] = fiscal_year
		_set_values("Fixed Asset CAPEX Plan", plan.name, updates)

	for request in frappe.get_all(
		"Fixed Asset Request",
		fields=["name", "company", "fiscal_year", "cost_center", "requesting_employee"],
	):
		updates: dict[str, Any] = {}
		company = request.company or _default_company(request.cost_center, request.requesting_employee)
		if company and company != request.company:
			updates["company"] = company
		fiscal_year = request.fiscal_year or get_current_fiscal_year(company)
		if fiscal_year and fiscal_year != request.fiscal_year:
			updates["fiscal_year"] = fiscal_year
		_set_values("Fixed Asset Request", request.name, updates)

	for doctype in ["Material Request", "Purchase Order", "Purchase Receipt", "Purchase Invoice", "Asset"]:
		fields = _select_fields(doctype, "name", "asset_request", "capex_plan", "company", "cost_center")
		field_set = set(fields)
		rows = frappe.get_all(
			doctype,
			fields=fields,
		)
		for row in rows:
			if not row.get("asset_request"):
				continue

			request = frappe.db.get_value(
				"Fixed Asset Request",
				row.get("asset_request"),
				["name", "company", "cost_center", "capex_plan"],
				as_dict=True,
			)
			if not request:
				continue

			updates: dict[str, Any] = {}
			if "company" in field_set and request.get("company") and not row.get("company"):
				updates["company"] = request.company
			if "cost_center" in field_set and request.get("cost_center") and not row.get("cost_center"):
				updates["cost_center"] = request.cost_center
			if "capex_plan" in field_set and request.get("capex_plan") and not row.get("capex_plan"):
				updates["capex_plan"] = request.capex_plan
			_set_values(doctype, row.get("name"), updates)
