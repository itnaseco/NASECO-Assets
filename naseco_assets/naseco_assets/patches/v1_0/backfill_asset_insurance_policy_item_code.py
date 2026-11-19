from __future__ import annotations

from collections import defaultdict

import frappe


def execute() -> None:
	child_rows = frappe.get_all(
		"Asset Insurance Policy Item",
		fields=["name", "parent", "asset", "item_code"],
		order_by="creation asc",
	)

	parent_item_codes: dict[str, list[str]] = defaultdict(list)

	for row in child_rows:
		if not row.asset:
			continue

		asset_item_code = frappe.db.get_value("Asset", row.asset, "item_code")
		if not asset_item_code:
			continue

		if row.item_code != asset_item_code:
			frappe.db.set_value("Asset Insurance Policy Item", row.name, "item_code", asset_item_code, update_modified=False)

		parent_item_codes[row.parent].append(asset_item_code)

	for parent_name, item_codes in parent_item_codes.items():
		unique_item_codes = list(dict.fromkeys(item_codes))
		if len(unique_item_codes) == 1:
			current_value = frappe.db.get_value("Asset Insurance Policy", parent_name, "asset_item_code")
			if current_value != unique_item_codes[0]:
				frappe.db.set_value(
					"Asset Insurance Policy",
					parent_name,
					"asset_item_code",
					unique_item_codes[0],
					update_modified=False,
				)
