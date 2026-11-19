from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def _column(label: str, fieldname: str | None = None, fieldtype: str = "Data", width: int = 140) -> dict[str, Any]:
	return {
		"label": _(label),
		"fieldname": fieldname or frappe.scrub(label),
		"fieldtype": fieldtype,
		"width": width,
	}


def _asset_filter_sql(filters: dict[str, Any], alias: str = "a") -> tuple[str, list[Any]]:
	conditions = ["1=1"]
	values: list[Any] = []

	for key, column in [
		("company", "company"),
		("branch", "branch"),
		("department", "department"),
		("cost_center", "cost_center"),
		("asset_category", "asset_category"),
		("custodian", "custodian"),
		("location", "asset_location"),
		("status", "status"),
	]:
		if filters.get(key):
			conditions.append(f"IFNULL({alias}.{column}, '') = %s")
			values.append(filters[key])

	if filters.get("from_date"):
		conditions.append(f"DATE({alias}.purchase_date) >= %s")
		values.append(filters["from_date"])
	if filters.get("to_date"):
		conditions.append(f"DATE({alias}.purchase_date) <= %s")
		values.append(filters["to_date"])

	return " AND ".join(conditions), values


def _execute_asset_register(filters: dict[str, Any]):
	where_sql, values = _asset_filter_sql(filters)
	rows = frappe.db.sql(
		f"""
		SELECT
			a.name AS asset,
			a.asset_name,
			a.asset_category,
			a.asset_business_class,
			a.branch,
			a.department,
			COALESCE(a.asset_location, a.location) AS location,
			a.current_custodian,
			a.total_asset_cost AS gross_cost,
			a.total_asset_cost - COALESCE(a.value_after_depreciation, 0) AS accumulated_depreciation,
			COALESCE(a.value_after_depreciation, 0) AS net_book_value,
			a.total_number_of_depreciations AS useful_life,
			GREATEST(COALESCE(a.total_number_of_depreciations, 0) - COALESCE(a.opening_number_of_booked_depreciations, 0), 0) AS remaining_life,
			a.status
		FROM `tabAsset` a
		WHERE {where_sql}
		ORDER BY a.asset_category, a.asset_name
		""",
		values,
		as_dict=True,
	)
	columns = [
		_column("Asset", "asset"),
		_column("Asset Name", "asset_name"),
		_column("Asset Category", "asset_category"),
		_column("Business Class", "asset_business_class"),
		_column("Branch", "branch"),
		_column("Department", "department"),
		_column("Location", "location"),
		_column("Custodian", "current_custodian"),
		_column("Gross Cost", "gross_cost", "Currency"),
		_column("Accumulated Depreciation", "accumulated_depreciation", "Currency"),
		_column("Net Book Value", "net_book_value", "Currency"),
		_column("Useful Life", "useful_life", "Int"),
		_column("Remaining Life", "remaining_life", "Int"),
		_column("Status", "status"),
	]
	return columns, rows


def _execute_capex_budget_utilization(filters: dict[str, Any]):
	conditions = ["1=1"]
	values: list[Any] = []
	for key, column in [
		("company", "company"),
		("fiscal_year", "fiscal_year"),
		("branch", "branch"),
		("department", "department"),
		("cost_center", "cost_center"),
		("asset_category", "asset_category"),
		("status", "status"),
	]:
		if filters.get(key):
			conditions.append(f"IFNULL(c.{column}, '') = %s")
			values.append(filters[key])
	if filters.get("from_date"):
		conditions.append("DATE(c.modified) >= %s")
		values.append(filters["from_date"])
	if filters.get("to_date"):
		conditions.append("DATE(c.modified) <= %s")
		values.append(filters["to_date"])
	rows = frappe.db.sql(
		f"""
		SELECT
			c.name AS capex_plan,
			c.company,
			c.fiscal_year,
			c.cost_center,
			c.department,
			c.branch,
			c.asset_category,
			c.approved_budget,
			c.committed_amount,
			c.actual_spent,
			c.remaining_budget,
			c.budget_utilization_percentage,
			c.budget_utilization_status,
			c.forecast_amount,
			CASE
				WHEN COALESCE(c.approved_budget, 0) = 0 THEN 0
				ELSE ROUND(((COALESCE(c.forecast_amount, 0) - COALESCE(c.approved_budget, 0)) / COALESCE(c.approved_budget, 1)) * 100, 2)
			END AS variance_pct,
			c.status
		FROM `tabFixed Asset CAPEX Plan` c
		WHERE { " AND ".join(conditions) }
		ORDER BY c.fiscal_year DESC, c.company, c.cost_center, c.asset_category
		""",
		values,
		as_dict=True,
	)
	columns = [
		_column("CAPEX Plan", "capex_plan"),
		_column("Company", "company"),
		_column("Fiscal Year", "fiscal_year"),
		_column("Cost Center", "cost_center"),
		_column("Department", "department"),
		_column("Branch", "branch"),
		_column("Asset Category", "asset_category"),
		_column("Approved Budget", "approved_budget", "Currency"),
		_column("Received, Not Billed", "committed_amount", "Currency"),
		_column("Billed Spend", "actual_spent", "Currency"),
		_column("Remaining Budget", "remaining_budget", "Currency"),
		_column("Budget Used (%)", "budget_utilization_percentage", "Percent"),
		_column("Budget Usage Status", "budget_utilization_status"),
		_column("Forecast Amount", "forecast_amount", "Currency"),
		_column("Variance %", "variance_pct", "Percent"),
		_column("Status", "status"),
	]
	return columns, rows


