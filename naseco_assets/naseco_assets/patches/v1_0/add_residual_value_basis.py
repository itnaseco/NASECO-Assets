"""Add residual policy selection without altering existing Asset schedules."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt

from naseco_assets.naseco_assets.residual_value import FIXED_AMOUNT, PERCENTAGE


def execute() -> None:
	create_custom_fields(
		{
			"Asset Finance Book": [
				{
					"fieldname": "naseco_residual_value_basis",
					"fieldtype": "Select",
					"label": "Residual Value Basis",
					"options": "\nFixed Amount\nPercentage\nManual",
					"description": "On a category, Fixed Amount uses its Default Residual Value. On an Asset, Manual keeps the entered Expected Value After Useful Life.",
					"insert_after": "salvage_value_percentage",
					"in_list_view": 1,
				},
			],
			"Asset": [
				{
					"fieldname": "naseco_depreciation_preview",
					"fieldtype": "HTML",
					"label": "Depreciation Preview",
					"insert_after": "finance_books",
					"depends_on": "eval:doc.calculate_depreciation",
					"no_copy": 1,
				},
			],
		},
		update=True,
	)

	for category in frappe.get_all(
		"Asset Category", fields=["name", "naseco_default_residual_value"]
	):
		for row in frappe.get_all(
			"Asset Finance Book",
			filters={"parenttype": "Asset Category", "parent": category.name},
			fields=["name", "naseco_residual_value_basis", "salvage_value_percentage"],
		):
			if row.naseco_residual_value_basis:
				continue
			basis = (
				FIXED_AMOUNT
				if flt(category.naseco_default_residual_value) > 0
				and not flt(row.salvage_value_percentage)
				else PERCENTAGE
			)
			frappe.db.set_value("Asset Finance Book", row.name, "naseco_residual_value_basis", basis)
