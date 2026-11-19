"""Remove the duplicate depreciation table from the Asset form."""

import frappe


def execute() -> None:
	field_name = "Asset-naseco_depreciation_preview"
	if frappe.db.exists("Custom Field", field_name):
		frappe.delete_doc("Custom Field", field_name, ignore_permissions=True)