def _execute_acquisition_pipeline(filters: dict[str, Any]):
	where_sql, values = _asset_filter_sql(filters, alias="r")
	if filters.get("fiscal_year"):
		where_sql += " AND IFNULL(r.fiscal_year, '') = %s"
		values.append(filters["fiscal_year"])
	rows = frappe.db.sql(
		f"""
		SELECT
			r.name AS asset_request,
			r.request_title,
			r.company,
			r.fiscal_year,
			r.cost_center,
			r.capex_plan,
			r.approval_status,
			mr.name AS material_request,
			po.name AS purchase_order,
			pr.name AS purchase_receipt,
			pi.name AS purchase_invoice,
			a.name AS asset,
			a.available_for_use_date,
			a.capitalization_status,
			r.estimated_total_cost
		FROM `tabFixed Asset Request` r
		LEFT JOIN `tabMaterial Request` mr ON mr.asset_request = r.name
		LEFT JOIN `tabPurchase Order` po ON po.asset_request = r.name
		LEFT JOIN `tabPurchase Receipt` pr ON pr.asset_request = r.name
		LEFT JOIN `tabPurchase Invoice` pi ON pi.asset_request = r.name
		LEFT JOIN `tabAsset` a ON a.asset_request = r.name
		WHERE {where_sql}
		ORDER BY r.modified DESC
		""",
		values,
		as_dict=True,
	)
	columns = [
		_column("Asset Request", "asset_request"),
		_column("Request Title", "request_title"),
		_column("Company", "company"),
		_column("Fiscal Year", "fiscal_year"),
		_column("Cost Center", "cost_center"),
		_column("CAPEX Plan", "capex_plan"),
		_column("Approval Status", "approval_status"),
		_column("Material Request", "material_request"),
		_column("Purchase Order", "purchase_order"),
		_column("Purchase Receipt", "purchase_receipt"),
		_column("Purchase Invoice", "purchase_invoice"),
		_column("Asset", "asset"),
		_column("Available for Use Date", "available_for_use_date", "Date"),
		_column("Capitalization Status", "capitalization_status"),
		_column("Estimated Total Cost", "estimated_total_cost", "Currency"),
	]
	return columns, rows


