"""Persist approval states that old post-save hooks left out of sync."""

import frappe


def execute() -> None:
	for name in frappe.get_all(
		"Asset Insurance Policy",
		filters={
			"docstatus": 1,
			"approval_status": ["in", ["Draft", "Pending Review", "Returned for Revision", "Rejected"]],
		},
		pluck="name",
	):
		frappe.db.set_value(
			"Asset Insurance Policy", name, "approval_status", "Approved", update_modified=False
		)

	for name in frappe.get_all(
		"Asset Insurance Policy",
		filters={"docstatus": 2},
		pluck="name",
	):
		frappe.db.set_value(
			"Asset Insurance Policy",
			name,
			{"approval_status": "Cancelled", "status": "Cancelled"},
			update_modified=False,
		)
