from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, getdate, nowdate

from .constants import (
	ASSET_BUSINESS_CLASSES,
	ASSET_CONDITION_STATUS_OPTIONS,
	ASSET_OPERATIONAL_STATUS_OPTIONS,
	CAPEX_PLAN_STATUS_OPTIONS,
	CAPITALIZATION_STATUS_OPTIONS,
	CIP_STATUS_OPTIONS,
	CLAIM_STATUS_OPTIONS,
	DEFAULT_LOCATION_NAME,
	DEPRECIATION_DEFAULTS,
	INSURANCE_COVERAGE_BASIS_OPTIONS,
	MAINTENANCE_FREQUENCY_OPTIONS,
	MAINTENANCE_STATUS_OPTIONS,
	NON_DEPRECIABLE_BUSINESS_CLASSES,
	POLICY_APPROVAL_STATUS_OPTIONS,
	REQUEST_APPROVAL_STATUS_OPTIONS,
	ROLE_ASSET_ADMINISTRATOR,
	ROLE_FINANCE_MANAGER,
	ROLE_FIXED_ASSET_ACCOUNTANT,
	ROLE_INTERNAL_AUDITOR,
	ROLE_PROCUREMENT_MANAGER,
	ROLE_DEPARTMENT_MANAGER,
	ROLE_EXECUTIVE_VIEWER,
	USAGE_READING_TYPES,
)
from .utils import (
	add_days_to_today,
	as_date,
	as_float,
	calculate_budget_utilization,
	calculate_remaining_budget,
	get_asset_category_defaults,
	get_cost_center_company,
	get_default_location_name,
	get_current_fiscal_year,
	get_employee_company,
	get_employee_department,
	get_fixed_asset_item,
	has_role,
	send_role_mail,
	safe_set,
	today,
	user_has_finance_override,
)

from .insurance import sync_assets_for_insurance_policy


def _first_non_empty(*values: Any) -> Any:
	for value in values:
		if value not in (None, "", []):
			return value
	return None


def _get_doc_before_save(doc: Document) -> Document | None:
	get_before_save = getattr(doc, "get_doc_before_save", None)
	if callable(get_before_save):
		return get_before_save()
	return None


def _scrub_code(value: str | None) -> str:
	if not value:
		return ""
	return frappe.scrub(value).replace("_", "-").upper()


def _asset_code_format(doc: Document) -> str:
	parts = [
		_scrub_code(doc.get("branch")),
		_scrub_code(doc.get("asset_category")),
		_scrub_code(doc.get("internal_tag_number")),
	]
	if not any(parts):
		return doc.name or ""
	return "-".join(part for part in parts if part)


def _sync_asset_link_fields(asset: Document) -> None:
	safe_set(asset, "asset_location", asset.get("location"))
	safe_set(asset, "current_custodian", asset.get("custodian"))

	if not asset.get("custodian"):
		safe_set(asset, "custodian_department", None)
		return

	employee = frappe.db.get_value(
		"Employee",
		asset.get("custodian"),
		["department", "branch"],
		as_dict=True,
	)
	if not employee:
		safe_set(asset, "custodian_department", None)
		return

	safe_set(asset, "custodian_department", employee.department)
	if employee.department:
		safe_set(asset, "department", employee.department)
	if employee.branch:
		safe_set(asset, "branch", employee.branch)


def _apply_asset_category_defaults(asset: Document) -> None:
	defaults = get_asset_category_defaults(asset.get("asset_category"))
	if not defaults:
		return

	safe_set(asset, "asset_business_class", _first_non_empty(asset.get("asset_business_class"), defaults.get("naseco_asset_business_class")))
	if defaults.get("naseco_non_depreciable"):
		safe_set(asset, "calculate_depreciation", 0)
		return

	# ERPNext v16 builds schedules from finance-book rows, not the legacy
	# depreciation fields on the Asset header.
	if (
		asset.is_new()
		and not asset.get("calculate_depreciation")
		and not (asset.get("asset_type") == "Existing Asset" and asset.get("is_fully_depreciated"))
	):
		category = frappe.get_cached_doc("Asset Category", asset.asset_category)
		if category.get("finance_books"):
			asset.calculate_depreciation = 1


def _validate_depreciation_policy(asset: Document) -> None:
	defaults = get_asset_category_defaults(asset.get("asset_category"))
	if not defaults:
		return
	if asset.docstatus == 0 and asset.get("calculate_depreciation") and not asset.get("finance_books"):
		frappe.throw(
			_("Add a Finance Book depreciation rule to Asset Category {0} or to this Asset before saving.").format(
				frappe.bold(asset.asset_category)
			)
		)

	if defaults.get("naseco_non_depreciable") and asset.get("calculate_depreciation"):
		frappe.throw(_("Asset Category {0} is marked as non-depreciable.").format(asset.asset_category))

	if not user_has_finance_override():
		before_save = _get_doc_before_save(asset)
		if before_save and before_save.docstatus == 1:
			changed_fields = {
				"depreciation_method",
				"total_number_of_depreciations",
				"value_after_depreciation",
				"calculate_depreciation",
			}
			for fieldname in changed_fields:
				if before_save.get(fieldname) != asset.get(fieldname):
					reason_field = "useful_life_override_reason" if fieldname == "total_number_of_depreciations" else "residual_value_override_reason"
					if fieldname == "calculate_depreciation":
						reason_field = "useful_life_override_reason"
					if not asset.get(reason_field):
						frappe.throw(
							_("Finance Manager approval and an override reason are required to change {0} after capitalization.").format(
								frappe.bold(fieldname.replace("_", " "))
							)
						)


def validate_asset(doc: Document) -> None:
	_sync_asset_link_fields(doc)
	_apply_asset_category_defaults(doc)
	safe_set(doc, "asset_code_format", _asset_code_format(doc))
	if doc.get("available_for_use_date") and not doc.get("depreciation_start_date"):
		safe_set(doc, "depreciation_start_date", doc.get("available_for_use_date"))
	if doc.get("capex_plan") or doc.get("asset_request"):
		_validate_capex_plan_budget(doc, _capex_doc_amount(doc))
	_validate_depreciation_policy(doc)


def before_submit_asset(doc: Document) -> None:
	if doc.get("calculate_depreciation") and not doc.get("available_for_use_date"):
		frappe.throw(_("Available-for-use Date is required before submitting a depreciating asset."))
	safe_set(doc, "depreciation_start_date", _first_non_empty(doc.get("depreciation_start_date"), doc.get("available_for_use_date")))
	if doc.get("capitalization_status") in (None, "Pending", "On Hold"):
		safe_set(doc, "capitalization_status", "Capitalized")
	if doc.get("operational_status") in (None, "", "Inactive"):
		safe_set(doc, "operational_status", "Active")
	if not doc.get("status") or doc.get("status") in {"Draft", "Work In Progress"}:
		safe_set(doc, "status", "Capitalized")