def _execute_insurance_expiry(filters: dict[str, Any]):
	conditions = ["p.docstatus = 1"]
	values: list[Any] = []
	for key, column in [
		("asset", "a.name"),
		("policy_number", "p.policy_number"),
		("insurance_company", "p.insurance_company"),
		("policy_type", "p.policy_type"),
		("branch", "a.branch"),
		("department", "a.department"),
		("asset_category", "i.asset_category"),
		("custodian", "a.current_custodian"),
		("location", "COALESCE(a.asset_location, a.location)"),
	]:
		if filters.get(key):
			conditions.append(f"IFNULL({column}, '') = %s")
			values.append(filters[key])
	if filters.get("expires_within_days") not in (None, ""):
		conditions.append("DATEDIFF(p.coverage_end_date, CURDATE()) BETWEEN 0 AND %s")
		values.append(filters["expires_within_days"])
	if filters.get("from_date"):
		conditions.append("DATE(p.coverage_end_date) >= %s")
		values.append(filters["from_date"])
	if filters.get("to_date"):
		conditions.append("DATE(p.coverage_end_date) <= %s")
		values.append(filters["to_date"])
	rows = frappe.db.sql(
		f"""
		SELECT
			p.name AS policy,
			p.policy_number,
			p.policy_type,
			p.insurance_company,
			p.coverage_start_date,
			p.coverage_end_date,
			DATEDIFF(p.coverage_end_date, CURDATE()) AS days_remaining,
			COALESCE(i.insured_value, p.insured_value) AS insured_value,
			p.premium_amount,
			a.name AS asset,
			a.asset_name,
			a.asset_category,
			a.branch,
			a.department,
			COALESCE(a.asset_location, a.location) AS location,
			a.current_custodian,
			p.status
		FROM `tabAsset Insurance Policy` p
			LEFT JOIN `tabAsset Insurance Policy Item` i ON i.parent = p.name
		LEFT JOIN `tabAsset` a ON a.name = i.asset
		WHERE {" AND ".join(conditions)}
		ORDER BY p.coverage_end_date ASC, p.policy_number ASC
		""",
		values,
		as_dict=True,
	)
	columns = [
		_column("Policy", "policy"),
		_column("Policy Number", "policy_number"),
		_column("Policy Type", "policy_type"),
		_column("Insurer", "insurance_company"),
		_column("Asset", "asset"),
		_column("Asset Name", "asset_name"),
		_column("Asset Category", "asset_category"),
		_column("Coverage Start Date", "coverage_start_date", "Date"),
		_column("Coverage End Date", "coverage_end_date", "Date"),
		_column("Days Remaining", "days_remaining", "Int"),
		_column("Insured Value", "insured_value", "Currency"),
		_column("Premium", "premium_amount", "Currency"),
		_column("Branch", "branch"),
		_column("Department", "department"),
		_column("Location", "location"),
		_column("Custodian", "current_custodian"),
		_column("Status", "status"),
	]
	return columns, rows


def _execute_assets_without_custodian(filters: dict[str, Any]):
	where_sql, values = _asset_filter_sql(filters)
	rows = frappe.db.sql(
		f"""
		SELECT
			a.name AS asset,
			a.asset_name,
			a.asset_category,
			a.asset_business_class,
			a.branch,
			a.department,
			COALESCE(a.asset_location, a.location) AS location,
			a.status,
			a.operational_status
		FROM `tabAsset` a
		WHERE {where_sql}
		  AND IFNULL(a.current_custodian, '') = ''
		ORDER BY a.asset_category, a.asset_name
		""",
		values,
		as_dict=True,
	)
	return [
		_column("Asset", "asset"),
		_column("Asset Name", "asset_name"),
		_column("Asset Category", "asset_category"),
		_column("Business Class", "asset_business_class"),
		_column("Branch", "branch"),
		_column("Department", "department"),
		_column("Location", "location"),
		_column("Status", "status"),
		_column("Operational Status", "operational_status"),
	], rows


def _execute_asset_maintenance_due(filters: dict[str, Any]):
	conditions = ["p.docstatus < 2"]
	values: list[Any] = []
	for key, column in [("asset", "p.asset"), ("department", "p.responsible_department"), ("branch", "a.branch")]:
		if filters.get(key):
			conditions.append(f"IFNULL({column}, '') = %s")
			values.append(filters[key])
	if filters.get("from_date"):
		conditions.append("DATE(p.next_due_date) >= %s")
		values.append(filters["from_date"])
	if filters.get("to_date"):
		conditions.append("DATE(p.next_due_date) <= %s")
		values.append(filters["to_date"])
	rows = frappe.db.sql(
		f"""
		SELECT
			p.name AS maintenance_plan,
			p.asset,
			a.asset_name,
			p.maintenance_type,
			p.frequency,
			p.next_due_date,
			p.last_done_date,
			p.responsible_department,
			p.responsible_employee,
			p.estimated_cost,
			p.status
		FROM `tabAsset Maintenance Plan` p
		LEFT JOIN `tabAsset` a ON a.name = p.asset
		WHERE {" AND ".join(conditions)}
		  AND (p.next_due_date IS NULL OR DATEDIFF(p.next_due_date, CURDATE()) <= 30)
		ORDER BY p.next_due_date ASC, p.asset ASC
		""",
		values,
		as_dict=True,
	)
	return [
		_column("Maintenance Plan", "maintenance_plan"),
		_column("Asset", "asset"),
		_column("Asset Name", "asset_name"),
		_column("Maintenance Type", "maintenance_type"),
		_column("Frequency", "frequency"),
		_column("Next Due Date", "next_due_date", "Date"),
		_column("Last Done Date", "last_done_date", "Date"),
		_column("Responsible Department", "responsible_department"),
		_column("Responsible Employee", "responsible_employee"),
		_column("Estimated Cost", "estimated_cost", "Currency"),
		_column("Status", "status"),
	], rows


