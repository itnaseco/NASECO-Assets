from __future__ import annotations

import json

import frappe

from naseco_assets.naseco_assets.constants import ASSET_OPERATIONAL_STATUS_OPTIONS


COMMISSIONING_DOCTYPE = "Asset Commissioning Certificate"
COMMISSIONING_WORKFLOW = "Asset Commissioning Certificate Workflow"
COMMISSIONING_NUMBER_CARD = "Assets Awaiting Commissioning"
PENDING_CAPITALIZATION_NUMBER_CARD = "Assets Pending Capitalization"
LEGACY_CUSTODY_DOCTYPE = "Asset Custody Assignment"
ASSET_MOVEMENT_DOCTYPE = "Asset Movement"


def _preserve_asset_dates() -> None:
	if not frappe.db.has_column("Asset", "commissioning_date"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabAsset`
		SET available_for_use_date = commissioning_date
		WHERE commissioning_date IS NOT NULL
		  AND available_for_use_date IS NULL
		"""
	)
	if frappe.db.has_column("Asset", "depreciation_start_date"):
		frappe.db.sql(
			"""
			UPDATE `tabAsset`
			SET depreciation_start_date = commissioning_date
			WHERE commissioning_date IS NOT NULL
			  AND depreciation_start_date IS NULL
			"""
		)


def _normalize_operational_status() -> None:
	if not frappe.db.has_column("Asset", "operational_status"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabAsset`
		SET operational_status = CASE
			WHEN docstatus = 1 OR available_for_use_date IS NOT NULL THEN 'Active'
			ELSE 'Inactive'
		END
		WHERE operational_status = 'Not Commissioned'
		"""
	)
	field_name = frappe.db.get_value(
		"Custom Field",
		{"dt": "Asset", "fieldname": "operational_status"},
		"name",
	)
	if field_name:
		frappe.db.set_value(
			"Custom Field",
			field_name,
			"options",
			"\n".join(ASSET_OPERATIONAL_STATUS_OPTIONS),
			update_modified=False,
		)


def _remove_custom_fields() -> None:
	field_filters = {
		"Asset": ["commissioning_date", "commissioning_certificate", "commissioning_remarks"],
		"Asset Category": ["naseco_requires_commissioning"],
	}
	for doctype, fieldnames in field_filters.items():
		for field_name in frappe.get_all(
			"Custom Field",
			filters={"dt": doctype, "fieldname": ["in", fieldnames]},
			pluck="name",
		):
			frappe.delete_doc("Custom Field", field_name, force=True, ignore_permissions=True)


def _remove_workspace_references() -> None:
	if not frappe.db.exists("Workspace", "NASECO ASSETS"):
		return

	workspace = frappe.get_doc("Workspace", "NASECO ASSETS")
	workspace.set(
		"links",
		[
			row
			for row in workspace.links
			if row.get("link_to") not in {COMMISSIONING_DOCTYPE, LEGACY_CUSTODY_DOCTYPE}
		],
	)

	shortcuts = [
		row
		for row in workspace.shortcuts
		if row.get("link_to") not in {COMMISSIONING_DOCTYPE, LEGACY_CUSTODY_DOCTYPE}
	]
	if not any(row.get("link_to") == ASSET_MOVEMENT_DOCTYPE for row in shortcuts):
		shortcuts.append(
			{
				"label": ASSET_MOVEMENT_DOCTYPE,
				"link_to": ASSET_MOVEMENT_DOCTYPE,
				"type": "DocType",
			}
		)
	workspace.set("shortcuts", shortcuts)

	number_cards = [
		row
		for row in workspace.number_cards
		if row.get("number_card_name") != COMMISSIONING_NUMBER_CARD
	]
	if not any(
		row.get("number_card_name") == PENDING_CAPITALIZATION_NUMBER_CARD
		for row in number_cards
	):
		number_cards.append(
			{
				"label": PENDING_CAPITALIZATION_NUMBER_CARD,
				"number_card_name": PENDING_CAPITALIZATION_NUMBER_CARD,
			}
		)
	workspace.set("number_cards", number_cards)

	if workspace.content:
		content = json.loads(workspace.content)
		has_asset_movement = any(
			block.get("data", {}).get("shortcut_name") == ASSET_MOVEMENT_DOCTYPE
			for block in content
		)
		cleaned_content = []
		for block in content:
			data = block.get("data", {})
			if data.get("shortcut_name") == LEGACY_CUSTODY_DOCTYPE:
				continue
			if data.get("shortcut_name") == COMMISSIONING_DOCTYPE:
				if has_asset_movement:
					continue
				data["shortcut_name"] = ASSET_MOVEMENT_DOCTYPE
				has_asset_movement = True
			if data.get("number_card_name") == COMMISSIONING_NUMBER_CARD:
				data["number_card_name"] = PENDING_CAPITALIZATION_NUMBER_CARD
			cleaned_content.append(block)
		content = cleaned_content

		if not any(
			block.get("data", {}).get("number_card_name") == PENDING_CAPITALIZATION_NUMBER_CARD
			for block in content
		):
			insert_at = next(
				(index for index, block in enumerate(content) if block.get("id") == "na-05"),
				len(content),
			)
			content.insert(
				insert_at,
				{
					"id": "na-04",
					"type": "number_card",
					"data": {"number_card_name": PENDING_CAPITALIZATION_NUMBER_CARD, "col": 4},
				},
			)

		if not has_asset_movement:
			insert_at = next(
				(index for index, block in enumerate(content) if block.get("id") == "na-25"),
				len(content),
			)
			content.insert(
				insert_at,
				{
					"id": "na-24",
					"type": "shortcut",
					"data": {"shortcut_name": ASSET_MOVEMENT_DOCTYPE, "col": 3},
				},
			)
		workspace.content = json.dumps(content, separators=(",", ":"))

	workspace.save(ignore_permissions=True)


def _delete_metadata() -> None:
	for doctype, name in (
		("Workflow", COMMISSIONING_WORKFLOW),
		("Number Card", COMMISSIONING_NUMBER_CARD),
	):
		if frappe.db.exists(doctype, name):
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)

	if frappe.db.exists("DocType", COMMISSIONING_DOCTYPE):
		frappe.delete_doc("DocType", COMMISSIONING_DOCTYPE, force=True, ignore_permissions=True)

	for action_name in ("Approve Technical", "Commission"):
		action = frappe.db.get_value(
			"Workflow Action Master",
			{"workflow_action_name": action_name},
			"name",
		)
		if action and not frappe.db.exists("Workflow Transition", {"action": action_name}):
			frappe.delete_doc("Workflow Action Master", action, force=True, ignore_permissions=True)

	if (
		frappe.db.exists("Workflow State", "Pending Technical Review")
		and not frappe.db.exists("Workflow Document State", {"state": "Pending Technical Review"})
	):
		frappe.delete_doc(
			"Workflow State",
			"Pending Technical Review",
			force=True,
			ignore_permissions=True,
		)


def _ensure_pending_capitalization_card() -> None:
	values = {
		"doctype": "Number Card",
		"label": PENDING_CAPITALIZATION_NUMBER_CARD,
		"document_type": "Asset",
		"type": "Document Type",
		"function": "Count",
		"filters_json": '[[\"Asset\", \"capitalization_status\", \"=\", \"Pending\"]]',
		"dynamic_filters_json": "[]",
		"is_public": 1,
		"is_standard": 1,
		"show_percentage_stats": 0,
		"stats_time_interval": "Monthly",
		"module": "NASECO ASSETS",
		"name": PENDING_CAPITALIZATION_NUMBER_CARD,
	}
	if frappe.db.exists("Number Card", PENDING_CAPITALIZATION_NUMBER_CARD):
		card = frappe.get_doc("Number Card", PENDING_CAPITALIZATION_NUMBER_CARD)
		card.update(values)
		card.save(ignore_permissions=True)
	else:
		frappe.get_doc(values).insert(ignore_permissions=True)


def execute() -> None:
	_preserve_asset_dates()
	_normalize_operational_status()
	_remove_custom_fields()
	_delete_metadata()
	_ensure_pending_capitalization_card()
	_remove_workspace_references()
