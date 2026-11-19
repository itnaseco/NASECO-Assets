from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe
from frappe.model.rename_doc import rename_doc

from naseco_assets.naseco_assets.constants import ROLE_GROUP_ACCESS


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"


def _load(name: str) -> Any:
	return json.loads((FIXTURES / name).read_text())


def _upsert_role(role_name: str) -> None:
	if frappe.db.exists("Role", {"role_name": role_name}):
		return
	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": role_name,
			"desk_access": 1,
			"is_custom": 1,
		}
	).insert(ignore_permissions=True)


def _upsert_action(action_name: str) -> None:
	if frappe.db.exists("Workflow Action Master", {"workflow_action_name": action_name}):
		return
	frappe.get_doc(
		{
			"doctype": "Workflow Action Master",
			"workflow_action_name": action_name,
		}
	).insert(ignore_permissions=True)


def _upsert_supplier_group(group_name: str, parent_group: str | None = None) -> None:
	if frappe.db.exists("Supplier Group", group_name):
		return
	doc = {
		"doctype": "Supplier Group",
		"supplier_group_name": group_name,
	}
	if parent_group:
		doc["parent_supplier_group"] = parent_group
	frappe.get_doc(doc).insert(ignore_permissions=True)


def _upsert_workflow_state(state_name: str) -> None:
	if frappe.db.exists("Workflow State", state_name):
		return
	frappe.get_doc(
		{
			"doctype": "Workflow State",
			"workflow_state_name": state_name,
		}
	).insert(ignore_permissions=True)


def _upsert_document(doc: dict[str, Any], doctype: str, unique_field: str) -> None:
	existing = frappe.db.exists(doctype, doc.get(unique_field))
	if existing:
		target = frappe.get_doc(doctype, existing)
		target.update(doc)
		target.save(ignore_permissions=True)
		return
	frappe.get_doc({"doctype": doctype, **doc}).insert(ignore_permissions=True)


def _upsert_workflow(workflow: dict[str, Any]) -> None:
	existing = frappe.db.exists("Workflow", workflow["workflow_name"])
	if existing:
		target = frappe.get_doc("Workflow", existing)
		target.update(workflow)
		target.save(ignore_permissions=True)
		return
	frappe.get_doc({"doctype": "Workflow", **workflow}).insert(ignore_permissions=True)


def _upsert_number_card(card: dict[str, Any]) -> None:
	card = dict(card)
	value_field = card.pop("value_field", None)
	if card.get("type") == "Document Type" and card.get("function") != "Count" and not card.get(
		"aggregate_function_based_on"
	):
		card["aggregate_function_based_on"] = value_field

	existing = frappe.db.exists("Number Card", card["label"])
	if existing:
		target = frappe.get_doc("Number Card", existing)
		target.update(card)
		target.save(ignore_permissions=True)
		return
	frappe.get_doc(card).insert(ignore_permissions=True)


def _upsert_workspace(workspace: dict[str, Any]) -> None:
	existing = frappe.db.exists("Workspace", workspace["name"])
	if existing:
		target = frappe.get_doc("Workspace", existing)
		target.update(workspace)
		target.save(ignore_permissions=True)
		return

	legacy_name = "Fixed Asset Management"
	if legacy_name != workspace["name"] and frappe.db.exists("Workspace", legacy_name):
		rename_doc(
			"Workspace",
			legacy_name,
			workspace["name"],
			force=True,
			merge=False,
			ignore_permissions=True,
			ignore_if_exists=True,
		)
		existing = frappe.db.exists("Workspace", workspace["name"])
		if existing:
			target = frappe.get_doc("Workspace", existing)
			target.update(workspace)
			target.save(ignore_permissions=True)
			return

	frappe.get_doc(workspace).insert(ignore_permissions=True)


def _seed_workflow_states() -> None:
	workflow_states: list[str] = []
	for workflow in _load("workflows.json"):
		for state in workflow.get("states", []):
			workflow_states.append(state["state"])
		for transition in workflow.get("transitions", []):
			workflow_states.append(transition["state"])
			workflow_states.append(transition["next_state"])

	for state_name in dict.fromkeys(workflow_states):
		_upsert_workflow_state(state_name)


def execute() -> None:
	for role_name in ROLE_GROUP_ACCESS:
		_upsert_role(role_name)

	for action_name in _load("workflow_actions.json"):
		_upsert_action(action_name)

	_upsert_supplier_group("Insurance Provider", "All Supplier Groups")

	_seed_workflow_states()

	for workflow in _load("workflows.json"):
		_upsert_workflow(workflow)

	for card in _load("number_cards.json"):
		_upsert_number_card(card)

	_upsert_workspace(_load("workspace.json"))

	if not frappe.db.exists("Location", {"location_name": "Unassigned"}):
		frappe.get_doc(
			{
				"doctype": "Location",
				"location_name": "Unassigned",
				"is_group": 0,
				"is_container": 0,
			}
		).insert(ignore_permissions=True)