def on_submit_asset(doc: Document) -> None:
	if doc.get("capex_plan") or doc.get("asset_request"):
		_refresh_linked_capex_plans(doc)


def on_cancel_asset(doc: Document) -> None:
	if doc.get("capex_plan") or doc.get("asset_request"):
		_refresh_linked_capex_plans(doc)


def on_update_after_submit_asset(doc: Document) -> None:
	if doc.get("capex_plan") or doc.get("asset_request"):
		_refresh_linked_capex_plans(doc)


def _resolve_capex_company(doc: Document) -> str | None:
	return _first_non_empty(
		doc.get("company"),
		get_cost_center_company(doc.get("cost_center")),
		get_employee_company(doc.get("requesting_employee")),
		frappe.defaults.get_user_default("Company"),
	)


def _resolve_capex_fiscal_year(doc: Document, company: str | None = None) -> str | None:
	return _first_non_empty(doc.get("fiscal_year"), get_current_fiscal_year(company))


def _capex_asset_category(doc: Document) -> str | None:
	return _first_non_empty(doc.get("asset_category"), doc.get("fixed_asset_category"))


def _capex_doc_amount(doc: Document) -> float:
	if doc.doctype == "Fixed Asset Request":
		return flt(doc.get("estimated_total_cost") or 0)
	if doc.doctype == "Material Request":
		request_name = doc.get("asset_request")
		if request_name and frappe.db.exists("Fixed Asset Request", request_name):
			return flt(frappe.db.get_value("Fixed Asset Request", request_name, "estimated_total_cost") or 0)
		return 0.0
	if doc.doctype in {"Purchase Order", "Purchase Receipt", "Purchase Invoice"}:
		return flt(doc.get("base_grand_total") or doc.get("grand_total") or doc.get("base_total") or doc.get("total") or 0)
	if doc.doctype == "Asset":
		if doc.get("purchase_invoice"):
			return 0.0
		return flt(doc.get("total_asset_cost") or 0)
	return 0.0


def _capex_plan_filters(doc: Document) -> dict[str, Any] | None:
	company = _resolve_capex_company(doc)
	fiscal_year = _resolve_capex_fiscal_year(doc, company)
	cost_center = doc.get("cost_center")
	asset_category = _capex_asset_category(doc)
	if not all([company, fiscal_year, cost_center, asset_category]):
		return None
	return {
		"company": company,
		"fiscal_year": fiscal_year,
		"cost_center": cost_center,
		"asset_category": asset_category,
		"docstatus": ["<", 2],
		"status": ["in", ["Approved", "Frozen"]],
	}


def _find_matching_capex_plan(doc: Document) -> str | None:
	filters = _capex_plan_filters(doc)
	if not filters:
		return None

	plans = frappe.get_all("Fixed Asset CAPEX Plan", filters=filters, fields=["name"], limit=2)
	if not plans:
		return None
	if len(plans) > 1:
		frappe.throw(
			_(
				"More than one approved CAPEX plan matches company {0}, fiscal year {1}, cost center {2} and asset category {3}."
			).format(filters["company"], filters["fiscal_year"], filters["cost_center"], filters["asset_category"])
		)
	return plans[0].name


def find_matching_capex_plan(
	company: str | None,
	fiscal_year: str | None,
	cost_center: str | None,
	asset_category: str | None,
) -> str | None:
	return _find_matching_capex_plan(
		frappe._dict(
			{
				"company": company,
				"fiscal_year": fiscal_year,
				"cost_center": cost_center,
				"asset_category": asset_category,
			}
		)
	)


def _capex_plan_doc(plan_name: str | None) -> Document | None:
	if not plan_name:
		return None
	if not frappe.db.exists("Fixed Asset CAPEX Plan", plan_name):
		return None
	return frappe.get_doc("Fixed Asset CAPEX Plan", plan_name)


def _sync_capex_plan_context(doc: Document, plan: Document | None) -> None:
	if not plan:
		return

	safe_set(doc, "company", _first_non_empty(doc.get("company"), plan.get("company")))
	safe_set(doc, "fiscal_year", _first_non_empty(doc.get("fiscal_year"), plan.get("fiscal_year")))
	safe_set(doc, "cost_center", _first_non_empty(doc.get("cost_center"), plan.get("cost_center")))
	safe_set(doc, "asset_category", _first_non_empty(doc.get("asset_category"), plan.get("asset_category")))


def _validate_capex_alignment(doc: Document, plan: Document) -> None:
	mismatch_messages: list[str] = []
	for fieldname, label in [
		("company", _("Company")),
		("fiscal_year", _("Fiscal Year")),
		("cost_center", _("Cost Center")),
		("asset_category", _("Asset Category")),
	]:
		doc_value = doc.get(fieldname)
		plan_value = plan.get(fieldname)
		if doc_value and plan_value and doc_value != plan_value:
			mismatch_messages.append(f"{label}: {doc_value} ≠ {plan_value}")
	if mismatch_messages:
		frappe.throw(_("CAPEX document does not match the selected plan: {0}").format("; ".join(mismatch_messages)))


def _capex_plan_source_status(doc: Document) -> str:
	before_save = _get_doc_before_save(doc)
	if before_save and before_save.get("status"):
		return before_save.get("status")
	return doc.get("status") or "Draft"


def _capex_plan_editable_fields(status: str) -> set[str]:
	if status in {"Draft", "Returned for Revision"}:
		return {
			"company",
			"fiscal_year",
			"department",
			"branch",
			"cost_center",
			"asset_category",
			"forecast_amount",
			"notes",
		}
	if status == "Pending Review":
		return {"approved_budget"}
	return set()


