from __future__ import annotations

import frappe

from naseco_assets.naseco_assets.lifecycle import refresh_capex_plan_totals


def execute() -> None:
	for plan_name in frappe.get_all("Fixed Asset CAPEX Plan", pluck="name"):
		refresh_capex_plan_totals(plan_name)
