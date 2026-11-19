app_name = "naseco_assets"
app_title = "NASECO ASSETS"
app_publisher = "Matovu Matthew"
app_description = "An extension to the Frappe Assets App to manage NASECO Assets"
app_email = "itnaseco@gmail.com"
app_license = "mit"
app_logo_url = "/assets/naseco_assets/images/naseco-assets.svg"
app_home = "/desk/naseco-assets"
required_apps = ["erpnext", "hrms"]
after_install = "naseco_assets.naseco_assets.setup.ensure_native_custom_fields"
after_migrate = "naseco_assets.naseco_assets.patches.v1_0.restore_asset_capitalization._restore_naseco_assets_workspace"

override_whitelisted_methods = {
	"erpnext.assets.doctype.asset.asset.make_sales_invoice": "naseco_assets.naseco_assets.api.make_sales_invoice_for_asset_sale",
	"erpnext.assets.doctype.asset.asset.get_item_details": "naseco_assets.naseco_assets.residual_value.get_item_details",
}

doctype_js = {
	"Asset": ["public/js/asset.js", "public/js/fully_depreciated_opening.js"],
	"Employee": "public/js/employee.js",
	"Asset Insurance Policy": "public/js/asset_insurance_policy.js",
	"Fixed Asset Request": "public/js/fixed_asset_request.js",
	"Fixed Asset CAPEX Plan": "public/js/fixed_asset_capex_plan.js",
}

doctype_list_js = {
	"Asset": "public/js/fixed_asset_management.js",
	"Fixed Asset Request": "public/js/fixed_asset_management.js",
	"Fixed Asset CAPEX Plan": "public/js/fixed_asset_management.js",
	"Asset Insurance Policy": "public/js/fixed_asset_management.js",
	"Asset Maintenance Plan": "public/js/fixed_asset_management.js",
	"CIP Capitalization Request": "public/js/fixed_asset_management.js",
}

scheduler_events = {
	"daily": [
		"naseco_assets.naseco_assets.notifications.run_daily_asset_alerts",
	],
}

doc_events = {
	"Asset": {
		"before_validate": "naseco_assets.naseco_assets.asset_hooks.before_validate_asset",
		"validate": "naseco_assets.naseco_assets.asset_hooks.validate_asset",
		"on_update": "naseco_assets.naseco_assets.asset_hooks.on_update_asset",
		"before_submit": "naseco_assets.naseco_assets.asset_hooks.before_submit_asset",
		"on_submit": "naseco_assets.naseco_assets.asset_hooks.on_submit_asset",
		"on_cancel": "naseco_assets.naseco_assets.asset_hooks.on_cancel_asset",
		"on_update_after_submit": "naseco_assets.naseco_assets.asset_hooks.on_update_after_submit_asset",
	},
	"Asset Category": {
		"before_validate": "naseco_assets.naseco_assets.residual_value.before_validate_asset_category",
	},
	"Asset Movement": {
		"on_submit": "naseco_assets.naseco_assets.asset_hooks.on_submit_asset_movement",
		"on_cancel": "naseco_assets.naseco_assets.asset_hooks.on_cancel_asset_movement",
		"on_update_after_submit": "naseco_assets.naseco_assets.asset_hooks.on_update_after_submit_asset_movement",
	},
	"Material Request": {
		"validate": "naseco_assets.naseco_assets.asset_hooks.validate_material_request",
		"on_submit": "naseco_assets.naseco_assets.asset_hooks.on_submit_material_request",
		"on_cancel": "naseco_assets.naseco_assets.asset_hooks.on_cancel_material_request",
		"on_update_after_submit": "naseco_assets.naseco_assets.asset_hooks.on_update_after_submit_material_request",
	},
	"Purchase Order": {
		"validate": "naseco_assets.naseco_assets.asset_hooks.validate_purchase_order",
		"on_submit": "naseco_assets.naseco_assets.asset_hooks.on_submit_purchase_order",
		"on_cancel": "naseco_assets.naseco_assets.asset_hooks.on_cancel_purchase_order",
		"on_update_after_submit": "naseco_assets.naseco_assets.asset_hooks.on_update_after_submit_purchase_order",
	},
	"Purchase Receipt": {
		"validate": "naseco_assets.naseco_assets.asset_hooks.validate_purchase_receipt",
		"on_submit": "naseco_assets.naseco_assets.asset_hooks.on_submit_purchase_receipt",
		"on_cancel": "naseco_assets.naseco_assets.asset_hooks.on_cancel_purchase_receipt",
		"on_update_after_submit": "naseco_assets.naseco_assets.asset_hooks.on_update_after_submit_purchase_receipt",
	},
	"Purchase Invoice": {
		"validate": "naseco_assets.naseco_assets.asset_hooks.validate_purchase_invoice",
		"on_submit": "naseco_assets.naseco_assets.asset_hooks.on_submit_purchase_invoice",
		"on_cancel": "naseco_assets.naseco_assets.asset_hooks.on_cancel_purchase_invoice",
		"on_update_after_submit": "naseco_assets.naseco_assets.asset_hooks.on_update_after_submit_purchase_invoice",
	},
	"Journal Entry": {
		"before_submit": "naseco_assets.naseco_assets.hr_asset_actions.validate_hr_scrap_before_submit",
	},
}

