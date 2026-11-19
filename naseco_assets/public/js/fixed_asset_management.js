const indicator = (value, mapping, fallback = "gray") => [__(value || "Draft"), mapping[value] || fallback, `status,=,${value || "Draft"}`];

frappe.listview_settings["Fixed Asset Request"] = {
	get_indicator(doc) {
		return indicator(
			doc.approval_status,
			{
				"Draft": "gray",
				"Pending Department Approval": "orange",
				"Pending Finance Review": "orange",
				"Pending Management Approval": "yellow",
				"Approved": "green",
				"Rejected": "red",
				"Deferred": "blue",
			},
		);
	},
};

frappe.listview_settings["Fixed Asset CAPEX Plan"] = {
	get_indicator(doc) {
		return indicator(doc.status, { Draft: "gray", Approved: "green", Frozen: "orange", Closed: "red" });
	},
};

frappe.listview_settings["Asset Insurance Policy"] = {
	get_indicator(doc) {
		return indicator(doc.status, { Active: "green", "Expiring Soon": "orange", Expired: "red", Cancelled: "gray" });
	},
};

frappe.listview_settings["Asset Maintenance Plan"] = {
	get_indicator(doc) {
		return indicator(doc.status, { Active: "green", Suspended: "orange", Closed: "red" });
	},
};

frappe.listview_settings["CIP Capitalization Request"] = {
	get_indicator(doc) {
		return indicator(doc.finance_review_status, { Draft: "gray", "Pending Review": "orange", Approved: "green", Rejected: "red" });
	},
};
