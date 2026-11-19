from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute() -> None:
	create_custom_fields(
		{
			"Employee": [
				{
					"fieldname": "naseco_asset_custody_tab",
					"fieldtype": "Tab Break",
					"label": "Asset Custody",
					"insert_after": "internal_work_history",
					"module": "NASECO ASSETS",
				},
				{
					"fieldname": "naseco_custodied_assets_html",
					"fieldtype": "HTML",
					"label": "Current Assets",
					"insert_after": "naseco_asset_custody_tab",
					"module": "NASECO ASSETS",
					"no_copy": 1,
				},
			]
		},
		update=True,
	)
