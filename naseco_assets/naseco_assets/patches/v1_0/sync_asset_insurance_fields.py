from __future__ import annotations

import frappe

from naseco_assets.naseco_assets.insurance import sync_asset_insurance_fields


def execute() -> None:
	"""Rebuild display fields without changing the policy or coverage records."""
	assets = set(frappe.get_all("Asset Insurance Policy Item", pluck="asset"))
	assets.update(frappe.get_all("Asset", filters={"current_insurance_policy": ["!=", ""]}, pluck="name"))
	for asset in assets:
		if asset:
			sync_asset_insurance_fields(asset)
