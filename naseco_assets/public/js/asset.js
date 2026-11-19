const CREATE_GROUP = __("Create");
const MANAGE_GROUP = __("Manage");

function add_button_if_missing(frm, label, handler, group) {
	const translated_label = __(label);
	if (frm.custom_buttons && frm.custom_buttons[translated_label]) {
		return;
	}

	frm.add_custom_button(translated_label, handler, group);
}

async function apply_residual_basis_on_form(frm, row) {
	if (frm.doc.docstatus !== 0) return;
	if (row.naseco_residual_value_basis === "Percentage") {
		await frappe.model.set_value(row.doctype, row.name, "expected_value_after_useful_life",
			flt(frm.doc.net_purchase_amount) * flt(row.salvage_value_percentage) / 100);
	} else if (row.naseco_residual_value_basis === "Fixed Amount" && frm.doc.asset_category) {
		const category = await frappe.db.get_value("Asset Category", frm.doc.asset_category, "naseco_default_residual_value");
		await frappe.model.set_value(row.doctype, row.name, "expected_value_after_useful_life",
			flt(category.message?.naseco_default_residual_value));
	}
	frm.refresh_field("finance_books");
}

function route_to_doclist(message) {
	const doclist = frappe.model.sync(message);
	frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
}

function add_create_buttons(frm) {
	add_button_if_missing(frm, "Create Insurance Coverage", () => show_insurance_coverage_dialog(frm), CREATE_GROUP);

	add_button_if_missing(frm, "Create Maintenance Plan", () => {
		frappe.new_doc("Asset Maintenance Plan", {
			asset: frm.doc.name,
			responsible_department: frm.doc.department,
		});
	}, CREATE_GROUP);

	add_button_if_missing(frm, "Record Usage Reading", () => {
		frappe.new_doc("Asset Usage Reading", { asset: frm.doc.name });
	}, CREATE_GROUP);

}

async function show_current_insurance_coverage(frm) {
	const assetName = frm.doc.name;
	for (const field of ["current_insurance_policy", "policy_number", "insurance_policy_type", "insurer", "insurance_start_date", "insurance_end_date"]) {
		if (frm.fields_dict[field]) frm.toggle_display(field, true);
	}
	const response = await frappe.call({
		type: "GET",
		method: "naseco_assets.naseco_assets.doctype.asset_insurance_policy.asset_insurance_policy.get_current_coverage",
		args: { asset: assetName },
	});
	if (frm.doc.name !== assetName) return;
	const policy = response.message;
	const values = {
		current_insurance_policy: policy?.name || null,
		policy_number: policy?.policy_number || null,
		insurance_policy_type: policy?.policy_type || null,
		insurer: policy?.insurance_company || null,
		insured_value: policy?.insured_value ?? null,
		insurance_start_date: policy?.coverage_start_date || null,
		insurance_end_date: policy?.coverage_end_date || null,
	};
	for (const [field, value] of Object.entries(values)) {
		if (frm.fields_dict[field]) {
			frm.doc[field] = value;
			frm.refresh_field(field);
		}
	}
	if (policy) {
		const label = __("Insured until {0} under {1}", [policy.coverage_end_date, policy.policy_number]);
		frm.dashboard.add_comment(frappe.utils.escape_html(label), "green", true);
	} else if (frm.doc.insurance_required) {
		frm.dashboard.add_comment(__("No confirmed insurance coverage is effective today."), "orange", true);
	}
}

