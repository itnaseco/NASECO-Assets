from __future__ import annotations

from typing import Any

import frappe
from frappe.model.document import Document
from erpnext.accounts.utils import get_fiscal_year
from frappe.utils import add_days, flt, getdate, nowdate

from .constants import DEFAULT_LOCATION_NAME


def has_role(role: str, user: str | None = None) -> bool:
	try:
		return role in frappe.get_roles(user)
	except Exception:
		return False


def user_has_finance_override() -> bool:
	return has_role("Finance Manager") or has_role("System Manager")


def today() -> str:
	return nowdate()


def as_float(value: Any) -> float:
	return flt(value or 0)


def as_date(value: Any):
	if not value:
		return None
	return getdate(value)


def safe_set(doc: Document, fieldname: str, value: Any) -> None:
	if value is not None and doc.get(fieldname) != value:
		doc.set(fieldname, value)


def get_default_location_name() -> str:
	name = frappe.db.get_value("Location", {"location_name": DEFAULT_LOCATION_NAME}, "name")
	if name:
		return name

	location = frappe.get_doc(
		{
			"doctype": "Location",
			"location_name": DEFAULT_LOCATION_NAME,
			"is_group": 0,
			"is_container": 0,
		}
	)
	location.insert(ignore_permissions=True)
	return location.name


def get_users_with_role(role: str) -> list[str]:
	return [
		row.parent
		for row in frappe.get_all(
			"Has Role",
			filters={"role": role},
			fields=["parent"],
			distinct=True,
		)
	]


def send_role_mail(roles: list[str], subject: str, message: str) -> None:
	recipients: set[str] = set()
	for role in roles:
		recipients.update(get_users_with_role(role))

	if not recipients:
		return

	frappe.sendmail(recipients=sorted(recipients), subject=subject, message=message)


def get_fixed_asset_item(asset_category: str, company: str | None = None) -> str | None:
	filters: dict[str, Any] = {"is_fixed_asset": 1, "asset_category": asset_category}
	if company and frappe.db.has_column("Item", "company"):
		filters["company"] = company
		item_name = frappe.db.get_value("Item", filters, "name")
		if item_name:
			return item_name

	item_names = frappe.get_all("Item", filters=filters, pluck="name", order_by="modified desc")
	if not item_names:
		return None

	if company and frappe.db.table_exists("Item Default"):
		matching_items = set(
			frappe.get_all(
				"Item Default",
				filters={"parent": ["in", item_names], "company": company},
				pluck="parent",
				distinct=True,
			)
		)
		for item_name in item_names:
			if item_name in matching_items:
				return item_name

	return item_names[0]


def get_employee_department(employee: str | None) -> str | None:
	if not employee:
		return None
	return frappe.db.get_value("Employee", employee, "department")


def get_employee_company(employee: str | None) -> str | None:
	if not employee:
		return None
	return frappe.db.get_value("Employee", employee, "company")


def get_asset_category_defaults(asset_category: str | None) -> dict[str, Any]:
	if not asset_category:
		return {}

	defaults = frappe.db.get_value(
		"Asset Category",
		asset_category,
		[
			"naseco_asset_business_class",
			"naseco_non_depreciable",
			"naseco_default_useful_life_years",
			"naseco_default_depreciation_method",
			"naseco_default_residual_value",
			"naseco_usage_based_reporting",
		],
		as_dict=True,
	)
	return defaults or {}


def calculate_remaining_budget(approved_budget: float, committed_amount: float, actual_spent: float) -> float:
	return as_float(approved_budget) - as_float(committed_amount) - as_float(actual_spent)


def calculate_budget_utilization(
	approved_budget: float,
	committed_amount: float,
	actual_spent: float,
) -> tuple[float, str]:
	approved_amount = as_float(approved_budget)
	utilized_amount = max(as_float(committed_amount) + as_float(actual_spent), 0)

	if approved_amount <= 0:
		return 0, "Over Budget" if utilized_amount > 0 else "No Approved Budget"

	utilization_percentage = round((utilized_amount / approved_amount) * 100, 2)
	if utilization_percentage <= 0:
		status = "Not Utilized"
	elif utilization_percentage < 50:
		status = "Low Utilization"
	elif utilization_percentage < 80:
		status = "Moderate Utilization"
	elif utilization_percentage < 100:
		status = "High Utilization"
	elif utilization_percentage == 100:
		status = "Fully Utilized"
	else:
		status = "Over Budget"

	return utilization_percentage, status


def get_cost_center_company(cost_center: str | None) -> str | None:
	if not cost_center:
		return None
	return frappe.db.get_value("Cost Center", cost_center, "company")


def get_current_fiscal_year(company: str | None = None) -> str | None:
	try:
		return get_fiscal_year(date=nowdate(), company=company)[0]
	except Exception:
		return None


def days_until(date_value: Any) -> int | None:
	if not date_value:
		return None
	return (getdate(date_value) - getdate(nowdate())).days


def add_days_to_today(days: int):
	return add_days(nowdate(), days)