def _execute_asset_usage(filters: dict[str, Any]):
	conditions = ["u.docstatus < 2"]
	values: list[Any] = []
	for key, column in [("asset", "u.asset"), ("custodian", "a.current_custodian"), ("asset_category", "a.asset_category")]:
		if filters.get(key):
			conditions.append(f"IFNULL({column}, '') = %s")
			values.append(filters[key])
	if filters.get("from_date"):
		conditions.append("DATE(u.reading_date) >= %s")
		values.append(filters["from_date"])
	if filters.get("to_date"):
		conditions.append("DATE(u.reading_date) <= %s")
		values.append(filters["to_date"])
	rows = frappe.db.sql(
		f"""
		SELECT
			u.name AS usage_reading,
			u.asset,
			a.asset_name,
			a.asset_category,
			u.reading_date,
			u.reading_type,
			u.previous_reading,
			u.current_reading,
			u.usage_for_period,
			u.recorded_by,
			u.remarks
		FROM `tabAsset Usage Reading` u
		LEFT JOIN `tabAsset` a ON a.name = u.asset
		WHERE {" AND ".join(conditions)}
		ORDER BY u.reading_date DESC, u.creation DESC
		""",
		values,
		as_dict=True,
	)
	return [
		_column("Usage Reading", "usage_reading"),
		_column("Asset", "asset"),
		_column("Asset Name", "asset_name"),
		_column("Asset Category", "asset_category"),
		_column("Reading Date", "reading_date", "Date"),
		_column("Reading Type", "reading_type"),
		_column("Previous Reading", "previous_reading", "Float"),
		_column("Current Reading", "current_reading", "Float"),
		_column("Usage for Period", "usage_for_period", "Float"),
		_column("Recorded By", "recorded_by"),
		_column("Remarks", "remarks"),
	], rows


def _execute_cip_capitalization(filters: dict[str, Any]):
	conditions = ["c.docstatus < 2"]
	values: list[Any] = []
	if filters.get("company"):
		conditions.append("IFNULL(p.company, '') = %s")
		values.append(filters["company"])
	if filters.get("branch"):
		conditions.append("IFNULL(p.branch, '') = %s")
		values.append(filters["branch"])
	if filters.get("asset_category"):
		conditions.append("IFNULL(c.asset_category, '') = %s")
		values.append(filters["asset_category"])
	rows = frappe.db.sql(
		f"""
		SELECT
			c.name AS cip_request,
			c.project,
			p.company,
			c.capitalization_date,
			c.total_project_cost,
			c.amount_to_capitalize,
			c.asset_category,
			c.created_asset,
			c.finance_review_status,
			c.remarks
		FROM `tabCIP Capitalization Request` c
		LEFT JOIN `tabProject` p ON p.name = c.project
		WHERE {" AND ".join(conditions)}
		ORDER BY c.capitalization_date DESC, c.modified DESC
		""",
		values,
		as_dict=True,
	)
	return [
		_column("CIP Request", "cip_request"),
		_column("Project", "project"),
		_column("Company", "company"),
		_column("Capitalization Date", "capitalization_date", "Date"),
		_column("Total Project Cost", "total_project_cost", "Currency"),
		_column("Amount to Capitalize", "amount_to_capitalize", "Currency"),
		_column("Asset Category", "asset_category"),
		_column("Created Asset", "created_asset"),
		_column("Finance Review Status", "finance_review_status"),
		_column("Remarks", "remarks"),
	], rows


