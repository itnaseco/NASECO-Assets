from __future__ import annotations

import json

import frappe
from frappe.permissions import setup_custom_perms

from naseco_assets.naseco_assets.constants import (
	ROLE_ASSET_ADMINISTRATOR,
	ROLE_EXECUTIVE_VIEWER,
	ROLE_FINANCE_MANAGER,
	ROLE_FIXED_ASSET_ACCOUNTANT,
	ROLE_INTERNAL_AUDITOR,
)


LEGACY_DOCTYPE = "Asset Custody Assignment"
MOVEMENT_DOCTYPE = "Asset Movement"
MIRROR_FIELDS = ("asset_location", "current_custodian", "custodian_department")
PERMISSION_FIELDS = (
	"select",
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"report",
	"export",
	"import",
	"share",
	"print",
	"email",
)


def _latest_movement_states() -> dict[str, frappe._dict]:
	rows = frappe.db.sql(
		"""
		SELECT
			movement_item.asset,
			movement_item.target_location AS location,
			movement_item.to_employee AS custodian
		FROM `tabAsset Movement Item` movement_item
		INNER JOIN `tabAsset Movement` movement
			ON movement.name = movement_item.parent
		WHERE movement.docstatus = 1
		ORDER BY
			movement.transaction_date DESC,
			movement.creation DESC,
			movement_item.idx DESC
		""",
		as_dict=True,
	)
	states: dict[str, frappe._dict] = {}
	for row in rows:
		if row.asset not in states:
			states[row.asset] = row
	return states


def _latest_legacy_states() -> dict[str, frappe._dict]:
	if not frappe.db.exists("DocType", LEGACY_DOCTYPE):
		return {}

	rows = frappe.db.sql(
		"""
		SELECT
			asset,
			location,
			assigned_to AS custodian,
			department,
			branch,
			status
		FROM `tabAsset Custody Assignment`
		WHERE docstatus = 1
		ORDER BY assignment_date DESC, creation DESC
		""",
		as_dict=True,
	)
	states: dict[str, frappe._dict] = {}
	for row in rows:
		if row.asset in states:
			continue
		if row.status not in {"Active", "Transferred"}:
			row.custodian = None
		states[row.asset] = row
	return states


def _employee_context(employee: str | None) -> frappe._dict:
	if not employee:
		return frappe._dict()
	return (
		frappe.db.get_value(
			"Employee",
			employee,
			["department", "branch"],
			as_dict=True,
		)
		or frappe._dict()
	)


def _sync_asset_state() -> None:
	movement_states = _latest_movement_states()
	legacy_states = _latest_legacy_states()
	assets = frappe.get_all(
		"Asset",
		fields=["name", "location", "custodian", "department", "branch"],
	)

	for asset in assets:
		state = movement_states.get(asset.name) or legacy_states.get(asset.name)
		location = state.location if state and state.location else asset.location
		custodian = state.custodian if state else asset.custodian
		employee = _employee_context(custodian)
		department = employee.get("department") or (state.get("department") if state else None)
		branch = employee.get("branch") or (state.get("branch") if state else None)

		values = {
			"custodian": custodian or None,
			"current_custodian": custodian or None,
			"custodian_department": department or None,
		}
		if location:
			values["location"] = location
			values["asset_location"] = location
		if department:
			values["department"] = department
		if branch:
			values["branch"] = branch

		frappe.db.set_value("Asset", asset.name, values, update_modified=False)


def _make_mirror_fields_read_only() -> None:
	for fieldname in MIRROR_FIELDS:
		custom_field = frappe.db.get_value(
			"Custom Field",
			{"dt": "Asset", "fieldname": fieldname},
			"name",
		)
		if custom_field:
			frappe.db.set_value(
				"Custom Field",
				custom_field,
				"read_only",
				1,
				update_modified=False,
			)


def _remove_workspace_references() -> None:
	if not frappe.db.exists("Workspace", "NASECO ASSETS"):
		return

	workspace = frappe.get_doc("Workspace", "NASECO ASSETS")
	workspace.set(
		"links",
		[row for row in workspace.links if row.get("link_to") != LEGACY_DOCTYPE],
	)
	workspace.set(
		"shortcuts",
		[row for row in workspace.shortcuts if row.get("link_to") != LEGACY_DOCTYPE],
	)

	if workspace.content:
		content = json.loads(workspace.content)
		workspace.content = json.dumps(
			[
				block
				for block in content
				if block.get("data", {}).get("shortcut_name") != LEGACY_DOCTYPE
			],
			separators=(",", ":"),
		)

	workspace.save(ignore_permissions=True)


def _upsert_asset_movement_permissions() -> None:
	setup_custom_perms(MOVEMENT_DOCTYPE)
	profiles = {
		ROLE_ASSET_ADMINISTRATOR: set(PERMISSION_FIELDS),
		ROLE_FINANCE_MANAGER: set(PERMISSION_FIELDS),
		ROLE_FIXED_ASSET_ACCOUNTANT: {
			"select",
			"read",
			"write",
			"create",
			"submit",
			"cancel",
			"amend",
			"report",
			"export",
			"print",
			"email",
		},
		ROLE_INTERNAL_AUDITOR: {"select", "read", "report", "export", "print"},
		ROLE_EXECUTIVE_VIEWER: {"select", "read", "report", "export", "print"},
	}

	for role, granted in profiles.items():
		values = {fieldname: int(fieldname in granted) for fieldname in PERMISSION_FIELDS}
		existing = frappe.db.get_value(
			"Custom DocPerm",
			{
				"parent": MOVEMENT_DOCTYPE,
				"role": role,
				"permlevel": 0,
				"if_owner": 0,
			},
			"name",
		)
		if existing:
			frappe.db.set_value(
				"Custom DocPerm",
				existing,
				values,
				update_modified=False,
			)
			continue

		frappe.get_doc(
			{
				"doctype": "Custom DocPerm",
				"parent": MOVEMENT_DOCTYPE,
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": role,
				"permlevel": 0,
				"if_owner": 0,
				**values,
			}
		).insert(ignore_permissions=True)


def _delete_legacy_doctype() -> None:
	for workflow_name in frappe.get_all(
		"Workflow",
		filters={"document_type": LEGACY_DOCTYPE},
		pluck="name",
	):
		frappe.delete_doc(
			"Workflow",
			workflow_name,
			force=True,
			ignore_permissions=True,
		)

	if frappe.db.exists("DocType", LEGACY_DOCTYPE):
		frappe.delete_doc(
			"DocType",
			LEGACY_DOCTYPE,
			force=True,
			ignore_permissions=True,
		)


def drop_legacy_table() -> None:
	frappe.db.sql_ddl("DROP TABLE IF EXISTS `tabAsset Custody Assignment`")


def execute() -> None:
	_sync_asset_state()
	_make_mirror_fields_read_only()
	_remove_workspace_references()
	_upsert_asset_movement_permissions()
	_delete_legacy_doctype()
	drop_legacy_table()
	frappe.clear_cache(doctype="Asset")
	frappe.clear_cache(doctype=MOVEMENT_DOCTYPE)