def _validate_capex_plan_status_transition(doc: Document) -> None:
	before_save = _get_doc_before_save(doc)
	if not before_save:
		if doc.get("status") not in {None, "", "Draft"} and not has_role("System Manager"):
			frappe.throw(_("New CAPEX plans must start in Draft state."))
		return

	previous_status = before_save.get("status") or "Draft"
	current_status = doc.get("status") or previous_status
	if previous_status == current_status or has_role("System Manager"):
		return

	allowed_transitions = {
		"Draft": {"Pending Review"},
		"Pending Review": {"Approved", "Returned for Revision"},
		"Returned for Revision": {"Pending Review"},
		"Approved": {"Frozen", "Returned for Revision"},
		"Frozen": {"Closed", "Returned for Revision"},
		"Closed": set(),
	}
	allowed_roles = {
		("Draft", "Pending Review"): {ROLE_ASSET_ADMINISTRATOR},
		("Pending Review", "Approved"): {ROLE_FINANCE_MANAGER},
		("Pending Review", "Returned for Revision"): {ROLE_FINANCE_MANAGER},
		("Returned for Revision", "Pending Review"): {ROLE_ASSET_ADMINISTRATOR},
		("Approved", "Frozen"): {ROLE_FINANCE_MANAGER},
		("Approved", "Returned for Revision"): {ROLE_FINANCE_MANAGER},
		("Frozen", "Closed"): {ROLE_FINANCE_MANAGER},
		("Frozen", "Returned for Revision"): {ROLE_FINANCE_MANAGER},
	}

	if current_status not in allowed_transitions.get(previous_status, set()):
		frappe.throw(
			_("CAPEX Plan status cannot change from {0} to {1} directly. Use the workflow actions.").format(
				previous_status, current_status
			)
		)

	roles = allowed_roles.get((previous_status, current_status), set())
	if roles and not any(has_role(role) for role in roles):
		frappe.throw(
			_("You are not allowed to move CAPEX Plan from {0} to {1}.").format(previous_status, current_status)
		)


def _validate_capex_plan_field_locking(doc: Document) -> None:
	before_save = _get_doc_before_save(doc)
	if not before_save or has_role("System Manager"):
		return

	source_status = _capex_plan_source_status(doc)
	tracked_fields = {
		"company",
		"fiscal_year",
		"department",
		"branch",
		"cost_center",
		"asset_category",
		"approved_budget",
		"forecast_amount",
		"notes",
	}
	allowed_role = {
		"Draft": ROLE_ASSET_ADMINISTRATOR,
		"Pending Review": ROLE_FINANCE_MANAGER,
		"Returned for Revision": ROLE_ASSET_ADMINISTRATOR,
		"Approved": ROLE_FINANCE_MANAGER,
		"Frozen": ROLE_FINANCE_MANAGER,
		"Closed": ROLE_FINANCE_MANAGER,
	}.get(source_status)
	if allowed_role and not has_role(allowed_role):
		frappe.throw(_("Only {0} can edit a CAPEX plan in {1} state.").format(allowed_role, source_status))

	editable_fields = _capex_plan_editable_fields(source_status)
	changed_fields = [fieldname for fieldname in tracked_fields if before_save.get(fieldname) != doc.get(fieldname)]
	if not changed_fields:
		return

	if source_status in {"Approved", "Frozen", "Closed"}:
		frappe.throw(_("CAPEX Plan fields are locked once the plan reaches {0} state.").format(source_status))

	unauthorized_fields = sorted(set(changed_fields) - editable_fields)
	if unauthorized_fields:
		frappe.throw(
			_("You can only edit {0} while the CAPEX plan is in {1} state.").format(
				", ".join(sorted(editable_fields)),
				source_status,
			)
		)


def _refresh_linked_capex_plans(doc: Document) -> None:
	plan_names: set[str] = set()
	if doc.get("capex_plan"):
		plan_names.add(doc.capex_plan)
	if doc.get("asset_request") and frappe.db.exists("Fixed Asset Request", doc.asset_request):
		request_plan = frappe.db.get_value("Fixed Asset Request", doc.asset_request, "capex_plan")
		if request_plan:
			plan_names.add(request_plan)

	for plan_name in plan_names:
		refresh_capex_plan_totals(plan_name)


def _validate_capex_plan_budget(doc: Document, amount: float) -> None:
	if amount <= 0 and doc.doctype != "Asset":
		return

	plan_name = doc.get("capex_plan")
	if not plan_name and doc.get("asset_request") and frappe.db.exists("Fixed Asset Request", doc.asset_request):
		plan_name = frappe.db.get_value("Fixed Asset Request", doc.asset_request, "capex_plan")
	if not plan_name:
		if amount > 0:
			frappe.throw(_("A Fixed Asset CAPEX Plan is required before this document can be saved."))
		return

	plan = _capex_plan_doc(plan_name)
	if not plan:
		frappe.throw(_("CAPEX Plan {0} does not exist.").format(plan_name))

	_sync_capex_plan_context(doc, plan)
	_validate_capex_alignment(doc, plan)

	if plan.get("status") not in {"Approved", "Frozen"}:
		frappe.throw(_("CAPEX Plan {0} must be Approved or Frozen before it can control asset procurement.").format(plan.name))

	refresh_capex_plan_totals(plan.name)
	remaining_budget = flt(frappe.db.get_value("Fixed Asset CAPEX Plan", plan.name, "remaining_budget") or 0)
	if amount > 0:
		doc.budget_available = 1 if remaining_budget >= amount else 0
	if remaining_budget < amount and not user_has_finance_override():
		frappe.throw(
			_("Document amount {0} exceeds remaining CAPEX budget of {1} on plan {2}.").format(
				frappe.format_value(amount),
				frappe.format_value(remaining_budget),
				plan.name,
			)
		)


