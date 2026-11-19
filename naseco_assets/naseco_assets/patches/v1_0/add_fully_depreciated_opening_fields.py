"""Add draft-only controls for importing fully depreciated assets."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute() -> None:
	visibility = 'eval:doc.asset_type == "Existing Asset" && doc.is_fully_depreciated && !doc.calculate_depreciation'
	create_custom_fields(
		{
			"Asset": [
				{
					"fieldname": "naseco_opening_residual_source",
					"fieldtype": "Select",
					"label": "Opening Residual Source",
					"options": "\nCategory Default\nManual Override",
					"description": "Category Default recalculates opening depreciation on every draft save. Choose Manual Override for an approved historical value.",
					"insert_after": "opening_accumulated_depreciation",
					"depends_on": visibility,
				},
				{
					"fieldname": "naseco_opening_finance_book",
					"fieldtype": "Link",
					"label": "Opening Finance Book",
					"options": "Finance Book",
					"insert_after": "naseco_opening_residual_source",
					"depends_on": visibility,
				},
				{
					"fieldname": "naseco_opening_residual_value",
					"fieldtype": "Currency",
					"label": "Opening Residual Value",
					"options": "Company:company:default_currency",
					"insert_after": "naseco_opening_finance_book",
					"depends_on": visibility,
					"read_only_depends_on": 'eval:doc.naseco_opening_residual_source == "Category Default"',
				},
				{
					"fieldname": "naseco_opening_override_reason",
					"fieldtype": "Small Text",
					"label": "Opening Residual Override Reason",
					"insert_after": "naseco_opening_residual_value",
					"depends_on": 'eval:doc.asset_type == "Existing Asset" && doc.is_fully_depreciated && doc.naseco_opening_residual_source == "Manual Override"',
				},
			],
		},
		update=True,
	)