def _execute_capex_commitments(filters: dict[str, Any]):
	conditions = ["po.docstatus = 1", "COALESCE(po.per_billed, 0) < 100"]
	values: list[Any] = []
	if filters.get("company"):
		conditions.append("IFNULL(po.company, '') = %s")
		values.append(filters["company"])
	if filters.get("branch"):
		conditions.append("IFNULL(po.branch, '') = %s")
		values.append(filters["branch"])
	if filters.get("cost_center"):
		conditions.append("IFNULL(po.cost_center, '') = %s")
		values.append(filters["cost_center"])
	if filters.get("asset_category"):
		conditions.append("IFNULL(po.fixed_asset_category, '') = %s")
		values.append(filters["asset_category"])
	rows = frappe.db.sql(
		f"""
		SELECT
			po.name AS purchase_order,
			po.transaction_date,
			po.company,
			po.cost_center,
			po.asset_request,
			po.capex_plan,
			po.fixed_asset_category,
			po.base_grand_total,
			po.per_billed,
			po.status
		FROM `tabPurchase Order` po
		WHERE {" AND ".join(conditions)}
		ORDER BY po.transaction_date DESC, po.modified DESC
		""",
		values,
		as_dict=True,
	)
	return [
		_column("Purchase Order", "purchase_order"),
		_column("Transaction Date", "transaction_date", "Date"),
		_column("Company", "company"),
		_column("Cost Center", "cost_center"),
		_column("Asset Request", "asset_request"),
		_column("CAPEX Plan", "capex_plan"),
		_column("Asset Category", "fixed_asset_category"),
		_column("Base Grand Total", "base_grand_total", "Currency"),
		_column("% Billed", "per_billed", "Percent"),
		_column("Status", "status"),
	], rows


def _execute_disposal_register(filters: dict[str, Any]):
	where_sql, values = _asset_filter_sql(filters)
	rows = frappe.db.sql(
		f"""
		SELECT
			a.name AS asset,
			a.asset_name,
			a.asset_category,
			a.disposal_date,
			a.total_asset_cost,
			COALESCE(a.value_after_depreciation, 0) AS net_book_value,
			a.disposal_proceeds,
			COALESCE(a.disposal_proceeds, 0) - (a.total_asset_cost - COALESCE(a.value_after_depreciation, 0)) AS gain_loss,
			a.status
		FROM `tabAsset` a
		WHERE {where_sql}
		  AND a.disposal_date IS NOT NULL
		ORDER BY a.disposal_date DESC, a.asset_name
		""",
		values,
		as_dict=True,
	)
	return [
		_column("Asset", "asset"),
		_column("Asset Name", "asset_name"),
		_column("Asset Category", "asset_category"),
		_column("Disposal Date", "disposal_date", "Date"),
		_column("Gross Cost", "total_asset_cost", "Currency"),
		_column("NBV", "net_book_value", "Currency"),
		_column("Disposal Proceeds", "disposal_proceeds", "Currency"),
		_column("Gain/Loss", "gain_loss", "Currency"),
		_column("Status", "status"),
	], rows


