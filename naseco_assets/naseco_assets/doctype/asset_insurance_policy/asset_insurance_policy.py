import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate

from naseco_assets.naseco_assets.insurance import get_effective_insurance_policy

from naseco_assets.naseco_assets.asset_hooks import (
	before_submit_insurance_policy,
	on_cancel_insurance_policy,
	on_submit_insurance_policy,
	on_update_after_submit_insurance_policy,
	validate_insurance_policy,
)


class AssetInsurancePolicy(Document):
	def validate(self):
		validate_insurance_policy(self)

	def before_submit(self):
		before_submit_insurance_policy(self)

	def on_submit(self):
		on_submit_insurance_policy(self)

	def on_update_after_submit(self):
		on_update_after_submit_insurance_policy(self)

	def on_cancel(self):
		on_cancel_insurance_policy(self)


@frappe.whitelist(methods=["GET"])
def get_eligible_policies(asset: str) -> list[dict]:
	frappe.get_doc("Asset", asset).check_permission("read")
	asset_category = frappe.db.get_value("Asset", asset, "asset_category")
	policies = frappe.get_list(
		"Asset Insurance Policy",
		filters={"docstatus": 1, "coverage_end_date": [">=", nowdate()]},
		fields=["name", "policy_number", "insurance_company", "asset_category", "coverage_start_date", "coverage_end_date"],
		order_by="coverage_end_date desc",
		limit_page_length=500,
	)
	return [policy for policy in policies if not policy.asset_category or policy.asset_category == asset_category]


@frappe.whitelist(methods=["POST"])
def add_asset_coverage(asset: str, insurance_policy: str) -> str:
	frappe.get_doc("Asset", asset).check_permission("read")
	frappe.db.sql("SELECT name FROM `tabAsset Insurance Policy` WHERE name = %s FOR UPDATE", insurance_policy)
	policy = frappe.get_doc("Asset Insurance Policy", insurance_policy)
	policy.check_permission("write")
	if policy.docstatus != 1:
		frappe.throw(_("Confirm the insurance policy before adding asset coverage."))
	if any(row.asset == asset for row in policy.covered_assets):
		frappe.throw(_("This asset is already covered by the selected policy."))
	policy.append("covered_assets", {"asset": asset})
	policy.save()
	return policy.name


@frappe.whitelist(methods=["GET"])
def get_current_coverage(asset: str) -> dict | None:
	frappe.get_doc("Asset", asset).check_permission("read")
	policy = get_effective_insurance_policy(asset)
	if policy and frappe.has_permission("Asset Insurance Policy", "read", policy.name):
		return policy
	return None
