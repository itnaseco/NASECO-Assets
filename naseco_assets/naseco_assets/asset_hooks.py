from __future__ import annotations

from frappe.utils import flt

from . import lifecycle
from .residual_value import apply_asset_residual_defaults
from .fully_depreciated_opening import prepare_fully_depreciated_opening, remove_unused_draft_schedules


def before_validate_asset(doc, method=None):
	prepare_fully_depreciated_opening(doc)
	apply_asset_residual_defaults(doc)
	if doc.docstatus == 0 and not doc.get("split_from"):
		opening_depreciation = (
			flt(doc.get("opening_accumulated_depreciation"))
			if doc.get("asset_type") == "Existing Asset"
			else 0
		)
		doc.value_after_depreciation = (
			flt(doc.get("net_purchase_amount"))
			- opening_depreciation
			+ flt(doc.get("additional_asset_cost"))
		)


def on_update_asset(doc, method=None):
	remove_unused_draft_schedules(doc)


def validate_asset(doc, method=None):
	lifecycle.validate_asset(doc)
	if (
		doc.docstatus == 0
		and doc.get("asset_type") == "Existing Asset"
		and doc.get("is_fully_depreciated")
		and not doc.get("calculate_depreciation")
	):
		doc.set("finance_books", [])


def before_submit_asset(doc, method=None):
	lifecycle.before_submit_asset(doc)


def on_submit_asset(doc, method=None):
	lifecycle.on_submit_asset(doc)


def on_cancel_asset(doc, method=None):
	lifecycle.on_cancel_asset(doc)


def on_update_after_submit_asset(doc, method=None):
	lifecycle.on_update_after_submit_asset(doc)


def validate_fixed_asset_request(doc, method=None):
	lifecycle.validate_fixed_asset_request(doc)


def on_submit_fixed_asset_request(doc, method=None):
	lifecycle.on_submit_fixed_asset_request(doc)


def on_update_after_submit_fixed_asset_request(doc, method=None):
	lifecycle.on_update_after_submit_fixed_asset_request(doc)


def validate_material_request(doc, method=None):
	lifecycle.validate_material_request(doc)


def on_submit_material_request(doc, method=None):
	lifecycle.on_submit_material_request(doc)


def on_cancel_material_request(doc, method=None):
	lifecycle.on_cancel_material_request(doc)


def on_update_after_submit_material_request(doc, method=None):
	lifecycle.on_update_after_submit_material_request(doc)


def validate_purchase_order(doc, method=None):
	lifecycle.validate_purchase_order(doc)


def on_submit_purchase_order(doc, method=None):
	lifecycle.on_submit_purchase_order(doc)


def on_cancel_purchase_order(doc, method=None):
	lifecycle.on_cancel_purchase_order(doc)


def on_update_after_submit_purchase_order(doc, method=None):
	lifecycle.on_update_after_submit_purchase_order(doc)


def validate_purchase_receipt(doc, method=None):
	lifecycle.validate_purchase_receipt(doc)


def on_submit_purchase_receipt(doc, method=None):
	lifecycle.on_submit_purchase_receipt(doc)


def on_cancel_purchase_receipt(doc, method=None):
	lifecycle.on_cancel_purchase_receipt(doc)


def on_update_after_submit_purchase_receipt(doc, method=None):
	lifecycle.on_update_after_submit_purchase_receipt(doc)


def validate_purchase_invoice(doc, method=None):
	lifecycle.validate_purchase_invoice(doc)


def on_submit_purchase_invoice(doc, method=None):
	lifecycle.on_submit_purchase_invoice(doc)


def on_cancel_purchase_invoice(doc, method=None):
	lifecycle.on_cancel_purchase_invoice(doc)


def on_update_after_submit_purchase_invoice(doc, method=None):
	lifecycle.on_update_after_submit_purchase_invoice(doc)


def validate_capex_plan(doc, method=None):
	lifecycle.validate_capex_plan(doc)


def refresh_capex_plan_totals(doc, method=None):
	plan_name = doc.name if hasattr(doc, "name") else doc
	lifecycle.refresh_capex_plan_totals(plan_name)


def on_submit_asset_movement(doc, method=None):
	lifecycle.on_submit_asset_movement(doc)


def on_cancel_asset_movement(doc, method=None):
	lifecycle.on_cancel_asset_movement(doc)


def on_update_after_submit_asset_movement(doc, method=None):
	lifecycle.on_submit_asset_movement(doc)


def validate_insurance_policy(doc, method=None):
	lifecycle.validate_insurance_policy(doc)


def on_submit_insurance_policy(doc, method=None):
	lifecycle.on_submit_insurance_policy(doc)


def before_submit_insurance_policy(doc, method=None):
	lifecycle.before_submit_insurance_policy(doc)


def on_update_after_submit_insurance_policy(doc, method=None):
	lifecycle.on_update_after_submit_insurance_policy(doc)


def on_cancel_insurance_policy(doc, method=None):
	lifecycle.on_cancel_insurance_policy(doc)


def validate_insurance_claim(doc, method=None):
	lifecycle.validate_insurance_claim(doc)


def validate_maintenance_plan(doc, method=None):
	lifecycle.validate_maintenance_plan(doc)


def validate_usage_reading(doc, method=None):
	lifecycle.validate_usage_reading(doc)


def validate_cip_capitalization_request(doc, method=None):
	lifecycle.validate_cip_capitalization_request(doc)


def on_submit_cip_capitalization_request(doc, method=None):
	lifecycle.on_submit_cip_capitalization_request(doc)