async function show_insurance_coverage_dialog(frm) {
	const method = "naseco_assets.naseco_assets.doctype.asset_insurance_policy.asset_insurance_policy";
	const response = await frappe.call({
		type: "GET",
		method: `${method}.get_eligible_policies`,
		args: { asset: frm.doc.name },
	});
	const policies = response.message || [];
	const allowed = new Set(policies.map((policy) => policy.name));
	const dialog = new frappe.ui.Dialog({
		title: __("Create Insurance Coverage"),
		fields: [
			{ fieldname: "asset", fieldtype: "Data", label: __("Asset"), default: frm.doc.name, read_only: 1 },
			{ fieldname: "asset_category", fieldtype: "Data", label: __("Asset Category"), default: frm.doc.asset_category || "", read_only: 1 },
			{
				fieldname: "insurance_policy", fieldtype: "Link", label: __("Insurance Policy"),
				options: "Asset Insurance Policy", reqd: 1,
				get_query: () => ({ filters: { name: ["in", [...allowed]] } }),
				onchange: () => {
					const policy = policies.find((item) => item.name === dialog.get_value("insurance_policy"));
					const details = policy
						? __("Insurer: {0} | Coverage: {1} to {2}", [policy.insurance_company, policy.coverage_start_date, policy.coverage_end_date])
						: __("Select a confirmed policy. Its insurer and dates will apply to this asset.");
					dialog.fields_dict.policy_help.$wrapper.text(details);
				},
			},
			{
				fieldname: "policy_help", fieldtype: "HTML",
				options: `<p class="text-muted">${__("Select a confirmed policy. Its insurer and dates will apply to this asset.")}</p>`,
			},
		],
				primary_action_label: __("Add Coverage"),
		primary_action: async (values) => {
			if (!allowed.has(values.insurance_policy)) {
				frappe.msgprint(__("Choose a confirmed policy for this asset category."));
				return;
			}
			const created = await frappe.call({
				type: "POST", method: `${method}.add_asset_coverage`,
				args: { asset: frm.doc.name, insurance_policy: values.insurance_policy },
			});
			dialog.hide();
			frappe.set_route("Form", "Asset Insurance Policy", created.message);
		},
	});
	dialog.set_secondary_action(() => {
		dialog.hide();
		frappe.new_doc("Asset Insurance Policy", {
			coverage_basis: "Selected Assets",
			asset_category: frm.doc.asset_category,
		});
		frappe.show_alert(__("Save and confirm the policy, then return to this asset to create coverage."));
	});
	dialog.set_secondary_action_label(__("Create New Policy"));
	dialog.show();
}

function get_asset_sale_summary(frm, values = {}) {
	return frappe.call({
		type: "GET",
		method: "naseco_assets.naseco_assets.api.get_asset_sale_summary",
		args: {
			asset_name: frm.doc.name,
			posting_date: values.posting_date || frappe.datetime.get_today(),
			finance_book: values.finance_book || undefined,
			sell_qty: values.sell_qty || frm.doc.asset_quantity || 1,
		},
	});
}

async function refresh_asset_sale_value(frm, dialog) {
	if (!dialog.asset_sale_summary) {
		return;
	}

	const values = dialog.get_values(true);
	if (!values.posting_date || !values.sell_qty) {
		return;
	}

	const previous_suggestion = dialog.last_suggested_selling_price;
	const response = await get_asset_sale_summary(frm, values);
	const summary = response.message;
	dialog.asset_sale_summary = summary;
	dialog.set_value("net_book_value", summary.net_book_value);

	const current_price = dialog.get_value("selling_price");
	if (current_price === undefined || current_price === null || current_price === previous_suggestion) {
		dialog.set_value("selling_price", summary.suggested_selling_price);
	}
	dialog.last_suggested_selling_price = summary.suggested_selling_price;
}

