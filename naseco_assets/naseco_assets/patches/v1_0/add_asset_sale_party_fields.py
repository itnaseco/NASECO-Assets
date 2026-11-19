from __future__ import annotations

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute() -> None:
	create_custom_fields(
		{
			"Employee": [
				{
					"fieldname": "naseco_asset_sale_customer",
					"fieldtype": "Link",
					"label": "Sales Invoice Customer",
					"options": "Customer",
					"insert_after": "bank_ac_no",
					"module": "NASECO ASSETS",
				},
			],
			"Sales Invoice": [
				{
					"fieldname": "naseco_asset_sale_employee",
					"fieldtype": "Link",
					"label": "Asset Sale Employee",
					"options": "Employee",
					"insert_after": "customer_name",
					"read_only": 1,
					"module": "NASECO ASSETS",
				},
			],
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