def _refresh_capex_totals(plan_name: str) -> tuple[float, float, float]:
	committed_amount = flt(
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(GREATEST(child.base_amount - COALESCE(child.billed_amt, 0), 0)), 0)
			FROM `tabPurchase Receipt Item` child
			INNER JOIN `tabPurchase Receipt` parent ON parent.name = child.parent
			WHERE parent.docstatus = 1
			  AND IFNULL(parent.is_return, 0) = 0
			  AND IFNULL(parent.capex_plan, '') = %s
			""",
			(plan_name,),
		)[0][0]
	)
	actual_from_invoices = flt(
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(base_grand_total), 0)
			FROM `tabPurchase Invoice`
			WHERE docstatus = 1 AND IFNULL(capex_plan, '') = %s
			""",
			(plan_name,),
		)[0][0]
	)
	actual_from_assets = flt(
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(total_asset_cost), 0)
			FROM `tabAsset`
			WHERE docstatus = 1
			  AND IFNULL(capex_plan, '') = %s
			  AND IFNULL(purchase_invoice, '') = ''
			  AND IFNULL(purchase_receipt, '') = ''
			""",
			(plan_name,),
		)[0][0]
	)
	actual_spent = actual_from_invoices + actual_from_assets
	approved_budget = flt(frappe.db.get_value("Fixed Asset CAPEX Plan", plan_name, "approved_budget") or 0)
	remaining_budget = calculate_remaining_budget(approved_budget, committed_amount, actual_spent)
	return committed_amount, actual_spent, remaining_budget


def refresh_capex_plan_totals(plan_name: str) -> None:
	committed_amount, actual_spent, remaining_budget = _refresh_capex_totals(plan_name)
	approved_budget = flt(frappe.db.get_value("Fixed Asset CAPEX Plan", plan_name, "approved_budget") or 0)
	utilization_percentage, utilization_status = calculate_budget_utilization(
		approved_budget,
		committed_amount,
		actual_spent,
	)
	frappe.db.set_value(
		"Fixed Asset CAPEX Plan",
		plan_name,
		{
			"committed_amount": committed_amount,
			"actual_spent": actual_spent,
			"remaining_budget": remaining_budget,
			"budget_utilization_percentage": utilization_percentage,
			"budget_utilization_status": utilization_status,
		},
		update_modified=False,
	)


def validate_capex_plan(doc: Document) -> None:
	company = _resolve_capex_company(doc)
	safe_set(doc, "company", company)
	safe_set(doc, "fiscal_year", _resolve_capex_fiscal_year(doc, company))

	if not doc.get("cost_center"):
		frappe.throw(_("Cost Center is required for a CAPEX plan."))
	if not doc.get("asset_category"):
		frappe.throw(_("Asset Category is required for a CAPEX plan."))
	if not doc.get("company"):
		frappe.throw(_("Company is required for a CAPEX plan."))

	cost_center_company = get_cost_center_company(doc.get("cost_center"))
	if cost_center_company and doc.get("company") and cost_center_company != doc.company:
		frappe.throw(
			_("Cost Center {0} does not belong to Company {1}.").format(doc.cost_center, doc.company)
		)

	existing_plan = frappe.get_all(
		"Fixed Asset CAPEX Plan",
		filters={
			"name": ["!=", doc.name],
			"docstatus": ["<", 2],
			"company": doc.company,
			"fiscal_year": doc.fiscal_year,
			"cost_center": doc.cost_center,
			"asset_category": doc.asset_category,
		},
		fields=["name"],
		limit=1,
	)
	if existing_plan:
		frappe.throw(
			_(
				"A CAPEX plan already exists for company {0}, fiscal year {1}, cost center {2}, and asset category {3}."
			).format(doc.company, doc.fiscal_year, doc.cost_center, doc.asset_category)
		)

	committed_amount, actual_spent, _ = _refresh_capex_totals(doc.name)
	remaining_budget = calculate_remaining_budget(doc.get("approved_budget"), committed_amount, actual_spent)
	utilization_percentage, utilization_status = calculate_budget_utilization(
		doc.get("approved_budget"),
		committed_amount,
		actual_spent,
	)
	safe_set(doc, "committed_amount", committed_amount)
	safe_set(doc, "actual_spent", actual_spent)
	safe_set(doc, "remaining_budget", remaining_budget)
	safe_set(doc, "budget_utilization_percentage", utilization_percentage)
	safe_set(doc, "budget_utilization_status", utilization_status)
	if doc.get("status") not in CAPEX_PLAN_STATUS_OPTIONS:
		safe_set(doc, "status", "Draft")

	_validate_capex_plan_status_transition(doc)
	_validate_capex_plan_field_locking(doc)


def _validate_request_capex_plan(doc: Document, require_plan: bool = False) -> None:
	company = _resolve_capex_company(doc)
	safe_set(doc, "company", company)
	safe_set(doc, "fiscal_year", _resolve_capex_fiscal_year(doc, company))

	plan_name = _first_non_empty(doc.get("capex_plan"), _find_matching_capex_plan(doc))
	if not plan_name:
		doc.budget_available = 0
		if require_plan or doc.get("approval_status") not in {"Draft", "Deferred"}:
			frappe.throw(_("A Fixed Asset CAPEX Plan is required for this request."))
		return

	safe_set(doc, "capex_plan", plan_name)
	plan = _capex_plan_doc(plan_name)
	if not plan:
		frappe.throw(_("CAPEX Plan {0} does not exist.").format(plan_name))

	_sync_capex_plan_context(doc, plan)
	_validate_capex_alignment(doc, plan)

	if plan.get("status") not in {"Approved", "Frozen"}:
		frappe.throw(_("CAPEX Plan {0} must be Approved or Frozen before it can be used.").format(plan.name))

	refresh_capex_plan_totals(plan.name)
	remaining_budget = flt(frappe.db.get_value("Fixed Asset CAPEX Plan", plan.name, "remaining_budget") or 0)
	doc.budget_available = 1 if remaining_budget >= flt(doc.get("estimated_total_cost") or 0) else 0
	if remaining_budget < flt(doc.get("estimated_total_cost") or 0) and not user_has_finance_override():
		frappe.throw(
			_(
				"Requested amount {0} exceeds CAPEX plan balance of {1}."
			).format(
				frappe.format_value(doc.get("estimated_total_cost") or 0),
				frappe.format_value(remaining_budget),
			)
		)


def validate_fixed_asset_request(doc: Document) -> None:
	quantity = max(cint(doc.get("quantity")), 1)
	unit_cost = flt(doc.get("estimated_unit_cost") or 0)
	estimated_total_cost = quantity * unit_cost
	safe_set(doc, "estimated_total_cost", estimated_total_cost)

	if doc.get("approval_status") not in REQUEST_APPROVAL_STATUS_OPTIONS:
		safe_set(doc, "approval_status", "Draft")

	_validate_request_capex_plan(doc, require_plan=False)


def on_submit_fixed_asset_request(doc: Document) -> None:
	_validate_request_capex_plan(doc, require_plan=True)
	safe_set(doc, "approval_status", "Approved")


def on_update_after_submit_fixed_asset_request(doc: Document) -> None:
	if doc.get("capex_plan"):
		refresh_capex_plan_totals(doc.capex_plan)


def _validate_fixed_asset_procurement(doc: Document, require_plan: bool = False) -> None:
	if not (doc.get("asset_request") or doc.get("capex_plan") or doc.get("fixed_asset_category")):
		return

	request = None
	if doc.get("asset_request") and frappe.db.exists("Fixed Asset Request", doc.asset_request):
		request = frappe.get_doc("Fixed Asset Request", doc.asset_request)
		safe_set(doc, "company", _first_non_empty(doc.get("company"), request.get("company")))
		safe_set(doc, "fiscal_year", _first_non_empty(doc.get("fiscal_year"), request.get("fiscal_year")))
		safe_set(doc, "cost_center", _first_non_empty(doc.get("cost_center"), request.get("cost_center")))
		safe_set(
			doc,
			"fixed_asset_category",
			_first_non_empty(doc.get("fixed_asset_category"), request.get("asset_category")),
		)
		safe_set(doc, "capex_plan", _first_non_empty(doc.get("capex_plan"), request.get("capex_plan")))

	plan_name = _first_non_empty(doc.get("capex_plan"), _find_matching_capex_plan(doc))
	if not plan_name:
		if require_plan or doc.get("asset_request") or doc.get("fixed_asset_category"):
			frappe.throw(_("A Fixed Asset CAPEX Plan is required for this document."))
		return

	safe_set(doc, "capex_plan", plan_name)
	plan = _capex_plan_doc(plan_name)
	if not plan:
		frappe.throw(_("CAPEX Plan {0} does not exist.").format(plan_name))

	_sync_capex_plan_context(doc, plan)
	_validate_capex_alignment(doc, plan)

	if plan.get("status") not in {"Approved", "Frozen"}:
		frappe.throw(_("CAPEX Plan {0} must be Approved or Frozen before it can be used.").format(plan.name))

	amount = _capex_doc_amount(doc)
	refresh_capex_plan_totals(plan.name)
	remaining_budget = flt(frappe.db.get_value("Fixed Asset CAPEX Plan", plan.name, "remaining_budget") or 0)
	if amount > 0 and remaining_budget < amount and not user_has_finance_override():
		frappe.throw(
			_("Document amount {0} exceeds remaining CAPEX budget of {1} on plan {2}.").format(
				frappe.format_value(amount),
				frappe.format_value(remaining_budget),
				plan.name,
			)
		)


def _ensure_fixed_asset_row_locations(doc: Document) -> None:
	default_location = None
	for row in doc.get("items") or []:
		is_fixed_asset = row.get("is_fixed_asset")
		if is_fixed_asset is None and row.get("item_code"):
			is_fixed_asset = frappe.db.get_value("Item", row.item_code, "is_fixed_asset")

		if not cint(is_fixed_asset) or row.get("asset_location"):
			continue

		if default_location is None:
			default_location = get_default_location_name()

		safe_set(row, "asset_location", default_location)


def validate_material_request(doc: Document) -> None:
	_validate_fixed_asset_procurement(doc, require_plan=False)


def on_submit_material_request(doc: Document) -> None:
	_refresh_linked_capex_plans(doc)


def on_cancel_material_request(doc: Document) -> None:
	_refresh_linked_capex_plans(doc)


def on_update_after_submit_material_request(doc: Document) -> None:
	_refresh_linked_capex_plans(doc)


def validate_purchase_order(doc: Document) -> None:
	_validate_fixed_asset_procurement(doc, require_plan=False)


def on_submit_purchase_order(doc: Document) -> None:
	_refresh_linked_capex_plans(doc)


def on_cancel_purchase_order(doc: Document) -> None:
	_refresh_linked_capex_plans(doc)


def on_update_after_submit_purchase_order(doc: Document) -> None:
	_refresh_linked_capex_plans(doc)


def validate_purchase_receipt(doc: Document) -> None:
	_ensure_fixed_asset_row_locations(doc)
	_validate_fixed_asset_procurement(doc, require_plan=False)


def on_submit_purchase_receipt(doc: Document) -> None:
	_refresh_linked_capex_plans(doc)


def on_cancel_purchase_receipt(doc: Document) -> None:
	_refresh_linked_capex_plans(doc)


def on_update_after_submit_purchase_receipt(doc: Document) -> None:
	_refresh_linked_capex_plans(doc)


def validate_purchase_invoice(doc: Document) -> None:
	_ensure_fixed_asset_row_locations(doc)
	_validate_fixed_asset_procurement(doc, require_plan=False)


def on_submit_purchase_invoice(doc: Document) -> None:
	_refresh_linked_capex_plans(doc)


def on_cancel_purchase_invoice(doc: Document) -> None:
	_refresh_linked_capex_plans(doc)


def on_update_after_submit_purchase_invoice(doc: Document) -> None:
	_refresh_linked_capex_plans(doc)


def sync_asset_location_details_from_movement(doc: Document, asset_name: str) -> None:
	location, current_employee = doc.get_latest_location_and_custodian(asset_name)
	current_location = frappe.db.get_value("Asset", asset_name, "location")
	effective_location = location or current_location
	update_values: dict[str, Any] = {
		"custodian": current_employee or None,
		"current_custodian": current_employee or None,
		"custodian_department": None,
	}

	if effective_location:
		update_values["location"] = effective_location
		update_values["asset_location"] = effective_location

	if current_employee:
		employee = frappe.db.get_value(
			"Employee",
			current_employee,
			["department", "branch"],
			as_dict=True,
		)
		if employee:
			update_values["custodian_department"] = employee.department or None
			if employee.department:
				update_values["department"] = employee.department
			if employee.branch:
				update_values["branch"] = employee.branch

	if update_values:
		frappe.db.set_value("Asset", asset_name, update_values, update_modified=False)


def on_submit_asset_movement(doc: Document) -> None:
	for row in doc.get("assets") or []:
		sync_asset_location_details_from_movement(doc, row.asset)


def on_cancel_asset_movement(doc: Document) -> None:
	for row in doc.get("assets") or []:
		sync_asset_location_details_from_movement(doc, row.asset)


def _policy_status_from_dates(start_date: Any, end_date: Any) -> str:
	if start_date and getdate(start_date) > getdate(nowdate()):
		return "Scheduled"
	if not end_date:
		return "Active"
	end_date = getdate(end_date)
	today_date = getdate(nowdate())
	days_remaining = (end_date - today_date).days
	if days_remaining < 0:
		return "Expired"
	if days_remaining <= 30:
		return "Expiring Soon"
	return "Active"


def _policy_approval_status(doc: Document) -> str:
	approval_status = doc.get("approval_status") or "Draft"
	if approval_status not in POLICY_APPROVAL_STATUS_OPTIONS:
		return "Draft"
	return approval_status


def _policy_coverage_basis(doc: Document) -> str:
	coverage_basis = doc.get("coverage_basis") or "Selected Assets"
	if coverage_basis not in INSURANCE_COVERAGE_BASIS_OPTIONS:
		return "Selected Assets"
	return coverage_basis


def _asset_insurance_value(asset: dict[str, Any]) -> float:
	return flt(
		_first_non_empty(
			asset.get("value_after_depreciation"),
			asset.get("total_asset_cost"),
			asset.get("gross_purchase_amount"),
			asset.get("purchase_amount"),
		)
	)


def _validate_insurable_asset(asset: dict[str, Any]) -> None:
	if cint(asset.get("docstatus")) != 1:
		frappe.throw(_("Asset {0} must be submitted before it can be insured.").format(asset.get("name")))
	if asset.get("status") in {"Sold", "Scrapped"}:
		frappe.throw(_("Asset {0} cannot be insured because it is {1}.").format(asset.get("name"), asset.get("status")))
	if not asset.get("item_code"):
		frappe.throw(_("Asset {0} does not have an Item Code.").format(asset.get("name")))


def _policy_has_date_overlap(existing_start: Any, existing_end: Any, new_start: Any, new_end: Any) -> bool:
	if not existing_start or not existing_end or not new_start or not new_end:
		return False
	existing_start_date = getdate(existing_start)
	existing_end_date = getdate(existing_end)
	new_start_date = getdate(new_start)
	new_end_date = getdate(new_end)
	return existing_start_date <= new_end_date and existing_end_date >= new_start_date


def _find_overlapping_insurance_policy(asset_name: str, policy_name: str, start_date: Any, end_date: Any) -> dict[str, Any] | None:
	overlapping_policies = frappe.db.sql(
		"""
		SELECT parent.name, parent.policy_number, parent.coverage_start_date, parent.coverage_end_date
		FROM `tabAsset Insurance Policy Item` child
		INNER JOIN `tabAsset Insurance Policy` parent ON parent.name = child.parent
		WHERE child.asset = %s
			AND parent.name != %s
			AND parent.docstatus = 1
			AND IFNULL(parent.status, '') != 'Cancelled'
		ORDER BY parent.coverage_start_date DESC, parent.modified DESC
		""",
		(asset_name, policy_name),
		as_dict=True,
	)
	for policy in overlapping_policies:
		if not policy.get("coverage_start_date") or not policy.get("coverage_end_date"):
			continue
		if _policy_has_date_overlap(policy.coverage_start_date, policy.coverage_end_date, start_date, end_date):
			return policy
	return None


def _normalise_insurance_policy_coverage(doc: Document) -> None:
	"""Validate the policy's covered asset rows."""
	previous = doc.get_doc_before_save()
	previous_assets = {row.asset for row in previous.covered_assets or []} if previous else set()

	seen: set[str] = set()
	for row in doc.get("covered_assets") or []:
		asset_name = row.get("asset")
		if not asset_name:
			continue
		if asset_name in seen:
			frappe.throw(_("Asset {0} is listed more than once in the Covered Assets table.").format(asset_name))
		seen.add(asset_name)
		asset = frappe.db.get_value(
			"Asset",
			asset_name,
			["name", "item_code", "asset_category", "gross_purchase_amount", "value_after_depreciation", "total_asset_cost", "docstatus", "status"],
			as_dict=True,
		)
		if not asset:
			frappe.throw(_("Asset {0} does not exist.").format(asset_name))
		if asset_name not in previous_assets:
			_validate_insurable_asset(asset)
		if doc.get("asset_category") and asset.asset_category != doc.asset_category:
			frappe.throw(_("Asset {0} is outside this policy's Asset Category.").format(asset_name))
		row.item_code = asset.item_code
		row.asset_category = asset.asset_category
		if row.get("insured_value") is None:
			row.insured_value = _asset_insurance_value(asset)
		if not row.get("coverage_notes"):
			row.coverage_notes = _("Selected asset coverage")


