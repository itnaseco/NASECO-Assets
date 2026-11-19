"""Keep existing coverage data in policy child rows before retiring its DocType."""

import frappe

from naseco_assets.naseco_assets.insurance import sync_asset_insurance_fields


def execute() -> None:
	if not frappe.db.exists("DocType", "Asset Insurance Coverage"):
		return

	coverages = frappe.get_all(
		"Asset Insurance Coverage",
		fields=["insurance_policy", "asset", "insured_value", "coverage_notes"],
	)
	affected_assets = set()
	for coverage in coverages:
		if not frappe.db.exists("Asset Insurance Policy", coverage.insurance_policy):
			continue
		affected_assets.add(coverage.asset)
		if frappe.db.exists("Asset Insurance Policy Item", {"parent": coverage.insurance_policy, "asset": coverage.asset}):
			continue
		asset = frappe.db.get_value("Asset", coverage.asset, ["item_code", "asset_category"], as_dict=True)
		index = frappe.db.sql(
			"SELECT COALESCE(MAX(idx), 0) + 1 FROM `tabAsset Insurance Policy Item` WHERE parent = %s",
			coverage.insurance_policy,
		)[0][0]
		frappe.db.sql(
			"""INSERT INTO `tabAsset Insurance Policy Item`
			(name, parent, parenttype, parentfield, idx, docstatus, asset, item_code,
			 asset_category, insured_value, coverage_notes, owner, creation, modified, modified_by)
			VALUES (%s, %s, 'Asset Insurance Policy', 'covered_assets', %s, %s, %s, %s,
			        %s, %s, %s, %s, NOW(), NOW(), %s)""",
			(
				frappe.generate_hash(length=10), coverage.insurance_policy, index,
				frappe.db.get_value("Asset Insurance Policy", coverage.insurance_policy, "docstatus"),
				coverage.asset, asset.item_code if asset else None,
				asset.asset_category if asset else None, coverage.insured_value,
				coverage.coverage_notes, frappe.session.user, frappe.session.user,
			),
		)

	frappe.delete_doc("DocType", "Asset Insurance Coverage", force=True, ignore_permissions=True)
	for asset in affected_assets:
		if asset:
			sync_asset_insurance_fields(asset)