def _execute_depreciation_schedule_summary(filters: dict[str, Any]):
	conditions = ["a.docstatus = 1"]
	values: list[Any] = []
	for key, column in [("company", "a.company"), ("branch", "a.branch"), ("department", "a.department"), ("asset_category", "a.asset_category"), ("cost_center", "a.cost_center")]:
		if filters.get(key):
			conditions.append(f"IFNULL({column}, '') = %s")
			values.append(filters[key])
	finance_book_filter = "AND IFNULL(schedule.finance_book, '') = %s" if filters.get("finance_book") else ""
	if filters.get("finance_book"):
		conditions.append("depreciation.asset IS NOT NULL")
		values.insert(0, filters["finance_book"])
	rows = frappe.db.sql(
		f"""
		SELECT
			a.asset_category,
			a.branch,
			a.department,
			a.cost_center,
			depreciation.finance_book,
			SUM(CASE WHEN a.calculate_depreciation = 1 AND depreciation.asset IS NULL THEN 1 ELSE 0 END) AS assets_missing_schedule,
			SUM(CASE WHEN a.calculate_depreciation = 0 THEN 1 ELSE 0 END) AS assets_not_depreciating,
			SUM(COALESCE(a.total_asset_cost, 0)) AS gross_cost,
			SUM(COALESCE(depreciation.posted_amount, 0)) AS posted_depreciation,
			SUM(COALESCE(depreciation.scheduled_amount, 0)) AS scheduled_depreciation,
			SUM(COALESCE(depreciation.due_amount, 0)) AS due_depreciation
		FROM `tabAsset` a
		LEFT JOIN (
			SELECT schedule.asset, schedule.finance_book,
				SUM(CASE WHEN entry.journal_entry IS NOT NULL THEN entry.depreciation_amount ELSE 0 END) AS posted_amount,
				SUM(entry.depreciation_amount) AS scheduled_amount,
				SUM(CASE WHEN entry.journal_entry IS NULL AND entry.schedule_date <= CURDATE()
					THEN entry.depreciation_amount ELSE 0 END) AS due_amount
			FROM `tabAsset Depreciation Schedule` schedule
			INNER JOIN `tabDepreciation Schedule` entry ON entry.parent = schedule.name
			WHERE schedule.docstatus = 1 {finance_book_filter}
			GROUP BY schedule.asset, schedule.finance_book
		) depreciation ON depreciation.asset = a.name
		WHERE {" AND ".join(conditions)}
		GROUP BY a.asset_category, a.branch, a.department, a.cost_center, depreciation.finance_book
		ORDER BY a.asset_category, a.branch, a.department, a.cost_center, depreciation.finance_book
		""",
		values,
		as_dict=True,
	)
	return [
		_column("Asset Category", "asset_category"),
		_column("Branch", "branch"),
		_column("Department", "department"),
		_column("Cost Center", "cost_center"),
		_column("Finance Book", "finance_book", "Link"),
		_column("Assets Missing Schedule", "assets_missing_schedule", "Int"),
		_column("Assets Not Depreciating", "assets_not_depreciating", "Int"),
		_column("Gross Cost", "gross_cost", "Currency"),
		_column("Posted Depreciation", "posted_depreciation", "Currency"),
		_column("Scheduled Depreciation", "scheduled_depreciation", "Currency"),
		_column("Due, Not Posted", "due_depreciation", "Currency"),
	], rows


def _execute_assets_missing_mandatory_documents(filters: dict[str, Any]):
	where_sql, values = _asset_filter_sql(filters)
	rows = frappe.db.sql(
		f"""
		SELECT
			a.name AS asset,
			a.asset_name,
			a.asset_category,
			a.branch,
			a.department,
			a.purchase_invoice,
			EXISTS (
				SELECT 1 FROM `tabAsset Insurance Policy Item` coverage
				JOIN `tabAsset Insurance Policy` policy ON policy.name = coverage.parent
				WHERE coverage.asset = a.name AND policy.docstatus = 1
				  AND policy.coverage_start_date <= CURDATE() AND policy.coverage_end_date >= CURDATE()
			) AS has_insurance,
			a.warranty_expiry_date,
			a.status
		FROM `tabAsset` a
		WHERE {where_sql}
		ORDER BY a.asset_category, a.asset_name
		""",
		values,
		as_dict=True,
	)
	output: list[dict[str, Any]] = []
	for row in rows:
		missing: list[str] = []
		if not row.get("purchase_invoice"):
			missing.append("Purchase Invoice")
		if not row.get("warranty_expiry_date"):
			missing.append("Warranty")
		if not row.get("has_insurance"):
			missing.append("Insurance")
		output.append({**row, "missing_documents": ", ".join(missing) if missing else ""})
	return [
		_column("Asset", "asset"),
		_column("Asset Name", "asset_name"),
		_column("Asset Category", "asset_category"),
		_column("Branch", "branch"),
		_column("Department", "department"),
		_column("Missing Documents", "missing_documents", "Data", 260),
		_column("Status", "status"),
	], output


