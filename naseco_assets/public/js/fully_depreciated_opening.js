const OPENING_DEFAULTS_METHOD = "naseco_assets.naseco_assets.fully_depreciated_opening.get_category_residual_choices";

async function get_opening_residual_choices(frm) {
	if (!frm.doc.asset_category || !flt(frm.doc.net_purchase_amount)) {
		frappe.msgprint(__("Select an Asset Category and enter Net Purchase Amount first."));
		return [];
	}
	const response = await frappe.call({
		method: OPENING_DEFAULTS_METHOD,
		args: {
			asset_category: frm.doc.asset_category,
			net_purchase_amount: frm.doc.net_purchase_amount,
		},
	});
	return response.message || [];
}

async function apply_category_opening(frm) {
	const category = frm.doc.asset_category;
	const cost = flt(frm.doc.net_purchase_amount);
	const choices = await get_opening_residual_choices(frm);
	if (!choices.length) return;
	if (frm.doc.asset_category !== category || flt(frm.doc.net_purchase_amount) !== cost) return;
	if (flt(frm.doc.additional_asset_cost)) {
		await set_opening_mode(frm, "Manual Override");
		frappe.msgprint(__("Additional Asset Cost needs a reviewed Manual Override for opening depreciation."));
		return;
	}

	const selected = choices.find((row) => row.finance_book === frm.doc.naseco_opening_finance_book);
	const choice = selected || (choices.length === 1 ? choices[0] : null);
	if (!choice) {
		await set_opening_mode(frm, "Category Default");
		frappe.msgprint(__("Select an Opening Finance Book before calculating opening depreciation."));
		return;
	}
	if (choice.residual < 0 || choice.residual >= flt(frm.doc.net_purchase_amount)) {
		await set_opening_mode(frm, "Manual Override");
		frappe.msgprint(__("The category residual must be below the Asset purchase cost. Choose Manual Override if Finance has approved a different value."));
		return;
	}

	await set_opening_mode(frm, "Category Default");
	await frm.set_value({
		naseco_opening_finance_book: choice.finance_book || null,
		naseco_opening_residual_value: choice.residual,
		opening_accumulated_depreciation: flt(frm.doc.net_purchase_amount) - choice.residual,
	});
	frappe.show_alert({ message: __("Opening depreciation calculated. Review the amounts before saving."), indicator: "blue" });
}

async function set_opening_mode(frm, source) {
	frm.__naseco_opening_updating = true;
	try {
		await frm.set_value("calculate_depreciation", 0);
		await frm.set_value("is_fully_depreciated", 1);
		await frm.set_value("naseco_opening_residual_source", source);
	} finally {
		frm.__naseco_opening_updating = false;
	}
}

function refresh_manual_opening_amount(frm) {
	if (frm.doc.naseco_opening_residual_source !== "Manual Override") return;
	const cost = flt(frm.doc.net_purchase_amount) + flt(frm.doc.additional_asset_cost);
	const residual = flt(frm.doc.naseco_opening_residual_value);
	if (cost > 0 && residual >= 0 && residual < cost) {
		frm.set_value("opening_accumulated_depreciation", cost - residual);
	}
}

function refresh_category_opening(frm) {
	if (frm.__naseco_opening_updating || frm.doc.docstatus !== 0 || !frm.doc.is_fully_depreciated) return;
	if (frm.doc.naseco_opening_residual_source !== "Category Default") return;
	if (frm.doc.asset_category && flt(frm.doc.net_purchase_amount)) apply_category_opening(frm);
}

function toggle_import_button(frm) {
	const label = __("Import as Fully Depreciated");
	if (frm.doc.docstatus === 0 && frm.doc.asset_type === "Existing Asset") {
		if (!frm.custom_buttons?.[label]) {
			frm.add_custom_button(label, () => apply_category_opening(frm), __("Actions"));
		}
	} else {
		frm.remove_custom_button(label, __("Actions"));
	}
}

frappe.ui.form.on("Asset", {
	refresh: toggle_import_button,
	asset_type: toggle_import_button,
	async is_fully_depreciated(frm) {
		if (frm.__naseco_opening_updating || frm.doc.docstatus !== 0 || !frm.doc.is_fully_depreciated) return;
		if (frm.doc.asset_type !== "Existing Asset" || frm.doc.naseco_opening_residual_source === "Manual Override") return;
		await apply_category_opening(frm);
	},
	naseco_opening_residual_source(frm) {
		if (frm.__naseco_opening_updating) return;
		if (frm.doc.naseco_opening_residual_source === "Manual Override") {
			refresh_manual_opening_amount(frm);
		} else {
			refresh_category_opening(frm);
		}
	},
	naseco_opening_finance_book: refresh_category_opening,
	asset_category: refresh_category_opening,
	net_purchase_amount(frm) {
		refresh_category_opening(frm);
		refresh_manual_opening_amount(frm);
	},
	naseco_opening_residual_value: refresh_manual_opening_amount,
	additional_asset_cost: refresh_manual_opening_amount,
});
