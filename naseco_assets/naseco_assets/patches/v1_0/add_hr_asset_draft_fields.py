"""Mark native drafts initiated from Employee custody."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute() -> None:
	fields = {}
	for doctype, insert_after in (
		("Sales Invoice", "customer_name"),
		("Journal Entry", "user_remark"),
		("Asset Movement", "assets"),
	):
		fields[doctype] = [
			{
				"fieldname": "naseco_hr_asset",
				"fieldtype": "Link",
				"label": "HR Initiated Asset",
				"options": "Asset",
				"insert_after": insert_after,
				"read_only": 1,
				"in_standard_filter": 1,
				"module": "NASECO ASSETS",
			},
			{
				"fieldname": "naseco_hr_employee",
				"fieldtype": "Link",
				"label": "Custodian at HR Initiation",
				"options": "Employee",
				"insert_after": "naseco_hr_asset",
				"read_only": 1,
				"module": "NASECO ASSETS",
			},
			{
				"fieldname": "naseco_hr_reason",
				"fieldtype": "Small Text",
				"label": "HR Initiation Reason",
				"insert_after": "naseco_hr_employee",
				"read_only": 1,
				"module": "NASECO ASSETS",
			},
		]
	create_custom_fields(fields, update=True)