def _execute_total_cost_of_ownership(filters: dict[str, Any]):
	where_sql, values = _asset_filter_sql(filters)
	rows = frappe.db.sql(
		f"""
		SELECT
			a.name AS asset,
			a.asset_name,
			a.asset_category,
			a.branch,
			a.department,
			COALESCE(a.total_asset_cost, 0) - COALESCE(a.additional_asset_cost, 0) AS acquisition_cost,
			COALESCE(a.additional_asset_cost, 0) AS capitalized_improvements,
			(
				SELECT COALESCE(SUM(m.estimated_cost), 0)
				FROM `tabAsset Maintenance Plan` m
				WHERE m.asset = a.name
			) AS maintenance_cost,
			(
				SELECT COALESCE(SUM(COALESCE(p.premium_amount, 0) / NULLIF((
					SELECT COUNT(*) FROM `tabAsset Insurance Policy Item` allocated
					WHERE allocated.parent = p.name
				), 0)), 0)
				FROM `tabAsset Insurance Policy` p
				INNER JOIN `tabAsset Insurance Policy Item` i ON i.parent = p.name
				WHERE i.asset = a.name
				  AND p.docstatus = 1
			) AS insurance_cost,
			(
				SELECT COALESCE(SUM(r.total_repair_cost), 0)
				FROM `tabAsset Repair` r
				WHERE r.asset = a.name
			) AS repair_cost,
			COALESCE(a.disposal_proceeds, 0) AS disposal_value,
			a.status
		FROM `tabAsset` a
		WHERE {where_sql}
		ORDER BY a.asset_category, a.asset_name
		""",
		values,
		as_dict=True,
	)
	for row in rows:
		row["total_cost_of_ownership"] = (
			flt(row.get("acquisition_cost"))
			+ flt(row.get("capitalized_improvements"))
			+ flt(row.get("maintenance_cost"))
			+ flt(row.get("insurance_cost"))
			+ flt(row.get("repair_cost"))
			- flt(row.get("disposal_value"))
		)
	return [
		_column("Asset", "asset"),
		_column("Asset Name", "asset_name"),
		_column("Asset Category", "asset_category"),
		_column("Branch", "branch"),
		_column("Department", "department"),
		_column("Acquisition Cost", "acquisition_cost", "Currency"),
		_column("Capitalized Improvements", "capitalized_improvements", "Currency"),
		_column("Maintenance Cost", "maintenance_cost", "Currency"),
		_column("Insurance Cost", "insurance_cost", "Currency"),
		_column("Repair Cost", "repair_cost", "Currency"),
		_column("Disposal Value", "disposal_value", "Currency"),
		_column("Total Cost of Ownership", "total_cost_of_ownership", "Currency", 170),
	], rows


def _execute_asset_replacement_forecast(filters: dict[str, Any]):
	where_sql, values = _asset_filter_sql(filters)
	rows = frappe.db.sql(
		f"""
		SELECT
			a.name AS asset,
			a.asset_name,
			a.asset_category,
			a.branch,
			a.department,
			a.current_custodian,
			a.condition_status,
			a.replacement_year,
			a.expected_replacement_cost,
			a.status
		FROM `tabAsset` a
		WHERE {where_sql}
		  AND a.replacement_year IS NOT NULL
		ORDER BY a.replacement_year ASC, a.asset_name
		""",
		values,
		as_dict=True,
	)
	current_year = getdate(nowdate()).year
	for row in rows:
		years_remaining = None
		if row.get("replacement_year"):
			years_remaining = int(row.replacement_year) - current_year
		row["years_remaining"] = years_remaining
		row["forecast_horizon"] = "1 Year" if years_remaining is not None and years_remaining <= 1 else "3 Years" if years_remaining is not None and years_remaining <= 3 else "5 Years" if years_remaining is not None and years_remaining <= 5 else "Beyond 5 Years"
	return [
		_column("Asset", "asset"),
		_column("Asset Name", "asset_name"),
		_column("Asset Category", "asset_category"),
		_column("Branch", "branch"),
		_column("Department", "department"),
		_column("Custodian", "current_custodian"),
		_column("Condition", "condition_status"),
		_column("Replacement Year", "replacement_year", "Int"),
		_column("Years Remaining", "years_remaining", "Int"),
		_column("Forecast Horizon", "forecast_horizon"),
		_column("Expected Replacement Cost", "expected_replacement_cost", "Currency"),
		_column("Status", "status"),
	], rows


