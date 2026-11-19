from __future__ import annotations

import frappe


def execute() -> None:
	field_name = "Employee-naseco_asset_sale_customer"
	if not frappe.db.exists("Custom Field", field_name):
		return

	frappe.db.set_value(
		"Custom Field",
		field_name,
		"insert_after",
		"bank_ac_no",
		update_modified=False,
	)
	frappe.clear_cache(doctype="Employee")