def validate_insurance_policy(doc: Document) -> None:
	if doc.get("coverage_start_date") and doc.get("coverage_end_date") and getdate(doc.coverage_end_date) < getdate(doc.coverage_start_date):
		frappe.throw(_("Coverage end date cannot be earlier than the start date."))
	if doc.get("insurance_company"):
		supplier_group = frappe.db.get_value("Supplier", doc.insurance_company, "supplier_group")
		if supplier_group != "Insurance Provider":
			frappe.throw(_("Insurance Company must be a Supplier in the Insurance Provider group."))

	safe_set(doc, "approval_status", _policy_approval_status(doc))
	safe_set(doc, "coverage_basis", _policy_coverage_basis(doc))
	safe_set(doc, "status", _policy_status_from_dates(doc.get("coverage_start_date"), doc.get("coverage_end_date")))

	if doc.get("coverage_basis") == "Item Code" and doc.get("asset_item_code"):
		item_data = frappe.db.get_value("Item", doc.asset_item_code, ["name", "is_fixed_asset"], as_dict=True)
		if not item_data:
			frappe.throw(_("Asset Item Code {0} does not exist.").format(doc.asset_item_code))
		if not item_data.is_fixed_asset:
			frappe.throw(_("Asset Item Code {0} must be marked as a fixed asset item.").format(doc.asset_item_code))

	_normalise_insurance_policy_coverage(doc)

	for row in doc.get("covered_assets") or []:
		if row.get("asset"):
			overlap = _find_overlapping_insurance_policy(row.get("asset"), doc.name, doc.get("coverage_start_date"), doc.get("coverage_end_date"))
			if overlap:
				frappe.throw(
					_("Asset {0} already has an overlapping insurance policy {1} ({2}).").format(
						row.get("asset"),
						overlap.name,
						overlap.policy_number or overlap.name,
					)
				)