function create_sales_invoice(frm) {
	let dialog;

	const refresh_value = () => refresh_asset_sale_value(frm, dialog);
	dialog = new frappe.ui.Dialog({
		title: __("Sell Asset"),
		size: "large",
		fields: [
			{
				fieldname: "valuation_status",
				fieldtype: "HTML",
				options: `<div class="text-muted">${__("Loading asset valuation...")}</div>`,
			},
			{
				fieldname: "buyer_type",
				fieldtype: "Select",
				label: __("Buyer Type"),
				options: ["Customer", "Employee"].join("\n"),
				default: "Customer",
				reqd: 1,
			},
			{
				fieldname: "customer",
				fieldtype: "Link",
				label: __("Customer / Other Party"),
				options: "Customer",
				depends_on: 'eval:doc.buyer_type == "Customer"',
				mandatory_depends_on: 'eval:doc.buyer_type == "Customer"',
				description: __("External and other buyers must be represented by a Customer record."),
			},
			{
				fieldname: "employee",
				fieldtype: "Link",
				label: __("Employee"),
				options: "Employee",
				depends_on: 'eval:doc.buyer_type == "Employee"',
				mandatory_depends_on: 'eval:doc.buyer_type == "Employee"',
				description: __("The Employee must have a Sales Invoice Customer configured."),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "posting_date",
				fieldtype: "Date",
				label: __("Sale Date"),
				default: frappe.datetime.get_today(),
				reqd: 1,
				change: refresh_value,
			},
			{
				fieldname: "sell_qty",
				fieldtype: "Int",
				label: __("Sell Quantity"),
				default: frm.doc.asset_quantity || 1,
				reqd: 1,
				change: refresh_value,
			},
			{
				fieldname: "finance_book",
				fieldtype: "Select",
				label: __("Finance Book"),
				options: "",
				change: refresh_value,
			},
			{ fieldtype: "Section Break", label: __("Valuation") },
			{
				fieldname: "net_book_value",
				fieldtype: "Currency",
				label: __("Net Book Value for Quantity"),
				read_only: 1,
			},
			{
				fieldname: "selling_price",
				fieldtype: "Currency",
				label: __("Total Selling Price"),
				reqd: 1,
				description: __("Defaults to net book value. Change it to record a gain or loss on disposal."),
			},
		],
		primary_action_label: __("Create Sales Invoice"),
		primary_action(values) {
			const summary = dialog.asset_sale_summary;
			if (!summary) {
				frappe.throw(__("Wait for the asset valuation to finish loading."));
			}

			if (flt(values.sell_qty) <= 0 || flt(values.sell_qty) > flt(summary.asset_quantity)) {
				frappe.throw(__("Sell quantity must be greater than zero and cannot exceed {0}.", [summary.asset_quantity]));
			}

			frappe.call({
				method: "naseco_assets.naseco_assets.api.make_sales_invoice_for_asset_sale",
				args: {
					asset_name: frm.doc.name,
					posting_date: values.posting_date,
					finance_book: values.finance_book || undefined,
					sell_qty: values.sell_qty,
					selling_price: values.selling_price,
					customer: values.buyer_type === "Customer" ? values.customer : undefined,
					employee: values.buyer_type === "Employee" ? values.employee : undefined,
				},
				freeze: 1,
				freeze_message: __("Preparing Sales Invoice..."),
				callback(r) {
					dialog.hide();
					route_to_doclist(r.message);
				},
			});
		},
	});
	dialog.show();
	dialog.get_primary_btn().prop("disabled", true);

	get_asset_sale_summary(frm)
		.then((response) => {
			const summary = response.message;
			dialog.asset_sale_summary = summary;
			dialog.last_suggested_selling_price = summary.suggested_selling_price;
			dialog.fields_dict.valuation_status.$wrapper.empty();
			dialog.set_df_property("finance_book", "options", ["", ...summary.finance_books].join("\n"));
			dialog.set_df_property("net_book_value", "options", summary.currency);
			dialog.set_df_property("selling_price", "options", summary.currency);
			dialog.set_value("finance_book", summary.default_finance_book);
			dialog.set_value("net_book_value", summary.net_book_value);
			dialog.set_value("selling_price", summary.suggested_selling_price);
			dialog.get_primary_btn().prop("disabled", false);
		})
		.catch(() => {
			dialog.fields_dict.valuation_status.$wrapper.html(
				`<div class="text-danger">${__("Could not load the asset valuation. Close this dialog and try again.")}</div>`
			);
		});
}

function create_asset_maintenance(frm) {
	frappe.call({
		method: "erpnext.assets.doctype.asset.asset.create_asset_maintenance",
		args: {
			asset: frm.doc.name,
			item_code: frm.doc.item_code,
			item_name: frm.doc.item_name,
			asset_category: frm.doc.asset_category,
			company: frm.doc.company,
		},
		callback(r) {
			route_to_doclist(r.message);
		},
	});
}

function create_asset_repair(frm) {
	frappe.call({
		method: "erpnext.assets.doctype.asset.asset.create_asset_repair",
		args: {
			company: frm.doc.company,
			asset: frm.doc.name,
			asset_name: frm.doc.asset_name,
		},
		callback(r) {
			route_to_doclist(r.message);
		},
	});
}

function create_asset_value_adjustment(frm) {
	frappe.call({
		method: "erpnext.assets.doctype.asset.asset.create_asset_value_adjustment",
		args: {
			asset: frm.doc.name,
			asset_category: frm.doc.asset_category,
			company: frm.doc.company,
		},
		freeze: 1,
		callback(r) {
			route_to_doclist(r.message);
		},
	});
}

function create_depreciation_entry(frm) {
	frappe.call({
		method: "erpnext.assets.doctype.asset.asset.make_journal_entry",
		args: {
			asset_name: frm.doc.name,
		},
		callback(r) {
			route_to_doclist(r.message);
		},
	});
}

function transfer_asset(frm) {
	frappe.call({
		method: "erpnext.assets.doctype.asset.asset.make_asset_movement",
		freeze: true,
		args: {
			assets: [{ name: frm.doc.name }],
			purpose: "Transfer",
		},
		callback(r) {
			route_to_doclist(r.message);
		},
	});
}