def _execute_warranty_expiry(filters: dict[str, Any]):
	where_sql, values = _asset_filter_sql(filters)
	rows = frappe.db.sql(
		f"""
		SELECT
			a.name AS asset,
			a.asset_name,
			a.asset_category,
			a.branch,
			a.department,
			COALESCE(a.asset_location, a.location) AS location,
			a.warranty_expiry_date,
			DATEDIFF(a.warranty_expiry_date, CURDATE()) AS days_remaining,
			a.status
		FROM `tabAsset` a
		WHERE {where_sql}
		  AND a.warranty_expiry_date IS NOT NULL
		ORDER BY a.warranty_expiry_date ASC, a.asset_name
		""",
		values,
		as_dict=True,
	)
	return [
		_column("Asset", "asset"),
		_column("Asset Name", "asset_name"),
		_column("Asset Category", "asset_category"),
		_column("Branch", "branch"),
		_column("Department", "department"),
		_column("Location", "location"),
		_column("Warranty Expiry Date", "warranty_expiry_date", "Date"),
		_column("Days Remaining", "days_remaining", "Int"),
		_column("Status", "status"),
	], rows


def _execute_uninsured_assets(filters: dict[str, Any]):
	where_sql, values = _asset_filter_sql(filters)
	rows = frappe.db.sql(
		f"""
		SELECT
			a.name AS asset,
			a.asset_name,
			a.asset_category,
			a.branch,
			a.department,
			COALESCE(a.asset_location, a.location) AS location,
			a.current_custodian,
			a.insurance_required,
			a.status
		FROM `tabAsset` a
		WHERE {where_sql}
		  AND a.docstatus = 1
		  AND a.status NOT IN ('Sold', 'Scrapped')
		  AND IFNULL(a.insurance_required, 0) = 1
			  AND NOT EXISTS (
				SELECT 1
				FROM `tabAsset Insurance Policy Item` covered
				INNER JOIN `tabAsset Insurance Policy` policy ON policy.name = covered.parent
				WHERE covered.asset = a.name
			  AND policy.docstatus = 1
			  AND policy.coverage_start_date <= CURDATE()
			  AND policy.coverage_end_date >= CURDATE()
		  )
		ORDER BY a.asset_category, a.asset_name
		""",
		values,
		as_dict=True,
	)
	return [
		_column("Asset", "asset"),
		_column("Asset Name", "asset_name"),
		_column("Asset Category", "asset_category"),
		_column("Branch", "branch"),
		_column("Department", "department"),
		_column("Location", "location"),
		_column("Custodian", "current_custodian"),
		_column("Insurance Required", "insurance_required"),
		_column("Status", "status"),
	], rows


def execute_report(report_key: str, filters: dict[str, Any] | None = None):
	filters = filters or {}
	if report_key == "enhanced_fixed_asset_register":
		return _execute_asset_register(filters)
	if report_key == "capex_budget_utilization":
		return _execute_capex_budget_utilization(filters)
	if report_key == "asset_acquisition_pipeline":
		return _execute_acquisition_pipeline(filters)
	if report_key == "insurance_expiry_report":
		return _execute_insurance_expiry(filters)
	if report_key == "assets_without_custodian_report":
		return _execute_assets_without_custodian(filters)
	if report_key == "asset_maintenance_due_report":
		return _execute_asset_maintenance_due(filters)
	if report_key == "asset_usage_report":
		return _execute_asset_usage(filters)
	if report_key == "cip_capitalization_report":
		return _execute_cip_capitalization(filters)
	if report_key == "capex_commitments_report":
		return _execute_capex_commitments(filters)
	if report_key == "asset_disposal_register":
		return _execute_disposal_register(filters)
	if report_key == "depreciation_schedule_summary":
		return _execute_depreciation_schedule_summary(filters)
	if report_key == "assets_missing_mandatory_documents_report":
		return _execute_assets_missing_mandatory_documents(filters)
	if report_key == "total_cost_of_ownership_report":
		return _execute_total_cost_of_ownership(filters)
	if report_key == "asset_replacement_forecast_report":
		return _execute_asset_replacement_forecast(filters)
	if report_key == "warranty_expiry_report":
		return _execute_warranty_expiry(filters)
	if report_key == "uninsured_assets_report":
		return _execute_uninsured_assets(filters)
	frappe.throw(_("Unsupported fixed asset report: {0}").format(report_key))
