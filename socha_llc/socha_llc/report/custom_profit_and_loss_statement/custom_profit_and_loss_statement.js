// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt


// Profit and Loss Statement Report
frappe.query_reports["Custom Profit and Loss Statement"] = $.extend({}, erpnext.financial_statements);

// Extend financial statements with custom settings
erpnext.utils.add_dimensions("Custom Profit and Loss Statement", 10);

// Override the periodicity filter to include additional options
setTimeout(() => {
	const periodicity_filter = frappe.query_reports["Custom Profit and Loss Statement"]["filters"].find(filter => filter.fieldname === "periodicity");
	if (periodicity_filter) {
		periodicity_filter.options = [
			{ value: "Weekly", label: __("Weekly") },
			{ value: "Monthly", label: __("Monthly") },
			{ value: "Quarterly", label: __("Quarterly") },
			{ value: "Half-Yearly", label: __("Half-Yearly") },
			{ value: "Yearly", label: __("Yearly") }
		];
		periodicity_filter.default = "Monthly";
	}
}, 100);

frappe.query_reports["Custom Profit and Loss Statement"]["filters"].push({
	fieldname: "selected_view",
	label: __("Select View"),
	fieldtype: "Select",
	options: [
		{ value: "Report", label: __("Report View") },
		{ value: "Growth", label: __("Growth View") },
		{ value: "Margin", label: __("Margin View") },
	],
	default: "Report",
	reqd: 1,
});

frappe.query_reports["Custom Profit and Loss Statement"]["filters"].push({
	fieldname: "accumulated_values",
	label: __("Accumulated Values"),
	fieldtype: "Check",
	default: 1,
});

frappe.query_reports["Custom Profit and Loss Statement"]["filters"].push({
	fieldname: "include_default_book_entries",
	label: __("Include Default FB Entries"),
	fieldtype: "Check",
	default: 1,
});


frappe.query_reports["Custom Profit and Loss Statement"]["filters"].push({
	fieldname: "show_difference",
	label: __("Show Difference Columns"),
	fieldtype: "Select",
	options: [" " , "Monthly" , "Yearly"],
	default: "",
});

