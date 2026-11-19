from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.assets.doctype.asset.depreciation import get_value_after_depreciation_on_disposal_date

from .lifecycle import (
	create_material_request_from_request,
	create_sales_invoice_for_asset_sale,
	find_matching_capex_plan,
	get_asset_sale_details,
	refresh_capex_plan_totals,
)


@frappe.whitelist()
def get_employee_custodied_assets(employee: str) -> dict:
	if not employee or not frappe.db.exists("Employee", employee):
		frappe.throw(_("A valid Employee is required."))

	frappe.get_doc("Employee", employee).check_permission("read")
	from .hr_asset_actions import can_prepare_hr_asset_draft

	can_read_assets = frappe.has_permission("Asset", ptype="read")
	can_prepare_drafts = can_prepare_hr_asset_draft()
	if not can_read_assets and not can_prepare_drafts:
		return {"assets": [], "can_read_assets": False}

	list_assets = frappe.get_list if can_read_assets else frappe.get_all
	assets = list_assets(
		"Asset",
		filters={
			"custodian": employee,
			"docstatus": ["<", 2],
		},
		fields=[
			"name",
			"asset_name",
			"asset_category",
			"status",
			"docstatus",
			"company",
			"calculate_depreciation",
			"total_asset_cost",
			"value_after_depreciation",
		],
		order_by="asset_category asc, asset_name asc",
		limit_page_length=500,
	)
	if can_prepare_drafts and assets:
		asset_names = [asset.name for asset in assets]
		pending_assets = set()
		for doctype in ("Sales Invoice", "Journal Entry", "Asset Movement"):
			pending_assets.update(
				row.naseco_hr_asset
				for row in frappe.get_all(
					doctype,
					filters={"naseco_hr_asset": ["in", asset_names], "docstatus": 0},
					fields=["naseco_hr_asset"],
				)
			)
		for asset in assets:
			asset.pending_hr_draft = asset.name in pending_assets
	finance_book_values = {}
	if assets:
		for finance_book in frappe.get_all(
			"Asset Finance Book",
			filters={
				"parent": ["in", [asset.name for asset in assets]],
				"parenttype": "Asset",
			},
			fields=["parent", "value_after_depreciation"],
			order_by="parent asc, idx asc",
		):
			finance_book_values.setdefault(finance_book.parent, finance_book)

	companies = {asset.company for asset in assets if asset.company}
	company_currencies = {
		company.name: company.default_currency
		for company in frappe.get_all(
			"Company",
			filters={"name": ["in", companies]},
			fields=["name", "default_currency"],
		)
	}

	for asset in assets:
		finance_book = finance_book_values.get(asset.name)
		book_value = finance_book.value_after_depreciation if finance_book and asset.calculate_depreciation else None
		if book_value is None:
			book_value = asset.value_after_depreciation
		if book_value is None:
			book_value = asset.total_asset_cost

		asset.value_after_depreciation = book_value
		asset.purchase_cost = asset.total_asset_cost
		asset.currency = company_currencies.get(asset.company)
		asset.pop("calculate_depreciation", None)
		asset.pop("total_asset_cost", None)
		asset.pop("company", None)

	return {
		"assets": assets,
		"asset_sales": _get_employee_asset_sales(employee),
		"can_read_assets": True,
		"can_read_asset_links": can_read_assets,
		"can_prepare_drafts": can_prepare_drafts,
	}


def _get_employee_asset_sales(employee: str) -> list[dict]:
	if not frappe.has_permission("Sales Invoice", ptype="read"):
		return []

	invoices = frappe.get_list(
		"Sales Invoice",
		filters={"naseco_asset_sale_employee": employee, "docstatus": 1},
		fields=["name", "posting_date", "status", "currency"],
		order_by="posting_date desc, creation desc",
		limit_page_length=500,
	)
	if not invoices:
		return []

	invoice_by_name = {invoice.name: invoice for invoice in invoices}
	items = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": ["in", list(invoice_by_name)], "asset": ["is", "set"]},
		fields=["parent", "asset", "item_name", "amount", "naseco_asset_net_book_value"],
		order_by="parent asc, idx asc",
	)

	asset_sales = []
	for item in items:
		invoice = invoice_by_name[item.parent]
		net_book_value = item.naseco_asset_net_book_value
		if net_book_value is None:
			net_book_value = _get_historical_asset_book_value(item.asset, invoice.posting_date)
		asset_sales.append(
			{
				"asset": item.asset,
				"asset_name": item.item_name,
				"posting_date": invoice.posting_date,
				"sales_invoice": invoice.name,
				"invoice_status": invoice.status,
				"currency": invoice.currency,
				"net_book_value": net_book_value,
				"selling_price": item.amount,
				"gain_loss": flt(item.amount) - flt(net_book_value),
			}
		)
	return asset_sales


def _get_historical_asset_book_value(asset_name: str, posting_date: str) -> float | None:
	try:
		return get_value_after_depreciation_on_disposal_date(asset_name, str(posting_date))
	except frappe.ValidationError:
		return None


@frappe.whitelist()
def create_material_request(request_name: str) -> dict[str, str]:
	return {"name": create_material_request_from_request(request_name)}


@frappe.whitelist()
def refresh_capex_plan(capex_plan_name: str) -> dict[str, str]:
	refresh_capex_plan_totals(capex_plan_name)
	return {"name": capex_plan_name}


@frappe.whitelist()
def find_capex_plan(
	company: str | None = None,
	fiscal_year: str | None = None,
	cost_center: str | None = None,
	asset_category: str | None = None,
) -> dict[str, str | None]:
	plan_name = find_matching_capex_plan(company, fiscal_year, cost_center, asset_category)
	if not plan_name:
		return {"name": None}
	return {"name": plan_name}


@frappe.whitelist(methods=["GET"])
def get_asset_sale_summary(
	asset_name: str,
	posting_date: str | None = None,
	finance_book: str | None = None,
	sell_qty: int | None = None,
) -> dict:
	return get_asset_sale_details(asset_name, posting_date, finance_book, sell_qty)


@frappe.whitelist(methods=["POST"])
def make_sales_invoice_for_asset_sale(
	asset: str | None = None,
	item_code: str | None = None,
	company: str | None = None,
	serial_no: str | None = None,
	sell_qty: int | None = None,
	asset_name: str | None = None,
	posting_date: str | None = None,
	finance_book: str | None = None,
	selling_price: float | None = None,
	customer: str | None = None,
	employee: str | None = None,
):
	asset_identifier = asset_name or asset
	if not asset_identifier:
		frappe.throw(_("Asset is required to create a Sales Invoice."))

	return create_sales_invoice_for_asset_sale(
		asset_identifier,
		posting_date=posting_date,
		item_code=item_code,
		company=company,
		serial_no=serial_no,
		sell_qty=sell_qty,
		finance_book=finance_book,
		selling_price=selling_price,
		customer=customer,
		employee=employee,
	)