function scrap_asset(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Enter date to scrap asset"),
		fields: [
			{
				label: __("Select the date"),
				fieldname: "scrap_date",
				fieldtype: "Date",
				reqd: 1,
			},
		],
		size: "medium",
		primary_action_label: "Submit",
		primary_action(values) {
			frappe.call({
				method: "erpnext.assets.doctype.asset.depreciation.scrap_asset",
				args: {
					asset_name: frm.doc.name,
					scrap_date: values.scrap_date,
				},
				callback() {
					frm.reload_doc();
					dialog.hide();
				},
			});
		},
	});

	dialog.show();
}

function restore_asset(frm) {
	frappe.confirm(__("Do you really want to restore this scrapped asset?"), () => {
		frappe.call({
			method: "erpnext.assets.doctype.asset.depreciation.restore_asset",
			args: {
				asset_name: frm.doc.name,
			},
			callback() {
				frm.reload_doc();
			},
		});
	});
}

function split_asset(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Split Asset"),
		fields: [
			{
				fieldname: "split_qty",
				fieldtype: "Int",
				label: __("Split Qty"),
				reqd: 1,
			},
		],
	});

	dialog.set_primary_action(__("Split"), () => {
		const dialog_data = dialog.get_values();
		frappe.call({
			method: "erpnext.assets.doctype.asset.asset.split_asset",
			args: {
				asset_name: frm.doc.name,
				split_qty: cint(dialog_data.split_qty),
			},
			callback(r) {
				route_to_doclist(r.message);
			},
		});

		dialog.hide();
	});

	dialog.show();
}

function view_general_ledger(frm) {
	frappe.route_options = {
		voucher_no: frm.doc.name,
		from_date: frm.doc.available_for_use_date,
		to_date: frm.doc.available_for_use_date,
		company: frm.doc.company,
	};
	frappe.set_route("query-report", "General Ledger");
}

function add_native_asset_actions(frm) {
	if (frm.doc.docstatus == 1) {
		if (["Submitted", "Partially Depreciated", "Fully Depreciated"].includes(frm.doc.status)) {
			add_button_if_missing(frm, "Transfer Asset", () => transfer_asset(frm), MANAGE_GROUP);
			add_button_if_missing(frm, "Scrap Asset", () => scrap_asset(frm), MANAGE_GROUP);
		} else if (frm.doc.status == "Scrapped") {
			add_button_if_missing(frm, "Restore Asset", () => restore_asset(frm), MANAGE_GROUP);
		}

		if (frm.doc.maintenance_required && !frm.doc.maintenance_schedule) {
			add_button_if_missing(frm, "Maintain Asset", () => create_asset_maintenance(frm), MANAGE_GROUP);
		}

		add_button_if_missing(frm, "Repair Asset", () => create_asset_repair(frm), MANAGE_GROUP);
		add_button_if_missing(frm, "Split Asset", () => split_asset(frm), MANAGE_GROUP);

		if (frm.doc.status != "Fully Depreciated") {
			add_button_if_missing(frm, "Adjust Asset Value", () => create_asset_value_adjustment(frm), MANAGE_GROUP);
		}

		if (!frm.doc.calculate_depreciation) {
			add_button_if_missing(frm, "Create Depreciation Entry", () => create_depreciation_entry(frm), MANAGE_GROUP);
		}

		if (frm.doc.purchase_receipt || !frm.doc.is_existing_asset) {
			add_button_if_missing(frm, "View General Ledger", () => view_general_ledger(frm), MANAGE_GROUP);
		}
	}
}

function replace_sell_asset_action(frm) {
	if (frm.doc.docstatus !== 1 || !["Submitted", "Partially Depreciated", "Fully Depreciated"].includes(frm.doc.status)) {
		return;
	}

	frm.remove_custom_button(__("Sell Asset"), __("Actions"));
	frm.add_custom_button(__("Sell Asset"), () => create_sales_invoice(frm), __("Actions"));
}

frappe.ui.form.on("Asset", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		add_create_buttons(frm);
		show_current_insurance_coverage(frm);
		add_native_asset_actions(frm);
		replace_sell_asset_action(frm);
	},
});

frappe.ui.form.on("Asset Finance Book", {
	naseco_residual_value_basis(frm, cdt, cdn) {
		apply_residual_basis_on_form(frm, locals[cdt][cdn]);
	},
});
