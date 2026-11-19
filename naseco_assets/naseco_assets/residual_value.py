"""Apply category residual policies to ERPNext Asset Finance Books."""

from __future__ import annotations

import frappe
from erpnext.assets.doctype.asset.asset import get_item_details as erpnext_get_item_details
from frappe import _
from frappe.utils import flt

FIXED_AMOUNT = "Fixed Amount"
PERCENTAGE = "Percentage"
MANUAL = "Manual"


def before_validate_asset_category(category, method=None) -> None:
	"""Give each category book an explicit residual policy."""
	amount = flt(category.get("naseco_default_residual_value"))
	if amount < 0:
		frappe.throw(_("Default Residual Value cannot be negative."))

	for row in category.get("finance_books") or []:
		basis = row.get("naseco_residual_value_basis")
		if not basis:
			basis = _infer_category_basis(amount, row)
			row.naseco_residual_value_basis = basis
		if basis not in (FIXED_AMOUNT, PERCENTAGE):
			frappe.throw(_("Row {0}: Select Fixed Amount or Percentage as Residual Value Basis.").format(row.idx))


def apply_asset_residual_defaults(asset) -> None:
	"""Set the schedule's exact residual before ERPNext validates the Asset."""
	if asset.docstatus != 0 or not asset.get("asset_category"):
		return

	category = frappe.get_cached_doc("Asset Category", asset.asset_category)
	if (
		asset.is_new()
		and not asset.get("calculate_depreciation")
		and not (asset.get("asset_type") == "Existing Asset" and asset.get("is_fully_depreciated"))
		and not category.get("naseco_non_depreciable")
		and category.get("finance_books")
	):
		asset.calculate_depreciation = 1
	if not asset.get("calculate_depreciation"):
		return

	if not asset.get("finance_books") and asset.get("item_code"):
		for book in get_item_details(asset.item_code, asset.asset_category, asset.net_purchase_amount):
			asset.append("finance_books", book)

	category_rows = {row.finance_book: row for row in category.get("finance_books") or []}
	for row in asset.get("finance_books") or []:
		basis = row.get("naseco_residual_value_basis")
		if not basis and (asset.is_new() or row.is_new()):
			category_row = category_rows.get(row.finance_book)
			basis = _category_basis(category, category_row)
			row.naseco_residual_value_basis = basis
		if basis == FIXED_AMOUNT:
			row.expected_value_after_useful_life = _fixed_amount(category, asset.net_purchase_amount, row.idx)
		elif basis == PERCENTAGE:
			row.expected_value_after_useful_life = flt(asset.net_purchase_amount) * flt(
				row.salvage_value_percentage
			) / 100
		elif basis and basis != MANUAL:
			frappe.throw(_("Row {0}: Invalid Residual Value Basis.").format(row.idx))


@frappe.whitelist()
def get_item_details(item_code, asset_category, net_purchase_amount):
	"""Return ERPNext category book defaults with the NASECO residual policy."""
	if not isinstance(item_code, str) or not isinstance(asset_category, str):
		frappe.throw(_("Item and Asset Category must be valid links."))

	books = erpnext_get_item_details(item_code, asset_category, net_purchase_amount)
	category = frappe.get_cached_doc("Asset Category", asset_category)
	category_rows = {row.finance_book: row for row in category.get("finance_books") or []}
	for book in books:
		category_row = category_rows.get(book["finance_book"])
		basis = _category_basis(category, category_row)
		book["naseco_residual_value_basis"] = basis
		if basis == FIXED_AMOUNT:
			book["expected_value_after_useful_life"] = flt(category.get("naseco_default_residual_value"))
	return books


def _category_basis(category, row) -> str:
	if row and row.get("naseco_residual_value_basis"):
		return row.naseco_residual_value_basis
	return _infer_category_basis(flt(category.get("naseco_default_residual_value")), row)


def _infer_category_basis(amount: float, row) -> str:
	return FIXED_AMOUNT if amount > 0 and row and not flt(row.salvage_value_percentage) else PERCENTAGE


def _fixed_amount(category, purchase_amount, row_number: int) -> float:
	amount = flt(category.get("naseco_default_residual_value"))
	if amount < 0 or amount >= flt(purchase_amount):
		frappe.throw(
			_("Row {0}: Default Residual Value must be at least zero and below Net Purchase Amount.").format(
				row_number
			)
		)
	return amount
