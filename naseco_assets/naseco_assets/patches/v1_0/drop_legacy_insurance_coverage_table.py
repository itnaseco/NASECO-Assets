"""Remove the retired insurance coverage table after its data has moved."""

import frappe


def execute() -> None:
	frappe.db.sql("DROP TABLE IF EXISTS `tabAsset Insurance Coverage`")
