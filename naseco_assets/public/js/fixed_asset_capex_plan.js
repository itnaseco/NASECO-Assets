const REVISION_STATUSES = ["Draft", "Returned for Revision"];
const REVIEW_STATUS = "Pending Review";
const FINAL_STATUSES = ["Approved", "Frozen", "Closed"];
const IDENTITY_FIELDS = ["company", "fiscal_year", "department", "branch", "cost_center", "asset_category"];
const REVISION_FIELDS = ["forecast_amount", "notes"];
const READ_ONLY_TOTAL_FIELDS = [
	"committed_amount",
	"actual_spent",
	"remaining_budget",
	"budget_utilization_percentage",
	"budget_utilization_status",
];

function set_capex_plan_defaults(frm) {
	if (!frm.doc.company) {
		const company = frappe.defaults.get_user_default("Company");
		if (company) {
			frm.set_value("company", company);
		}
	}

	if (!frm.doc.fiscal_year && window.erpnext?.utils?.get_fiscal_year) {
		const fiscalYear = erpnext.utils.get_fiscal_year(frappe.datetime.get_today());
		if (fiscalYear) {
			frm.set_value("fiscal_year", fiscalYear);
		}
	}
}

function has_role(role) {
	return frappe.user?.has_role?.(role) || false;
}

function is_system_user() {
	return has_role("System Manager");
}

function set_field_read_only(frm, fieldname, is_read_only) {
	frm.set_df_property(fieldname, "read_only", is_read_only ? 1 : 0);
}

function refresh_fields(frm) {
	[...IDENTITY_FIELDS, ...REVISION_FIELDS, ...READ_ONLY_TOTAL_FIELDS].forEach((fieldname) => {
		frm.refresh_field(fieldname);
	});
}

function apply_field_rules(frm) {
	const status = frm.doc.status || "Draft";
	const revision_state = REVISION_STATUSES.includes(status);
	const review_state = status === REVIEW_STATUS;
	const final_state = FINAL_STATUSES.includes(status);

	if (revision_state) {
		const can_edit_revision = has_role("Asset Administrator") || is_system_user();
		IDENTITY_FIELDS.forEach((fieldname) => set_field_read_only(frm, fieldname, !can_edit_revision));
		set_field_read_only(frm, "forecast_amount", !can_edit_revision);
		set_field_read_only(frm, "notes", !can_edit_revision);
		set_field_read_only(frm, "approved_budget", true);
	} else if (review_state) {
		const can_edit_review = has_role("Finance Manager") || is_system_user();
		IDENTITY_FIELDS.forEach((fieldname) => set_field_read_only(frm, fieldname, true));
		set_field_read_only(frm, "forecast_amount", true);
		set_field_read_only(frm, "notes", true);
		set_field_read_only(frm, "approved_budget", !can_edit_review);
	} else if (final_state) {
		IDENTITY_FIELDS.forEach((fieldname) => set_field_read_only(frm, fieldname, true));
		set_field_read_only(frm, "approved_budget", true);
		set_field_read_only(frm, "forecast_amount", true);
		set_field_read_only(frm, "notes", true);
	} else {
		IDENTITY_FIELDS.forEach((fieldname) => set_field_read_only(frm, fieldname, true));
		set_field_read_only(frm, "approved_budget", true);
		set_field_read_only(frm, "forecast_amount", true);
		set_field_read_only(frm, "notes", true);
	}

	READ_ONLY_TOTAL_FIELDS.forEach((fieldname) => set_field_read_only(frm, fieldname, true));
	refresh_fields(frm);
}

frappe.ui.form.on("Fixed Asset CAPEX Plan", {
	refresh(frm) {
		set_capex_plan_defaults(frm);
		apply_field_rules(frm);
	},
	status(frm) {
		apply_field_rules(frm);
	},
	company: set_capex_plan_defaults,
	fiscal_year: set_capex_plan_defaults,
	cost_center: set_capex_plan_defaults,
});
