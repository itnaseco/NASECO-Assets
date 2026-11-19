function escape_html(value) {
	return frappe.utils.escape_html(String(value || ""));
}

function format_asset_value(asset, fieldname) {
	if (asset[fieldname] === null || asset[fieldname] === undefined) {
		return "—";
	}

	return format_currency(
		asset[fieldname],
		asset.currency || frappe.boot.sysdefaults.currency,
	);
}

function format_sale_value(sale, fieldname) {
	if (sale[fieldname] === null || sale[fieldname] === undefined) {
		return "—";
	}

	return format_currency(
		sale[fieldname],
		sale.currency || frappe.boot.sysdefaults.currency,
	);
}

function render_asset_items(assets, result) {
	return assets
		.map((asset) => {
			const asset_label = asset.asset_name || asset.name;
			const label = result.can_read_asset_links
				? `<a href="${frappe.utils.get_form_link("Asset", asset.name)}" title="${escape_html(asset.name)}">${escape_html(asset_label)}</a>`
				: escape_html(asset_label);
			const actions = render_asset_actions(asset, result.can_prepare_drafts);

			return `
				<tr><td><div class="naseco-employee-asset-identity">${label}</div></td>
				<td>${escape_html(asset.asset_category) || "—"}</td>
				<td>${escape_html(asset.status) || "—"}</td>
				<td class="text-right">${escape_html(format_asset_value(asset, "purchase_cost"))}</td>
				<td class="text-right">${escape_html(format_asset_value(asset, "value_after_depreciation"))}</td>
				${result.can_prepare_drafts ? `<td class="naseco-employee-asset-action-cell">${actions}</td>` : ""}</tr>
			`;
		})
		.join("");
}

function render_asset_actions(asset, can_prepare_drafts) {
	if (!can_prepare_drafts) return "";
	if (asset.pending_hr_draft) {
		return `<span class="text-muted">${__("Awaiting Finance review")}</span>`;
	}
	if (asset.docstatus !== 1 || ["Sold", "Scrapped", "Cancelled"].includes(asset.status)) {
		return "";
	}

	const asset_name = escape_html(asset.name);
	return `
		<div class="dropdown naseco-employee-asset-actions">
			<button type="button" class="btn btn-xs btn-default dropdown-toggle" data-toggle="dropdown"
				data-boundary="viewport" aria-haspopup="true" aria-expanded="false">
				${__("Actions")}
			</button>
			<div class="dropdown-menu dropdown-menu-right">
				<button type="button" class="dropdown-item hr-asset-action" data-action="sale" data-asset="${asset_name}">${__("Sell Asset")}</button>
				<button type="button" class="dropdown-item hr-asset-action" data-action="scrap" data-asset="${asset_name}">${__("Scrap Asset")}</button>
				<button type="button" class="dropdown-item hr-asset-action" data-action="return" data-asset="${asset_name}">${__("Return Asset")}</button>
			</div>
		</div>
	`;
}

function render_asset_sale_history(asset_sales) {
	if (!asset_sales.length) {
		return "";
	}

	const rows = asset_sales.map((sale) => `
		<tr>
			<td>
				<a href="${frappe.utils.get_form_link("Asset", sale.asset)}">
					${escape_html(sale.asset_name || sale.asset)}
				</a>
			</td>
			<td>${escape_html(frappe.datetime.str_to_user(sale.posting_date))}</td>
			<td>
				<a href="${frappe.utils.get_form_link("Sales Invoice", sale.sales_invoice)}">
					${escape_html(sale.sales_invoice)}
				</a>
			</td>
			<td>${escape_html(sale.invoice_status) || "—"}</td>
			<td class="text-right">${escape_html(format_sale_value(sale, "net_book_value"))}</td>
			<td class="text-right">${escape_html(format_sale_value(sale, "selling_price"))}</td>
			<td class="text-right">${escape_html(format_sale_value(sale, "gain_loss"))}</td>
		</tr>
	`).join("");

	return `
		<div class="mt-5 naseco-employee-asset-sale-history">
			<h5>${__("Asset Sale History")}</h5>
			<div class="table-responsive">
				<table class="table table-bordered table-hover">
					<thead>
						<tr>
							<th>${__("Asset")}</th>
							<th>${__("Sale Date")}</th>
							<th>${__("Sales Invoice")}</th>
							<th>${__("Invoice Status")}</th>
							<th class="text-right">${__("NBV at Sale")}</th>
							<th class="text-right">${__("Selling Price")}</th>
							<th class="text-right">${__("Gain / Loss")}</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
		</div>
	`;
}

