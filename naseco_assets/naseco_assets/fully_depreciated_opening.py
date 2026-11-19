"""Opening values for assets already fully depreciated before import."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from .residual_value import FIXED_AMOUNT, PERCENTAGE, _category_basis

CATEGORY_DEFAULT = "Category Default"
MANUAL_OVERRIDE = "Manual Override"


def prepare_fully_depreciated_opening(asset) -> None:
	"""Calculate opening depreciation on drafts without posting past expenses."""
	if asset.docstatus != 0 or asset.get("asset_type") != "Existing Asset" or not asset.get("is_fully_depreciated"):
		return

	asset.calculate_depreciation = 0
	cost = _total_cost(asset)
	source = asset.get("naseco_opening_residual_source") or CATEGORY_DEFAULT
	if source not in (CATEGORY_DEFAULT, MANUAL_OVERRIDE):
		frappe.throw(_("Choose Category Default or Manual Override as Opening Residual Source."))

	if source == CATEGORY_DEFAULT:
		if flt(asset.get("additional_asset_cost")):
			frappe.throw(_("Assets with Additional Asset Cost require a reviewed Manual Override for opening depreciation."))
		choice = _selected_category_choice(asset, cost)
		residual = flt(choice["residual"], asset.precision("net_purchase_amount"))
		if not asset.get("naseco_opening_residual_source") and flt(asset.get("opening_accumulated_depreciation")):
			provided = flt(asset.opening_accumulated_depreciation, asset.precision("net_purchase_amount"))
			if provided != flt(cost - residual, asset.precision("net_purchase_amount")):
				frappe.throw(_("Existing Opening Accumulated Depreciation differs from the category calculation. Choose Manual Override to retain the approved amount."))
		asset.naseco_opening_finance_book = choice["finance_book"]
	else:
		asset.naseco_opening_finance_book = _selected_category_choice(asset, cost)["finance_book"]
		if not asset.get("naseco_opening_override_reason"):
			frappe.throw(_("Enter Residual Value Override Reason for a manual opening residual."))
		entered = asset.get("naseco_opening_residual_value")
		residual = (
			cost - flt(asset.opening_accumulated_depreciation)
			if entered in (None, "") and asset.get("opening_accumulated_depreciation")
			else flt(entered)
		)

	residual = flt(residual, asset.precision("net_purchase_amount"))
	if cost <= 0 or residual < 0 or residual >= cost:
		frappe.throw(_("Opening Residual Value must be at least zero and below total Asset cost."))

	asset.naseco_opening_residual_source = source
	asset.naseco_opening_residual_value = residual
	asset.opening_accumulated_depreciation = flt(
		cost - residual, asset.precision("opening_accumulated_depreciation")
	)
	asset.set("finance_books", [])


def remove_unused_draft_schedules(asset) -> None:
	"""Discard schedules left by a draft that switched to opening balances."""
	if asset.docstatus != 0 or asset.get("calculate_depreciation") or not asset.get("is_fully_depreciated"):
		return

	for schedule in frappe.get_all(
		"Asset Depreciation Schedule",
		filters={"asset": asset.name, "docstatus": 0},
		pluck="name",
	):
		if frappe.db.exists("Depreciation Schedule", {"parent": schedule, "journal_entry": ["is", "set"]}):
			frappe.throw(_("Draft depreciation schedule {0} has a Journal Entry and cannot be removed automatically.").format(schedule))
		frappe.delete_doc("Asset Depreciation Schedule", schedule, ignore_permissions=True)


@frappe.whitelist()
def get_category_residual_choices(asset_category: str, net_purchase_amount: float):
	"""Preview the residual policies available for an Existing Asset."""
	if not isinstance(asset_category, str) or not asset_category:
		frappe.throw(_("Select an Asset Category first."))
	if not frappe.has_permission("Asset", "create") and not frappe.has_permission("Asset", "write"):
		frappe.throw(_("You do not have permission to prepare an Asset."), frappe.PermissionError)

	cost = flt(net_purchase_amount)
	if cost <= 0:
		frappe.throw(_("Enter Net Purchase Amount before importing a fully depreciated Asset."))
	category = frappe.get_cached_doc("Asset Category", asset_category)
	return _category_choices(category, cost)


def _selected_category_choice(asset, cost: float) -> dict:
	if not asset.get("asset_category"):
		frappe.throw(_("Select an Asset Category before calculating opening depreciation."))
	category = frappe.get_cached_doc("Asset Category", asset.asset_category)
	choices = _category_choices(category, cost)
	if not choices:
		frappe.throw(_("Asset Category {0} needs a Finance Book residual policy.").format(asset.asset_category))
	selected = asset.get("naseco_opening_finance_book")
	if len(choices) == 1:
		return choices[0]
	for choice in choices:
		if choice["finance_book"] == selected:
			return choice
	frappe.throw(_("Select an Opening Finance Book for this Asset Category."))


def _category_choices(category, cost: float) -> list[dict]:
	choices = []
	for row in category.get("finance_books") or []:
		basis = _category_basis(category, row)
		if basis == FIXED_AMOUNT:
			residual = flt(category.get("naseco_default_residual_value"))
		elif basis == PERCENTAGE:
			residual = cost * flt(row.salvage_value_percentage) / 100
		else:
			continue
		choices.append({"finance_book": row.finance_book, "basis": basis, "residual": residual})
	return choices


def _total_cost(asset) -> float:
	return flt(asset.get("net_purchase_amount")) + flt(asset.get("additional_asset_cost"))
