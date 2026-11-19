"""Retire verification UI while preserving any historical Asset data."""

import frappe


def execute() -> None:
	workflow = "Asset Verification Batch Workflow"
	if frappe.db.exists("Workflow", workflow):
		frappe.delete_doc("Workflow", workflow, ignore_permissions=True)

	field = "Asset-last_verification_date"
	if not frappe.db.exists("Custom Field", field):
		return

	if frappe.db.exists("Asset", {"last_verification_date": ["is", "set"]}):
		frappe.db.set_value(
			"Custom Field", field, {"hidden": 1, "read_only": 1}, update_modified=False
		)
	else:
		frappe.delete_doc("Custom Field", field, ignore_permissions=True)
