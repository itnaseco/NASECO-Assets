"""Install native DocType fields required by NASECO ASSETS."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from .patches.v1_0.add_fully_depreciated_opening_fields import execute as add_opening_fields
from .patches.v1_0.add_hr_asset_draft_fields import execute as add_hr_draft_fields
from .patches.v1_0.create_fixed_asset_custom_fields import execute as add_base_fields


def ensure_native_custom_fields() -> None:
	add_base_fields()
	add_opening_fields()
	add_hr_draft_fields()
	create_custom_fields(
		{
			"Asset": [
				{"fieldname": "custom_column_break_jvdwh", "fieldtype": "Column Break", "insert_after": "qr_code"},
				{"fieldname": "custom_column_break_tflsw", "fieldtype": "Column Break", "insert_after": "condition_status"},
				{"fieldname": "custom_column_break_79yva", "fieldtype": "Column Break", "insert_after": "asset_request"},
			],
			"Asset Category": [
				{"fieldname": "custom_section_break_hfkhw", "fieldtype": "Section Break", "insert_after": "accounts"},
				{"fieldname": "custom_column_break_wnu8x", "fieldtype": "Column Break", "insert_after": "naseco_default_depreciation_method"},
			],
			"Asset Finance Book": [
				{
					"fieldname": "naseco_residual_value_basis",
					"fieldtype": "Select",
					"label": "Residual Value Basis",
					"options": "\nFixed Amount\nPercentage\nManual",
					"insert_after": "salvage_value_percentage",
					"in_list_view": 1,
				}
			],
		},
		update=True,
	)
