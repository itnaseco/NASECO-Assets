function set_request_defaults(frm) {
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

function auto_link_capex_plan(frm) {
	if (frm.doc.capex_plan || !frm.doc.asset_category || !frm.doc.cost_center || !frm.doc.company || !frm.doc.fiscal_year) {
		return;
	}

	frappe.call({
		method: "naseco_assets.naseco_assets.api.find_capex_plan",
		args: {
			company: frm.doc.company,
			fiscal_year: frm.doc.fiscal_year,
			cost_center: frm.doc.cost_center,
			asset_category: frm.doc.asset_category,
		},
		callback(r) {
			if (r.message && r.message.name && frm.doc.capex_plan !== r.message.name) {
				frm.set_value("capex_plan", r.message.name);
			}
		},
	});
}

frappe.ui.form.on("Fixed Asset Request", {
	refresh(frm) {
		set_request_defaults(frm);
		auto_link_capex_plan(frm);

		if (frm.doc.docstatus === 1 && !frm.doc.linked_material_request) {
			frm.add_custom_button(__("Create Material Request"), () => {
				frappe.call({
					method: "naseco_assets.naseco_assets.api.create_material_request",
					args: {
						request_name: frm.doc.name,
					},
					callback(r) {
						if (r.message && r.message.name) {
							frm.reload_doc();
							frappe.msgprint(__("Material Request {0} created.", [r.message.name]));
						}
					},
				});
			});
		}
	},
	company: auto_link_capex_plan,
	fiscal_year: auto_link_capex_plan,
	cost_center: auto_link_capex_plan,
	asset_category: auto_link_capex_plan,
	requesting_employee(frm) {
		set_request_defaults(frm);
		auto_link_capex_plan(frm);
	},
});
