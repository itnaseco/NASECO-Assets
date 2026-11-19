"""Create reviewable ERPNext drafts from the Employee custody view."""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from erpnext.assets.doctype.asset.asset import make_sales_invoice
from erpnext.assets.doctype.asset.depreciation import (
	get_gl_entries_on_asset_disposal,
	validate_asset_for_scrap,
)

from .lifecycle import _set_asset_sale_values


HR_ROLES = {"HR User", "HR Manager", "System Manager"}
DRAFT_DOCTYPES = ("Sales Invoice", "Journal Entry", "Asset Movement")


def can_prepare_hr_asset_draft() -> bool:
	return bool(HR_ROLES.intersection(frappe.get_roles()))


def _get_custodied_asset(employee: str, asset_name: str):
	if not can_prepare_hr_asset_draft():
		frappe.throw(_("An HR role is required to prepare an asset draft."), frappe.PermissionError)
	frappe.get_doc("Employee", employee).check_permission("read")
	asset = frappe.get_doc("Asset", asset_name)
	if asset.custodian != employee or asset.docstatus != 1 or asset.status in ("Sold", "Scrapped", "Cancelled"):
		frappe.throw(_("This asset is no longer submitted and assigned to this employee."))
	frappe.db.sql("SELECT name FROM `tabAsset` WHERE name = %s FOR UPDATE", asset.name)
	for doctype in DRAFT_DOCTYPES:
		if frappe.db.exists(doctype, {"naseco_hr_asset": asset.name, "docstatus": 0}):
			frappe.throw(_("A draft action already exists for asset {0}. Ask Finance to review it first.").format(asset.name))
	for child_doctype, parent_doctype, filters in (
		("Sales Invoice Item", "Sales Invoice", {"asset": asset.name}),
		("Journal Entry Account", "Journal Entry", {"reference_type": "Asset", "reference_name": asset.name}),
		("Asset Movement Item", "Asset Movement", {"asset": asset.name}),
	):
		parents = frappe.get_all(child_doctype, filters=filters, pluck="parent")
		if parents and frappe.db.exists(parent_doctype, {"name": ["in", parents], "docstatus": 0}):
			frappe.throw(_("A draft transaction already references asset {0}. Ask Finance to review it first.").format(asset.name))
	return asset


def _mark_hr_draft(doc, asset, employee: str, reason: str):
	doc.naseco_hr_asset = asset.name
	doc.naseco_hr_employee = employee
	doc.naseco_hr_reason = reason.strip()
	doc.insert(ignore_permissions=True)
	return {"doctype": doc.doctype, "name": doc.name}


@frappe.whitelist(methods=["POST"])
def prepare_asset_sale(employee: str, asset_name: str, buyer_type: str, customer: str | None = None,
	posting_date: str | None = None, selling_price: float | None = None, reason: str = "") -> dict:
	asset = _get_custodied_asset(employee, asset_name)
	if buyer_type == "Employee":
		customer = frappe.db.get_value("Employee", employee, "naseco_asset_sale_customer")
		if not customer:
			frappe.throw(_("Set Sales Invoice Customer on this Employee before preparing a sale."))
	elif buyer_type != "Customer":
		frappe.throw(_("Choose Employee or Customer as buyer."))
	if not customer or not frappe.db.exists("Customer", customer):
		frappe.throw(_("Select a valid Customer."))
	date = getdate(posting_date or nowdate())
	if date > getdate():
		frappe.throw(_("Sale date cannot be in the future."))
	quantity = cint(asset.asset_quantity or 1)
	invoice = make_sales_invoice(asset.name, asset.item_code, asset.company, quantity, asset.serial_no)
	invoice.customer = customer
	invoice.posting_date = date
	invoice.set_posting_time = 1
	if buyer_type == "Employee":
		invoice.naseco_asset_sale_employee = employee
	invoice.set_missing_values()
	_set_asset_sale_values(invoice, asset, quantity, None if selling_price in (None, "") else flt(selling_price), str(date), None)
	return _mark_hr_draft(invoice, asset, employee, reason)


@frappe.whitelist(methods=["POST"])
def prepare_asset_return(employee: str, asset_name: str, target_location: str,
	transaction_date: str | None = None, reason: str = "") -> dict:
	asset = _get_custodied_asset(employee, asset_name)
	if not target_location or not frappe.db.exists("Location", target_location):
		frappe.throw(_("Select a valid return location."))
	date = getdate(transaction_date or nowdate())
	if date > getdate():
		frappe.throw(_("Return date cannot be in the future."))
	movement = frappe.new_doc("Asset Movement")
	movement.company = asset.company
	movement.purpose = "Receipt"
	movement.transaction_date = date
	movement.append("assets", {"asset": asset.name, "source_location": asset.location,
		"from_employee": employee, "target_location": target_location})
	return _mark_hr_draft(movement, asset, employee, reason)


def _disposal_entries(asset, date):
	entries = get_gl_entries_on_asset_disposal(asset, date=date)
	for entry in entries:
		entry.update({"reference_type": "Asset", "reference_name": asset.name})
	return entries


@frappe.whitelist(methods=["POST"])
def prepare_asset_scrap(employee: str, asset_name: str, reason: str,
	posting_date: str | None = None) -> dict:
	asset = _get_custodied_asset(employee, asset_name)
	if not reason or not reason.strip():
		frappe.throw(_("A scrap reason is required."))
	date = getdate(posting_date or nowdate())
	validate_asset_for_scrap(asset, date)
	journal = frappe.new_doc("Journal Entry")
	journal.voucher_type = "Asset Disposal"
	journal.naming_series = frappe.get_cached_value("Company", asset.company, "series_for_depreciation_entry")
	journal.company = asset.company
	journal.posting_date = date
	journal.user_remark = _("HR requested scrap of Asset {0}: {1}").format(asset.name, reason.strip())
	for entry in _disposal_entries(asset, date):
		journal.append("accounts", entry)
	return _mark_hr_draft(journal, asset, employee, reason)


def validate_hr_scrap_before_submit(doc, method=None):
	if not doc.get("naseco_hr_asset"):
		return
	if doc.voucher_type != "Asset Disposal":
		frappe.throw(_("HR asset draft must remain an Asset Disposal journal entry."))
	asset = frappe.get_doc("Asset", doc.naseco_hr_asset)
	validate_asset_for_scrap(asset, getdate(doc.posting_date))
	if frappe.db.sql("""
		SELECT 1 FROM `tabAsset Depreciation Schedule` ads
		JOIN `tabDepreciation Schedule` ds ON ds.parent = ads.name
		WHERE ads.asset = %s AND ads.docstatus = 1 AND ds.schedule_date <= %s
		AND IFNULL(ds.journal_entry, '') = '' LIMIT 1
	""", (asset.name, doc.posting_date)):
		frappe.throw(_("Post all depreciation due through the disposal date before submitting this draft."))
	expected = _disposal_entries(asset, getdate(doc.posting_date))
	actual = doc.get("accounts") or []
	if len(actual) != len(expected) or any(
		row.account != entry.get("account")
		or abs(flt(row.debit) - flt(entry.get("debit"))) > 0.01
		or abs(flt(row.credit) - flt(entry.get("credit"))) > 0.01
		for row, entry in zip(actual, expected)
	):
		frappe.throw(_("Asset value changed after this scrap draft was created. Recreate the draft with current values."))
