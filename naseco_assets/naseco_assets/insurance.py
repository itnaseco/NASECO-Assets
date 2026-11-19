from __future__ import annotations

import frappe
from frappe.utils import nowdate


ASSET_INSURANCE_FIELDS = (
	"current_insurance_policy",
	"policy_number",
	"insurance_policy_type",
	"insurer",
	"insured_value",
	"insurance_start_date",
	"insurance_end_date",
)


def get_effective_insurance_policy(asset: str, on_date: str | None = None) -> dict | None:
	"""Find confirmed cover for one asset on a date."""
	rows = frappe.db.sql(
		"""
		SELECT policy.name, policy.policy_number, policy.policy_type,
		       policy.insurance_company, policy.coverage_start_date,
		       policy.coverage_end_date,
		       COALESCE((SELECT item.insured_value
		            FROM `tabAsset Insurance Policy Item` item
		            WHERE item.asset = %s AND item.parent = policy.name
		            LIMIT 1), policy.insured_value) AS insured_value
		FROM `tabAsset Insurance Policy` policy
		WHERE policy.docstatus = 1
		  AND policy.coverage_start_date <= %s
		  AND policy.coverage_end_date >= %s
		  AND EXISTS (SELECT 1 FROM `tabAsset Insurance Policy Item` item
		              WHERE item.asset = %s AND item.parent = policy.name)
		ORDER BY policy.coverage_start_date DESC, policy.coverage_end_date DESC, policy.name DESC
		LIMIT 1
		""",
		(asset, on_date or nowdate(), on_date or nowdate(), asset),
		as_dict=True,
	)
	return rows[0] if rows else None


def sync_asset_insurance_fields(asset: str) -> None:
	"""Maintain the submitted Asset's display-only insurance cache."""
	if not frappe.db.exists("Asset", asset):
		return
	policy = get_effective_insurance_policy(asset)
	values = {
		"current_insurance_policy": policy.name if policy else None,
		"policy_number": policy.policy_number if policy else None,
		"insurance_policy_type": policy.policy_type if policy else None,
		"insurer": policy.insurance_company if policy else None,
		"insured_value": policy.insured_value if policy else None,
		"insurance_start_date": policy.coverage_start_date if policy else None,
		"insurance_end_date": policy.coverage_end_date if policy else None,
	}
	asset_meta = frappe.get_meta("Asset")
	frappe.db.set_value(
		"Asset",
		asset,
		{field: values[field] for field in ASSET_INSURANCE_FIELDS if asset_meta.has_field(field)},
		update_modified=False,
	)


def sync_assets_for_insurance_policy(policy: str) -> None:
	assets = set(frappe.get_all("Asset Insurance Policy Item", filters={"parent": policy}, pluck="asset"))
	assets.update(frappe.get_all("Asset", filters={"current_insurance_policy": policy}, pluck="name"))
	for asset in assets:
		if asset:
			sync_asset_insurance_fields(asset)
