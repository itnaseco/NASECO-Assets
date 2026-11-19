from __future__ import annotations

import json
from pathlib import Path

import frappe


ASSET_CAPITALIZATION = "Asset Capitalization"


def _load_workspace_source(app: str, *path_parts: str) -> dict:
	path = Path(frappe.get_app_path(app, *path_parts))
	return json.loads(path.read_text())


def _insert_workspace_child(
	parent: str,
	parentfield: str,
	doctype: str,
	values: dict,
	idx: int,
) -> None:
	frappe.get_doc(
		{
			**values,
			"doctype": doctype,
			"parent": parent,
			"parentfield": parentfield,
			"parenttype": "Workspace",
			"idx": idx,
		}
	).db_insert()


def _restore_erpnext_asset_workspace() -> None:
	if not frappe.db.exists("Workspace", "Assets"):
		return
	if frappe.db.exists(
		"Workspace Link",
		{"parent": "Assets", "link_to": ASSET_CAPITALIZATION},
	):
		return

	source = _load_workspace_source(
		"erpnext",
		"assets",
		"workspace",
		"assets",
		"assets.json",
	)
	for idx, link in enumerate(source.get("links") or [], start=1):
		if link.get("link_to") != ASSET_CAPITALIZATION:
			continue

		frappe.db.sql(
			"""
			UPDATE `tabWorkspace Link`
			SET idx = idx + 1
			WHERE parent = 'Assets'
			  AND parenttype = 'Workspace'
			  AND parentfield = 'links'
			  AND idx >= %s
			""",
			idx,
		)
		_insert_workspace_child("Assets", "links", "Workspace Link", link, idx)
		break


def _replace_workspace_children(
	workspace_name: str,
	parentfield: str,
	doctype: str,
	rows: list[dict],
) -> None:
	frappe.db.delete(
		doctype,
		{
			"parent": workspace_name,
			"parenttype": "Workspace",
			"parentfield": parentfield,
		},
	)
	for idx, row in enumerate(rows, start=1):
		_insert_workspace_child(workspace_name, parentfield, doctype, row, idx)


def _restore_naseco_assets_workspace() -> None:
	if not frappe.db.exists("Workspace", "NASECO ASSETS"):
		return

	source = _load_workspace_source(
		"naseco_assets",
		"naseco_assets",
		"workspace",
		"naseco_assets",
		"naseco_assets.json",
	)
	for parentfield, doctype in (
		("links", "Workspace Link"),
		("shortcuts", "Workspace Shortcut"),
		("number_cards", "Workspace Number Card"),
	):
		_replace_workspace_children(
			"NASECO ASSETS",
			parentfield,
			doctype,
			source.get(parentfield) or [],
		)

	frappe.db.set_value(
		"Workspace",
		"NASECO ASSETS",
		"content",
		source.get("content") or "[]",
		update_modified=False,
	)
	frappe.clear_cache(doctype="Workspace")


def execute() -> None:
	_restore_erpnext_asset_workspace()
	_restore_naseco_assets_workspace()
	frappe.clear_cache(doctype="Asset")
	frappe.clear_cache(doctype="Asset Repair")
	frappe.clear_cache(doctype="Project")
	frappe.clear_cache(doctype="Workspace")