def on_submit_insurance_policy(doc: Document) -> None:
	sync_assets_for_insurance_policy(doc.name)


def before_submit_insurance_policy(doc: Document) -> None:
	if doc.get("approval_status") in {"Draft", "Pending Review", "Returned for Revision", "Rejected", None, ""}:
		safe_set(doc, "approval_status", "Approved")


def on_update_after_submit_insurance_policy(doc: Document) -> None:
	sync_assets_for_insurance_policy(doc.name)


def on_cancel_insurance_policy(doc: Document) -> None:
	doc.db_set({"approval_status": "Cancelled", "status": "Cancelled"}, update_modified=False)
	sync_assets_for_insurance_policy(doc.name)


def validate_insurance_claim(doc: Document) -> None:
	if doc.get("claim_status") not in CLAIM_STATUS_OPTIONS:
		safe_set(doc, "claim_status", "Draft")
	if doc.get("claim_date") and doc.get("incident_date") and getdate(doc.incident_date) > getdate(doc.claim_date):
		frappe.throw(_("Incident date cannot be later than the claim date."))
	if doc.get("insurance_policy") and doc.get("asset"):
		policy = frappe.get_doc("Asset Insurance Policy", doc.insurance_policy)
		if policy.docstatus != 1:
			frappe.throw(_("The selected insurance policy must be submitted before a claim can be raised."))
		if policy.get("status") == "Cancelled":
			frappe.throw(_("Claims cannot be raised against a cancelled insurance policy."))
		if policy.get("coverage_start_date") and policy.get("coverage_end_date"):
			if getdate(doc.incident_date) < getdate(policy.coverage_start_date) or getdate(doc.incident_date) > getdate(policy.coverage_end_date):
				frappe.throw(_("The incident date must fall within the policy coverage period."))
		covers_asset = frappe.db.exists("Asset Insurance Policy Item", {"parent": doc.insurance_policy, "asset": doc.asset})
		if not covers_asset:
			frappe.throw(_("The selected asset is not covered under this insurance policy."))


def validate_maintenance_plan(doc: Document) -> None:
	if doc.get("status") not in MAINTENANCE_STATUS_OPTIONS:
		safe_set(doc, "status", "Active")
	if doc.get("next_due_date") and doc.get("last_done_date") and getdate(doc.next_due_date) < getdate(doc.last_done_date):
		frappe.throw(_("Next due date cannot be earlier than the last done date."))
	if doc.get("maintenance_type") not in {"Preventive", "Corrective", "Calibration", "Inspection"}:
		frappe.throw(_("Select a valid maintenance type."))
	if doc.get("frequency") and doc.get("frequency") not in MAINTENANCE_FREQUENCY_OPTIONS:
		frappe.throw(_("Select a valid maintenance frequency."))


