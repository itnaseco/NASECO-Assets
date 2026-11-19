frappe.ui.form.on("Asset Insurance Policy", {
	setup(frm) {
		frm.set_query("asset_item_code", () => {
			return {
				filters: {
					is_fixed_asset: 1,
					disabled: 0,
				},
			};
		});

		frm.set_query("insurance_company", () => {
			return {
				filters: {
					supplier_group: "Insurance Provider",
					disabled: 0,
				},
			};
		});

		frm.set_query("asset", "covered_assets", () => {
			const filters = {
				docstatus: 1,
				status: ["not in", ["Draft", "Sold", "Scrapped"]],
			};

			const basis = frm.doc.coverage_basis || "Selected Assets";
			if (basis === "Item Code" && frm.doc.asset_item_code) {
				filters.item_code = frm.doc.asset_item_code;
			} else if (basis === "Asset Category" && frm.doc.asset_category) {
				filters.asset_category = frm.doc.asset_category;
			} else if (basis === "Branch" && frm.doc.branch) {
				filters.branch = frm.doc.branch;
			} else if (basis === "Department" && frm.doc.department) {
				filters.department = frm.doc.department;
			} else if (basis === "Location" && frm.doc.location) {
				filters.location = frm.doc.location;
			} else if (frm.doc.asset_item_code) {
				filters.item_code = frm.doc.asset_item_code;
			}

			return { filters };
		});
	},

	refresh(frm) {
		toggle_coverage_controls(frm);
	},

	coverage_basis(frm) {
		toggle_coverage_controls(frm);
		frm.refresh_field("covered_assets");
	},

	asset_item_code(frm) {
		frm.refresh_field("covered_assets");
	},

	asset_category(frm) {
		frm.refresh_field("covered_assets");
	},

	branch(frm) {
		frm.refresh_field("covered_assets");
	},

	department(frm) {
		frm.refresh_field("covered_assets");
	},

	location(frm) {
		frm.refresh_field("covered_assets");
	},
});

function toggle_coverage_controls(frm) {
	const editable = frm.doc.docstatus !== 2;
	frm.set_df_property("covered_assets", "read_only", !editable);
	frm.set_df_property("covered_assets", "cannot_add_rows", !editable);
	frm.set_df_property("covered_assets", "cannot_delete_rows", !editable);
}