function render_custodied_assets(frm, result) {
	const wrapper = frm.fields_dict.naseco_custodied_assets_html.$wrapper;
	if (!result.can_read_assets) {
		wrapper.html(
			`<div class="text-muted">${__("You do not have permission to view Asset records.")}</div>`,
		);
		return;
	}

	const assets = result.assets || [];
	const asset_sales = result.asset_sales || [];
	const summary = assets.length === 1
		? __("1 asset is currently assigned to this employee.")
		: __("{0} assets are currently assigned to this employee.", [assets.length]);

	if (!assets.length) {
		wrapper.html(`<div class="text-muted">${__("No assets are currently assigned to this employee.")}</div>`);
	} else {
		wrapper.html(`
			<div class="text-muted mb-3">${summary}</div>
			<div class="form-grid-container naseco-employee-asset-table-container">
				<div class="form-grid naseco-employee-asset-table-wrap">
					<table class="naseco-employee-asset-table">
						<thead><tr><th>${__("Asset")}</th><th>${__("Asset Category")}</th>
						<th>${__("Status")}</th><th class="text-right">${__("Purchase Cost")}</th>
						<th class="text-right">${__("Value After Depreciation")}</th>
						${result.can_prepare_drafts ? `<th class="naseco-employee-asset-action-heading">${__("Actions")}</th>` : ""}</tr></thead>
						<tbody>${render_asset_items(assets, result)}</tbody>
					</table>
				</div>
			</div>
		`);
	}

	if (asset_sales.length) {
		wrapper.append(render_asset_sale_history(asset_sales));
	}

	// Position the menu against the viewport so the grid cannot clip it.
	wrapper.find(".naseco-employee-asset-actions [data-toggle='dropdown']").dropdown({
		popperConfig: { positionFixed: true },
	});

	wrapper.find(".hr-asset-action").on("click", function () {
		open_hr_asset_dialog(frm, this.dataset.asset, this.dataset.action);
	});
}

function open_hr_asset_dialog(frm, asset_name, action) {
	const definitions = {
		sale: { title: __("Prepare Asset Sale"), method: "prepare_asset_sale", fields: [
			{ fieldname: "buyer_type", label: __("Buyer Type"), fieldtype: "Select", options: "Employee\nCustomer", reqd: 1, default: "Employee" },
			{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer", depends_on: "eval:doc.buyer_type==='Customer'", mandatory_depends_on: "eval:doc.buyer_type==='Customer'" },
			{ fieldname: "selling_price", label: __("Selling Price (leave blank for book value)"), fieldtype: "Currency" },
			{ fieldname: "posting_date", label: __("Sale Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
			{ fieldname: "reason", label: __("Reason"), fieldtype: "Small Text" },
		] },
		scrap: { title: __("Prepare Asset Scrap"), method: "prepare_asset_scrap", fields: [
			{ fieldname: "posting_date", label: __("Scrap Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
			{ fieldname: "reason", label: __("Scrap Reason"), fieldtype: "Small Text", reqd: 1 },
		] },
		return: { title: __("Prepare Asset Return"), method: "prepare_asset_return", fields: [
			{ fieldname: "target_location", label: __("Return Location"), fieldtype: "Link", options: "Location", reqd: 1 },
			{ fieldname: "transaction_date", label: __("Return Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
			{ fieldname: "reason", label: __("Reason"), fieldtype: "Small Text" },
		] },
	};
	const definition = definitions[action];
	if (!definition) return;
	const dialog = new frappe.ui.Dialog({
		title: definition.title, fields: definition.fields,
		primary_action_label: __("Create Draft"),
		primary_action(values) {
			dialog.disable_primary_action();
			frappe.call({
				method: `naseco_assets.naseco_assets.hr_asset_actions.${definition.method}`,
				args: { employee: frm.doc.name, asset_name, ...values },
				callback(r) {
					dialog.hide();
					frappe.msgprint(__("Draft {0} {1} created for Finance review.", [r.message.doctype, r.message.name]));
					load_custodied_assets(frm);
				},
				error() { dialog.enable_primary_action(); },
			});
		},
	});
	dialog.show();
}

function load_custodied_assets(frm) {
	const field = frm.fields_dict.naseco_custodied_assets_html;
	if (!field || frm.is_new()) {
		return;
	}

	field.$wrapper.html(`<div class="text-muted">${__("Loading current assets...")}</div>`);
	frappe.require("/assets/naseco_assets/css/employee_assets.css").then(() => frappe.call({
		method: "naseco_assets.naseco_assets.api.get_employee_custodied_assets",
		args: { employee: frm.doc.name },
		callback(r) {
			render_custodied_assets(frm, r.message || { assets: [], can_read_assets: true });
		},
	}));
}

frappe.ui.form.on("Employee", {
	refresh(frm) {
		load_custodied_assets(frm);
	},
});