def validate_usage_reading(doc: Document) -> None:
	if doc.get("reading_type") not in USAGE_READING_TYPES:
		frappe.throw(_("Select a valid usage reading type."))
	previous_reading = doc.get("previous_reading")
	if previous_reading in (None, ""):
		previous_reading = frappe.db.get_value(
			"Asset Usage Reading",
			{"asset": doc.asset, "reading_type": doc.reading_type, "docstatus": ["<", 2], "name": ["!=", doc.name]},
			"current_reading",
			order_by="reading_date desc, creation desc",
		)
		safe_set(doc, "previous_reading", previous_reading or 0)
	usage_for_period = flt(doc.get("current_reading") or 0) - flt(doc.get("previous_reading") or 0)
	if usage_for_period < 0:
		frappe.throw(_("Current reading must be greater than or equal to the previous reading."))
	safe_set(doc, "usage_for_period", usage_for_period)


def validate_cip_capitalization_request(doc: Document) -> None:
	if doc.get("finance_review_status") not in CIP_STATUS_OPTIONS:
		safe_set(doc, "finance_review_status", "Draft")
	if doc.get("total_project_cost") and not doc.get("amount_to_capitalize"):
		safe_set(doc, "amount_to_capitalize", doc.total_project_cost)
	if doc.get("amount_to_capitalize") and not doc.get("total_project_cost"):
		safe_set(doc, "total_project_cost", doc.amount_to_capitalize)
	if doc.get("total_project_cost") and doc.get("amount_to_capitalize") and flt(doc.amount_to_capitalize) > flt(doc.total_project_cost):
		frappe.throw(_("Amount to capitalize cannot exceed the total project cost."))
	if not doc.get("asset_category"):
		frappe.throw(_("Asset Category is required to capitalize a project."))


def _create_or_update_asset_from_cip(doc: Document) -> str:
	project_company = None
	if doc.get("project"):
		project_company = frappe.db.get_value("Project", doc.project, "company")
		if not project_company:
			project_company = frappe.defaults.get_user_default("Company")
	company = project_company or frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw(_("Please set a default company before capitalizing CIP assets."))

	item_code = get_fixed_asset_item(doc.asset_category, company)
	if not item_code:
		frappe.throw(
			_("Create a Fixed Asset item for Asset Category {0} before capitalizing the project.").format(
				frappe.bold(doc.asset_category)
			)
		)

	location = get_default_location_name()
	category_defaults = get_asset_category_defaults(doc.asset_category)
	asset_name = doc.get("created_asset")
	if asset_name and frappe.db.exists("Asset", asset_name):
		asset = frappe.get_doc("Asset", asset_name)
	else:
		asset = frappe.new_doc("Asset")
		asset.asset_name = doc.get("project") or doc.get("name") or doc.get("remarks") or doc.asset_category
		asset.item_code = item_code
		asset.company = company
		asset.location = location
		asset.asset_location = location
		asset.purchase_date = doc.get("capitalization_date") or today()
		asset.asset_category = doc.asset_category
		asset.asset_business_class = category_defaults.get("naseco_asset_business_class")
		asset.calculate_depreciation = 0 if category_defaults.get("naseco_non_depreciable") else 1
		asset.total_asset_cost = flt(doc.get("amount_to_capitalize") or 0)
		asset.gross_purchase_amount = flt(doc.get("amount_to_capitalize") or 0)
		asset.available_for_use_date = doc.get("capitalization_date") or today()
		asset.status = "Work In Progress"
		asset.capitalization_status = "Pending"
		asset.asset_request = doc.get("asset_request")
		asset.capex_plan = doc.get("capex_plan")
		asset.depreciation_start_date = None
		asset.insert(ignore_permissions=True)
		asset_name = asset.name
		return asset_name

	asset.item_code = item_code
	safe_set(asset, "company", company)
	safe_set(asset, "asset_category", doc.asset_category)
	safe_set(asset, "asset_business_class", category_defaults.get("naseco_asset_business_class"))
	if category_defaults.get("naseco_non_depreciable"):
		safe_set(asset, "calculate_depreciation", 0)
	safe_set(asset, "asset_request", doc.get("asset_request"))
	safe_set(asset, "capex_plan", doc.get("capex_plan"))
	safe_set(asset, "total_asset_cost", flt(doc.get("amount_to_capitalize") or asset.get("total_asset_cost") or 0))
	safe_set(asset, "gross_purchase_amount", flt(doc.get("amount_to_capitalize") or asset.get("gross_purchase_amount") or 0))
	safe_set(asset, "location", location)
	safe_set(asset, "asset_location", location)
	safe_set(asset, "purchase_date", doc.get("capitalization_date") or asset.get("purchase_date") or today())
	safe_set(asset, "status", "Work In Progress")
	safe_set(asset, "capitalization_status", "Pending")
	asset.save(ignore_permissions=True)
	return asset.name


def on_submit_cip_capitalization_request(doc: Document) -> None:
	asset_name = _create_or_update_asset_from_cip(doc)
	safe_set(doc, "created_asset", asset_name)
	safe_set(doc, "finance_review_status", "Approved")
	if doc.get("project"):
		frappe.db.set_value("Project", doc.project, "cip_capitalization_request", doc.name, update_modified=False)


def create_material_request_from_request(request_name: str) -> str:
	request = frappe.get_doc("Fixed Asset Request", request_name)
	company = _first_non_empty(
		request.get("company"),
		get_employee_company(request.get("requesting_employee")),
		get_cost_center_company(request.get("cost_center")),
		frappe.defaults.get_user_default("Company"),
	)
	item_code = get_fixed_asset_item(request.asset_category, company)
	if not item_code:
		frappe.throw(_("Create a Fixed Asset item for Asset Category {0} before creating the Material Request.").format(request.asset_category))

	item_row = frappe.db.get_value(
		"Item",
		item_code,
		["stock_uom", "item_name"],
		as_dict=True,
	)
	if not item_row or not item_row.stock_uom:
		frappe.throw(_("Fixed Asset item {0} is missing a Stock UOM.").format(item_code))

	material_request = frappe.new_doc("Material Request")
	material_request.material_request_type = "Purchase"
	material_request.transaction_date = today()
	material_request.title = request.request_title
	material_request.company = company
	material_request.asset_request = request.name
	material_request.capex_plan = request.get("capex_plan")
	material_request.cost_center = request.get("cost_center")
	material_request.fixed_asset_category = request.asset_category
	material_request.append(
		"items",
		{
			"item_code": item_code,
			"qty": request.get("quantity") or 1,
			"uom": item_row.stock_uom,
			"stock_uom": item_row.stock_uom,
			"conversion_factor": 1,
			"schedule_date": request.get("required_date") or today(),
		},
	)
	material_request.insert(ignore_permissions=True)
	request.db_set("linked_material_request", material_request.name)
	return material_request.name