fixtures = [
	{
		"dt": "Custom Field",
		"filters": [
			[
				"name",
				"in",
				[
					"Employee-naseco_asset_custody_tab",
					"Employee-naseco_custodied_assets_html",
					"Employee-naseco_asset_sale_customer",
					"Sales Invoice-naseco_asset_sale_employee",
					"Sales Invoice Item-naseco_asset_net_book_value",
					"Sales Invoice-naseco_hr_asset",
					"Sales Invoice-naseco_hr_employee",
					"Sales Invoice-naseco_hr_reason",
					"Journal Entry-naseco_hr_asset",
					"Journal Entry-naseco_hr_employee",
					"Journal Entry-naseco_hr_reason",
					"Asset Movement-naseco_hr_asset",
					"Asset Movement-naseco_hr_employee",
					"Asset Movement-naseco_hr_reason",
				],
			]
		],
	},
	{
		"dt": "Property Setter",
		"filters": [["name", "in", [
			"Asset Category-main-field_order",
			"Asset Category-naseco_default_depreciation_method-hidden",
			"Asset Category-naseco_usage_based_reporting-hidden",
			"Asset Category-naseco_non_depreciable-hidden",
			"Asset-insurer-in_list_view",
			"Asset-current_custodian-in_list_view",
			"Asset-serial_number-in_list_view",
			"Asset-insurance_start_date-in_list_view",
			"Asset-insurance_end_date-in_list_view",
		]]],
	},
	"Role",
	"Workflow",
	"Workspace",
	"Report",
	"Dashboard Chart",
	"Number Card",
]

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page.
add_to_apps_screen = [
	{
		"name": app_name,
		"logo": app_logo_url,
		"title": app_title,
		"route": app_home,
		"sequence_id": 11,
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_js = "/assets/naseco_assets/js/naseco_assets.js"

# include js, css files in header of web template
# web_include_css = "/assets/naseco_assets/css/naseco_assets.css"
# web_include_js = "/assets/naseco_assets/js/naseco_assets.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "naseco_assets/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "naseco_assets/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "naseco_assets.utils.jinja_methods",
# 	"filters": "naseco_assets.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "naseco_assets.install.before_install"
# after_install = "naseco_assets.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "naseco_assets.uninstall.before_uninstall"
# after_uninstall = "naseco_assets.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "naseco_assets.utils.before_app_install"
# after_app_install = "naseco_assets.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "naseco_assets.utils.before_app_uninstall"
# after_app_uninstall = "naseco_assets.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "naseco_assets.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"naseco_assets.tasks.all"
# 	],
# 	"daily": [
# 		"naseco_assets.tasks.daily"
# 	],
# 	"hourly": [
# 		"naseco_assets.tasks.hourly"
# 	],
# 	"weekly": [
# 		"naseco_assets.tasks.weekly"
# 	],
# 	"monthly": [
# 		"naseco_assets.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "naseco_assets.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "naseco_assets.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "naseco_assets.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["naseco_assets.utils.before_request"]
# after_request = ["naseco_assets.utils.after_request"]

# Job Events
# ----------
# before_job = ["naseco_assets.utils.before_job"]
# after_job = ["naseco_assets.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"naseco_assets.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
