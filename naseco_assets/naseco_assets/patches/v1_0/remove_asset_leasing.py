from __future__ import annotations

import json

import frappe

from naseco_assets.naseco_assets.constants import (
	ASSET_BUSINESS_CLASSES,
	FUNDING_SOURCE_OPTIONS,
)


LEASE_DOCTYPE = "Fixed Asset Lease Contract"
LEASE_REPORT = "Lease Expiry Report"
LEASE_WORKFLOW = "Fixed Asset Lease Contract Workflow"
LEASE_BUSINESS_CLASSES = ("Leasehold Improvements", "Right-of-Use Asset")


def _normalize_lease_classifications() -> None:
	frappe.db.sql(
		"""
		UPDATE `tabAsset`
		SET asset_business_class = NULL
		WHERE asset_business_class IN %s
		""",
		(LEASE_BUSINESS_CLASSES,),
	)
	frappe.db.sql(
		"""
		UPDATE `tabAsset`
		SET funding_source = NULL
		WHERE funding_source = 'Lease Funded'
		"""
	)
	frappe.db.sql(
		"""
		UPDATE `tabAsset Category`
		SET naseco_asset_business_class = NULL
		WHERE naseco_asset_business_class IN %s
		""",
		(LEASE_BUSINESS_CLASSES,),
	)
	frappe.db.sql(
		"""
		UPDATE `tabFixed Asset Request`
		SET asset_business_class = NULL
		WHERE asset_business_class IN %s
		""",
		(LEASE_BUSINESS_CLASSES,),
	)


def _update_select_options() -> None:
	field_options = {
		("Asset", "asset_business_class"): "\n".join(ASSET_BUSINESS_CLASSES),
		("Asset Category", "naseco_asset_business_class"): "\n".join(
			ASSET_BUSINESS_CLASSES
		),
		("Asset", "funding_source"): "\n".join(FUNDING_SOURCE_OPTIONS),
	}
	for (doctype, fieldname), options in field_options.items():
		custom_field = frappe.db.get_value(
			"Custom Field",
			{"dt": doctype, "fieldname": fieldname},
			"name",
		)
		if custom_field:
			frappe.db.set_value(
				"Custom Field",
				custom_field,
				"options",
				options,
				update_modified=False,
			)


def _remove_workspace_references() -> None:
	if not frappe.db.exists("Workspace", "NASECO ASSETS"):
		return

	workspace = frappe.get_doc("Workspace", "NASECO ASSETS")
	removed_names = {LEASE_DOCTYPE, LEASE_REPORT}
	workspace.set(
		"links",
		[row for row in workspace.links if row.get("link_to") not in removed_names],
	)
	workspace.set(
		"shortcuts",
		[row for row in workspace.shortcuts if row.get("link_to") not in removed_names],
	)

	if workspace.content:
		content = json.loads(workspace.content)
		workspace.content = json.dumps(
			[
				block
				for block in content
				if block.get("data", {}).get("shortcut_name") not in removed_names
			],
			separators=(",", ":"),
		)

	workspace.save(ignore_permissions=True)


def _delete_metadata() -> None:
	if frappe.db.exists("Report", LEASE_REPORT):
		frappe.delete_doc(
			"Report",
			LEASE_REPORT,
			force=True,
			ignore_permissions=True,
		)

	workflow_names = set(
		frappe.get_all(
			"Workflow",
			filters={"document_type": LEASE_DOCTYPE},
			pluck="name",
		)
	)
	workflow_names.add(LEASE_WORKFLOW)
	for workflow_name in workflow_names:
		if frappe.db.exists("Workflow", workflow_name):
			frappe.delete_doc(
				"Workflow",
				workflow_name,
				force=True,
				ignore_permissions=True,
			)

	if frappe.db.exists("DocType", LEASE_DOCTYPE):
		frappe.delete_doc(
			"DocType",
			LEASE_DOCTYPE,
			force=True,
			ignore_permissions=True,
		)

	for action_name in ("Activate", "Terminate"):
		action = frappe.db.get_value(
			"Workflow Action Master",
			{"workflow_action_name": action_name},
			"name",
		)
		if action and not frappe.db.exists(
			"Workflow Transition",
			{"action": action_name},
		):
			frappe.delete_doc(
				"Workflow Action Master",
				action,
				force=True,
				ignore_permissions=True,
			)


def drop_legacy_table() -> None:
	frappe.db.sql_ddl("DROP TABLE IF EXISTS `tabFixed Asset Lease Contract`")


def execute() -> None:
	_normalize_lease_classifications()
	_update_select_options()
	_remove_workspace_references()
	_delete_metadata()
	drop_legacy_table()
	frappe.clear_cache(doctype="Asset")
	frappe.clear_cache(doctype="Asset Category")
	frappe.clear_cache(doctype="Fixed Asset Request")