def get_asset_sale_details(
	asset_name: str,
	posting_date: str | None = None,
	finance_book: str | None = None,
	sell_qty: int | None = None,
) -> dict[str, Any]:
	asset = frappe.get_doc("Asset", asset_name)
	asset.check_permission("read")

	quantity = cint(asset.get("asset_quantity") or 1) if sell_qty is None else cint(sell_qty)
	total_book_value, allocated_book_value = _get_asset_sale_book_values(
		asset,
		posting_date,
		finance_book,
		quantity,
	)
	company_currency = frappe.get_cached_value("Company", asset.company, "default_currency")

	return {
		"asset_quantity": flt(asset.get("asset_quantity") or 1),
		"sell_qty": quantity,
		"currency": company_currency,
		"finance_books": [row.finance_book for row in asset.get("finance_books") or [] if row.finance_book],
		"default_finance_book": finance_book or _get_asset_sale_finance_book(asset),
		"total_net_book_value": total_book_value,
		"net_book_value": allocated_book_value,
		"suggested_selling_price": allocated_book_value,
	}


def _get_asset_sale_finance_book(asset: Document, finance_book: str | None = None) -> str | None:
	finance_books = asset.get("finance_books") or []
	if not finance_books:
		return None
	if finance_book:
		if finance_book not in {row.finance_book for row in finance_books}:
			frappe.throw(_("Finance Book {0} is not configured on Asset {1}.").format(finance_book, asset.name))
		return finance_book

	default_finance_book_idx = asset.get_default_finance_book_idx()
	if default_finance_book_idx is not None:
		return finance_books[default_finance_book_idx].finance_book

	return finance_books[0].finance_book


def _get_asset_sale_book_values(
	asset: Document,
	posting_date: str | None = None,
	finance_book: str | None = None,
	sell_qty: int | None = None,
) -> tuple[float, float]:
	asset_quantity = flt(asset.get("asset_quantity") or 1)
	quantity = cint(asset_quantity) if sell_qty is None else cint(sell_qty)
	if quantity <= 0:
		frappe.throw(_("Sell quantity must be greater than zero."))
	if quantity > asset_quantity:
		frappe.throw(_("Sell quantity cannot exceed the asset quantity of {0}.").format(asset_quantity))

	from erpnext.assets.doctype.asset.depreciation import get_value_after_depreciation_on_disposal_date

	valuation_date = getdate(posting_date or nowdate())
	available_for_use_date = asset.get("available_for_use_date")
	if available_for_use_date and valuation_date < getdate(available_for_use_date):
		frappe.throw(
			_("Sale date cannot be before the available-for-use date {0}.").format(
				frappe.format_value(available_for_use_date, {"fieldtype": "Date"})
			)
		)

	total_book_value = get_value_after_depreciation_on_disposal_date(
		asset.name,
		str(valuation_date),
		_get_asset_sale_finance_book(asset, finance_book),
	)
	precision = asset.precision("net_purchase_amount")
	total_book_value = flt(total_book_value, precision)
	allocated_book_value = flt(total_book_value * quantity / asset_quantity, precision)
	return total_book_value, allocated_book_value


def _set_asset_sale_values(
	sales_invoice: Document,
	asset: Document,
	sell_qty: int,
	selling_price: float | None,
	posting_date: str | None,
	finance_book: str | None,
) -> None:
	_, allocated_book_value = _get_asset_sale_book_values(asset, posting_date, finance_book, sell_qty)
	total_selling_price = allocated_book_value if selling_price is None else flt(selling_price)
	if total_selling_price < 0:
		frappe.throw(_("Selling price cannot be negative."))
	unit_rate = total_selling_price / sell_qty

	for item in sales_invoice.get("items") or []:
		item.price_list_rate = unit_rate
		item.rate = unit_rate
		item.discount_percentage = 0
		if item.meta.has_field("naseco_asset_net_book_value"):
			item.naseco_asset_net_book_value = allocated_book_value

	sales_invoice.calculate_taxes_and_totals()


def _resolve_asset_sale_customer(customer: str | None, employee: str | None) -> tuple[str | None, str | None]:
	if employee:
		employee_doc = frappe.get_doc("Employee", employee)
		employee_doc.check_permission("read")
		linked_customer = employee_doc.get("naseco_asset_sale_customer")
		if not linked_customer:
			frappe.throw(
				_("Employee {0} does not have a Sales Invoice Customer. Set it on the Employee record first.").format(
					employee
				)
			)
		customer = linked_customer

	if customer:
		frappe.get_doc("Customer", customer).check_permission("read")
	return customer, employee


def create_sales_invoice_for_asset_sale(
	asset_name: str,
	posting_date: str | None = None,
	item_code: str | None = None,
	company: str | None = None,
	serial_no: str | None = None,
	sell_qty: int | None = None,
	finance_book: str | None = None,
	selling_price: float | None = None,
	customer: str | None = None,
	employee: str | None = None,
) -> Document:
	asset = frappe.get_doc("Asset", asset_name)
	asset.check_permission("read")
	if not frappe.has_permission("Sales Invoice", ptype="create"):
		frappe.throw(_("You do not have permission to create a Sales Invoice."), frappe.PermissionError)

	quantity = cint(asset.get("asset_quantity") or 1) if sell_qty is None else cint(sell_qty)
	customer, employee = _resolve_asset_sale_customer(customer, employee)

	from erpnext.assets.doctype.asset.asset import make_sales_invoice

	sales_invoice = make_sales_invoice(
		asset.name,
		item_code or asset.get("item_code"),
		company or asset.get("company"),
		quantity,
		serial_no or asset.get("serial_no"),
	)
	if posting_date:
		sales_invoice.posting_date = getdate(posting_date)
	if customer:
		sales_invoice.customer = customer
	if employee and sales_invoice.meta.has_field("naseco_asset_sale_employee"):
		sales_invoice.naseco_asset_sale_employee = employee

	if customer:
		sales_invoice.set_missing_values()

	_set_asset_sale_values(
		sales_invoice,
		asset,
		quantity,
		selling_price,
		posting_date,
		finance_book,
	)
	return sales_invoice


def validate_asset_request_links(request: Document) -> None:
	if request.get("linked_material_request") and not frappe.db.exists("Material Request", request.linked_material_request):
		request.linked_material_request = None
