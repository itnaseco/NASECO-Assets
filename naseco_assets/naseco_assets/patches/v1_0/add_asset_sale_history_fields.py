from __future__ import annotations

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute() -> None:
	create_custom_fields(
		{
			"Sales Invoice Item": [
				{
					"fieldname": "naseco_asset_net_book_value",
					"fieldtype": "Currency",
					"label": "Asset Net Book Value at Sale",
					"insert_after": "asset",
					"read_only": 1,
					"module": "NASECO ASSETS",
				},
			],
		},
		update=True,
	)
