from __future__ import annotations

from typing import Any

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from naseco_assets.naseco_assets.constants import (
	ASSET_BUSINESS_CLASSES,
	ASSET_CONDITION_STATUS_OPTIONS,
	ASSET_CRITICALITY_OPTIONS,
	ASSET_OPERATIONAL_STATUS_OPTIONS,
	ASSET_RISK_LEVEL_OPTIONS,
	CAPITALIZATION_STATUS_OPTIONS,
	FUNDING_SOURCE_OPTIONS,
)


def _options(values: list[str]) -> str:
	return "\n".join(values)


def _field(fieldname: str, fieldtype: str, label: str, **kwargs: Any) -> dict[str, Any]:
	field = {"fieldname": fieldname, "fieldtype": fieldtype, "label": label}
	field.update(kwargs)
	return field


def _section(fieldname: str, label: str, insert_after: str | None = None) -> dict[str, Any]:
	field = _field(fieldname, "Section Break", label)
	if insert_after:
		field["insert_after"] = insert_after
	return field


def execute() -> None:
	custom_fields: dict[str, list[dict[str, Any]]] = {
		"Asset": [
			_section("naseco_asset_identification_section", "Identification", insert_after="asset_name"),
			_field("asset_code_format", "Data", "Asset Code Format", read_only=1, no_copy=1, insert_after="naseco_asset_identification_section"),
			_field("qr_code", "Data", "QR Code", insert_after="asset_code_format"),
			_field("barcode", "Data", "Barcode", insert_after="qr_code"),
			_field("rfid_tag", "Data", "RFID Tag", insert_after="barcode"),
			_field("asset_photo", "Attach Image", "Asset Photo", insert_after="rfid_tag"),
			_field("manufacturer", "Data", "Manufacturer", insert_after="asset_photo"),
			_field("model", "Data", "Model", insert_after="manufacturer"),
			_field("serial_number", "Data", "Serial Number", insert_after="model"),
			_field("internal_tag_number", "Data", "Internal Tag Number", insert_after="serial_number"),
			_field("asset_criticality", "Select", "Asset Criticality", options=_options(ASSET_CRITICALITY_OPTIONS), insert_after="internal_tag_number"),
			_field("asset_risk_level", "Select", "Asset Risk Level", options=_options(ASSET_RISK_LEVEL_OPTIONS), insert_after="asset_criticality"),
			_field("asset_business_class", "Select", "Asset Business Class", options=_options(ASSET_BUSINESS_CLASSES), insert_after="asset_risk_level"),
			_section("naseco_asset_custody_section", "Location and Custody", insert_after="asset_business_class"),
			_field("branch", "Link", "Branch", options="Branch", insert_after="naseco_asset_custody_section"),
			_field("asset_location", "Link", "Asset Location", options="Location", read_only=1, insert_after="branch"),
			_field("current_custodian", "Link", "Current Custodian", options="Employee", read_only=1, insert_after="asset_location"),
			_field("custodian_department", "Link", "Custodian Department", options="Department", read_only=1, insert_after="current_custodian"),
			_field("operational_status", "Select", "Operational Status", options=_options(ASSET_OPERATIONAL_STATUS_OPTIONS), insert_after="custodian_department"),
			_field("condition_status", "Select", "Condition Status", options=_options(ASSET_CONDITION_STATUS_OPTIONS), insert_after="operational_status"),
			_section("naseco_asset_control_section", "Financial and Control", insert_after="condition_status"),
			_field("capex_plan", "Link", "CAPEX Plan", options="Fixed Asset CAPEX Plan", insert_after="naseco_asset_control_section"),
			_field("asset_request", "Link", "Asset Request", options="Fixed Asset Request", insert_after="capex_plan"),
			_field("depreciation_start_date", "Date", "Depreciation Start Date", insert_after="asset_request"),
			_field("capitalization_status", "Select", "Capitalization Status", options=_options(CAPITALIZATION_STATUS_OPTIONS), insert_after="depreciation_start_date"),
			_field("capitalization_threshold_checked", "Check", "Capitalization Threshold Checked", insert_after="capitalization_status"),
			_field("funding_source", "Select", "Funding Source", options=_options(FUNDING_SOURCE_OPTIONS), insert_after="capitalization_threshold_checked"),
			_field("insurance_required", "Check", "Insurance Required", insert_after="funding_source"),
			_field("current_insurance_policy", "Link", "Current Insurance Policy", options="Asset Insurance Policy", insert_after="insurance_required"),
			_field(
				"policy_number",
				"Data",
				"Policy Number",
				read_only=1,
				in_list_view=1,
				fetch_from="current_insurance_policy.policy_number",
				insert_after="current_insurance_policy",
			),
			_field(
				"insurance_policy_type",
				"Data",
				"Insurance Policy Type",
				read_only=1,
				in_list_view=1,
				fetch_from="current_insurance_policy.policy_type",
				insert_after="policy_number",
			),
			_field(
				"insurer",
				"Data",
				"Insurer",
				read_only=1,
				in_list_view=1,
				fetch_from="current_insurance_policy.insurance_company",
				insert_after="insurance_policy_type",
			),
			_field(
				"insurance_start_date",
				"Date",
				"Insurance Start Date",
				read_only=1,
				in_list_view=1,
				fetch_from="current_insurance_policy.coverage_start_date",
				insert_after="insurer",
			),
			_field(
				"insurance_end_date",
				"Date",
				"Insurance End Date",
				read_only=1,
				in_list_view=1,
				fetch_from="current_insurance_policy.coverage_end_date",
				insert_after="insurance_start_date",
			),
			_field("warranty_expiry_date", "Date", "Warranty Expiry Date", insert_after="insurance_end_date"),
			_field("replacement_year", "Int", "Replacement Year", insert_after="warranty_expiry_date"),
			_field("expected_replacement_cost", "Currency", "Expected Replacement Cost", insert_after="replacement_year"),
			_field("useful_life_override_reason", "Small Text", "Useful Life Override Reason", insert_after="expected_replacement_cost"),
			_field("residual_value_override_reason", "Small Text", "Residual Value Override Reason", insert_after="useful_life_override_reason"),
			_field("disposal_proceeds", "Currency", "Disposal Proceeds", insert_after="residual_value_override_reason"),
			_field("disposal_reason", "Small Text", "Disposal Reason", insert_after="disposal_proceeds"),
			_field("technical_specifications", "Table", "Technical Specifications", options="Asset Technical Specification", insert_after="disposal_reason"),
		],
		"Asset Category": [
			_section("naseco_asset_policy_section", "NASECO Fixed Asset Policy", insert_after="description"),
			_field("naseco_asset_business_class", "Select", "NASECO Asset Business Class", options=_options(ASSET_BUSINESS_CLASSES), insert_after="naseco_asset_policy_section"),
			_field("naseco_non_depreciable", "Check", "Non Depreciable", insert_after="naseco_asset_business_class"),
			_field("naseco_default_useful_life_years", "Int", "Default Useful Life (Years)", insert_after="naseco_non_depreciable"),
			_field("naseco_default_depreciation_method", "Select", "Default Depreciation Method", options="Straight Line\nReducing Balance", insert_after="naseco_default_useful_life_years"),
			_field("naseco_default_residual_value", "Currency", "Default Residual Value", insert_after="naseco_default_depreciation_method"),
			_field("naseco_usage_based_reporting", "Check", "Usage Based Reporting", insert_after="naseco_default_residual_value"),
		],
		"Employee": [
			_field(
				"naseco_asset_custody_tab",
				"Tab Break",
				"Asset Custody",
				insert_after="internal_work_history",
				module="NASECO ASSETS",
			),
			_field(
				"naseco_custodied_assets_html",
				"HTML",
				"Current Assets",
				insert_after="naseco_asset_custody_tab",
				module="NASECO ASSETS",
				no_copy=1,
			),
			_field(
				"naseco_asset_sale_customer",
				"Link",
				"Sales Invoice Customer",
				options="Customer",
				insert_after="bank_ac_no",
				module="NASECO ASSETS",
			),
		],
		"Sales Invoice": [
			_field(
				"naseco_asset_sale_employee",
				"Link",
				"Asset Sale Employee",
				options="Employee",
				insert_after="customer_name",
				read_only=1,
				module="NASECO ASSETS",
			),
		],
		"Sales Invoice Item": [
			_field(
				"naseco_asset_net_book_value",
				"Currency",
				"Asset Net Book Value at Sale",
				insert_after="asset",
				read_only=1,
				module="NASECO ASSETS",
			),
		],
		"Material Request": [
			_section("naseco_asset_request_section", "NASECO Fixed Asset Control", insert_after="transaction_date"),
			_field("asset_request", "Link", "Asset Request", options="Fixed Asset Request", insert_after="naseco_asset_request_section"),
			_field("capex_plan", "Link", "CAPEX Plan", options="Fixed Asset CAPEX Plan", insert_after="asset_request"),
			_field("cost_center", "Link", "Cost Center", options="Cost Center", insert_after="capex_plan"),
			_field("fixed_asset_category", "Link", "Fixed Asset Category", options="Asset Category", insert_after="cost_center"),
			_field("linked_asset", "Link", "Linked Asset", options="Asset", insert_after="fixed_asset_category"),
		],
		"Purchase Order": [
			_section("naseco_asset_request_section", "NASECO Fixed Asset Control", insert_after="transaction_date"),
			_field("asset_request", "Link", "Asset Request", options="Fixed Asset Request", insert_after="naseco_asset_request_section"),
			_field("capex_plan", "Link", "CAPEX Plan", options="Fixed Asset CAPEX Plan", insert_after="asset_request"),
			_field("fixed_asset_category", "Link", "Fixed Asset Category", options="Asset Category", insert_after="capex_plan"),
			_field("linked_asset", "Link", "Linked Asset", options="Asset", insert_after="fixed_asset_category"),
		],
		"Purchase Receipt": [
			_section("naseco_asset_request_section", "NASECO Fixed Asset Control", insert_after="posting_date"),
			_field("asset_request", "Link", "Asset Request", options="Fixed Asset Request", insert_after="naseco_asset_request_section"),
			_field("capex_plan", "Link", "CAPEX Plan", options="Fixed Asset CAPEX Plan", insert_after="asset_request"),
			_field("fixed_asset_category", "Link", "Fixed Asset Category", options="Asset Category", insert_after="capex_plan"),
			_field("linked_asset", "Link", "Linked Asset", options="Asset", insert_after="fixed_asset_category"),
		],
		"Purchase Invoice": [
			_section("naseco_asset_request_section", "NASECO Fixed Asset Control", insert_after="posting_date"),
			_field("asset_request", "Link", "Asset Request", options="Fixed Asset Request", insert_after="naseco_asset_request_section"),
			_field("capex_plan", "Link", "CAPEX Plan", options="Fixed Asset CAPEX Plan", insert_after="asset_request"),
			_field("fixed_asset_category", "Link", "Fixed Asset Category", options="Asset Category", insert_after="capex_plan"),
			_field("linked_asset", "Link", "Linked Asset", options="Asset", insert_after="fixed_asset_category"),
		],
		"Project": [
			_section("naseco_asset_cip_section", "NASECO Capital Projects", insert_after="company"),
			_field("cip_capitalization_request", "Link", "CIP Capitalization Request", options="CIP Capitalization Request", insert_after="naseco_asset_cip_section"),
		],
	}

	create_custom_fields(custom_fields, update=True)
