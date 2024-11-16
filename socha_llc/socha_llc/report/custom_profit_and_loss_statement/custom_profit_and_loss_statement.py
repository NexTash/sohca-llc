# Copyright (c) 2024, Socha LLC and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.accounts.report.financial_statements import (
	get_columns,
	get_data,
	get_filtered_list_for_consolidated_report,
	get_period_list,
)


def execute(filters=None):
	period_list = get_period_list(
		filters.from_fiscal_year,
		filters.to_fiscal_year,
		filters.period_start_date,
		filters.period_end_date,
		filters.filter_based_on,
		filters.periodicity,
		company=filters.company,
	)

	filters.period_start_date = period_list[0]["year_start_date"]

	currency = filters.presentation_currency or frappe.get_cached_value(
		"Company", filters.company, "default_currency"
	)

	asset = get_data(
		filters.company,
		"Asset",
		"Debit",
		period_list,
		only_current_fiscal_year=False,
		filters=filters,
		accumulated_values=filters.accumulated_values,
	)

	liability = get_data(
		filters.company,
		"Liability",
		"Credit",
		period_list,
		only_current_fiscal_year=False,
		filters=filters,
		accumulated_values=filters.accumulated_values,
	)

	equity = get_data(
		filters.company,
		"Equity",
		"Credit",
		period_list,
		only_current_fiscal_year=False,
		filters=filters,
		accumulated_values=filters.accumulated_values,
	)
	income = get_data(
		filters.company,
		"Income",
		"Credit",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
	)

	expense = get_data(
		filters.company,
		"Expense",
		"Debit",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
	)

	message, opening_balance = check_opening_balance(asset, liability, equity, income, expense)

	data = []
	data.extend(asset or [])
	data.extend(liability or [])
	data.extend(equity or [])
	data.extend(income or [])
	data.extend(expense or [])
	if opening_balance and round(opening_balance, 2) != 0:
		unclosed = {
			"account_name": "'" + _("Unclosed Fiscal Years Profit / Loss (Credit)") + "'",
			"account": "'" + _("Unclosed Fiscal Years Profit / Loss (Credit)") + "'",
			"warn_if_negative": True,
			"currency": currency,
		}
		for period in period_list:
			unclosed[period.key] = opening_balance

		unclosed["total"] = opening_balance
		data.append(unclosed)

	columns = get_columns(
		filters.periodicity, period_list, filters.accumulated_values, company=filters.company
	)

	columns = get_difference_columns(columns, filters)

	chart = get_chart_data(filters, columns, asset, liability, equity, income, expense, currency)

	report_summary, primitive_summary = get_report_summary(
		period_list, asset, liability, equity, income, expense, {}, currency, filters
	)

	data = get_difference_data(columns, data)

	return columns, data, message, chart, report_summary, primitive_summary


def get_difference_data(columns, data):
    diff_w_columns = []
    percent_diff_columns = []

    # Extracting columns for differences and percentage differences
    for column in columns:
        fieldname = column.get("fieldname")
        if not fieldname:
            continue
        if "diff_with_" in fieldname:
            diff_w_columns.append(fieldname)
        elif "percent_with_" in fieldname:
            percent_diff_columns.append(fieldname)


    for row in data:
        for col in diff_w_columns:
            try:
                months = col.split("diff_with_")[1].split("_and_")
                old_value = float(row.get(months[0], 0) or 0)
                new_value = float(row.get(months[1], 0) or 0)
                row[col] = new_value - old_value
            except (IndexError, ValueError, TypeError) as e:
                frappe.msgprint(f"Error calculating difference for {col}: {e}")
                row[col] = None

    for row in data:
        for col in percent_diff_columns:
            try:
                months = col.split("percent_with_")[1].split("_and_")
                old_value = float(row.get(months[0], 0) or 0)
                new_value = float(row.get(months[1], 0) or 0)
                row[col] = calculate_percentage_difference(old_value, new_value)
            except (IndexError, ValueError, TypeError) as e:
                frappe.msgprint(f"Error calculating percentage for {col}: {e}")
                row[col] = None

    return data


def calculate_percentage_difference(old_value, new_value):
    """
    Calculate percentage difference between old_value and new_value.
    """
    if old_value == 0:
        if new_value == 0:
            return 0 
        return 100  

    try:
        return round(((new_value - old_value) / old_value) * 100, 2)
    except Exception as e:
        frappe.msgprint(f"Error in percentage calculation: {e}")
        return None



def get_difference_columns(columns, filters):
	flag = False
	old_value = {}
	columns_new = []

	for row in columns:
		columns_new.append(row) 
        
		if flag and row.get("fieldtype")  == "Currency":

			if filters.get("show_difference") in ["Monthly"]:
				columns_new.append({
					'fieldname': f'diff_with_{old_value.get("fieldname")}_and_{row.get("fieldname")}', 
					'label': f'Diff W/{old_value.get("label")}', 
					'fieldtype': 'Currency', 
					'options': 'currency', 
					'width': 150
				})
				columns_new.append({
						'fieldname': f'percent_with_{old_value.get("fieldname")}_and_{row.get("fieldname")}',
						'label': f'Percent Diff W/{old_value.get("label")}', 
						'fieldtype': 'Percent', 
						'width': 150
				})	

			if filters.get("show_difference") in ["Yearly"]:
			
				month = row.get("fieldname").split("_")
				
				if len(month) < 2:
					continue 
		
				month = f"{month[0]}_{int(month[1])-1}"

				month_name = row.get("label").split(" ")
				#frappe.msgprint(f"{month_name}")
				month_name = f"{month_name[0]} {int(month_name[1])-1}"
				#frappe.msgprint(f"{month_name}")

		
				columns_new.append({
					'fieldname': f'diff_with_{month}_and_{row.get("fieldname")}', 
					'label': f'Diff W/{month_name}', 
					'fieldtype': 'Currency', 
					'options': 'currency', 
					'width': 150
				})
				columns_new.append({
						'fieldname': f'percent_diff_with_{month_name}_and_{row.get("fieldname")}',
						'label': f'Percent Diff W/{month_name}', 
						'fieldtype': 'Percent', 
						'width': 150
				})
				
		if row.get("fieldtype")  == "Currency":
			flag = True
		
		old_value = row

	columns = columns_new

	# frappe.msgprint(f"{columns}")

	return columns

def check_opening_balance(asset, liability, equity, income, expense):
	# Check if previous year balance sheet closed
	opening_balance = 0
	float_precision = cint(frappe.db.get_default("float_precision")) or 2
	if asset:
		opening_balance = flt(asset[-1].get("opening_balance", 0), float_precision)
	if liability:
		opening_balance -= flt(liability[-1].get("opening_balance", 0), float_precision)
	if equity:
		opening_balance -= flt(equity[-1].get("opening_balance", 0), float_precision)

	if income:
		opening_balance -= flt(income[-1].get("opening_balance", 0), float_precision)
	if expense:
		opening_balance -= flt(expense[-1].get("opening_balance", 0), float_precision)

	opening_balance = flt(opening_balance, float_precision)
	if opening_balance:
		return _("Previous Financial Year is not closed"), opening_balance
	return None, None


def get_report_summary(
	period_list,
	asset,
	liability,
	equity,
	income, 
	expense,
	provisional_profit_loss,
	currency,
	filters,
	consolidated=False,
):
	net_asset, net_liability, net_equity, net_income, net_expense,net_provisional_profit_loss = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

	if filters.get("accumulated_values"):
		period_list = [period_list[-1]]

	# from consolidated financial statement
	if filters.get("accumulated_in_group_company"):
		period_list = get_filtered_list_for_consolidated_report(filters, period_list)

	for period in period_list:
		key = period if consolidated else period.key
		if asset:
			net_asset += asset[-2].get(key)
		if liability and liability[-1] == {}:
			net_liability += liability[-2].get(key)
		if equity and equity[-1] == {}:
			net_equity += equity[-2].get(key)
		if income and income[-1] == {}:
			net_income += income[-2].get(key)
		if expense and expense[-1] == {}:
			net_expense += expense[-2].get(key)

		if provisional_profit_loss:
			net_provisional_profit_loss += provisional_profit_loss.get(key)

	return [
		{"value": net_asset, "label": _("Total Asset"), "datatype": "Currency", "currency": currency},
		{
			"value": net_liability,
			"label": _("Total Liability"),
			"datatype": "Currency",
			"currency": currency,
		},
		{"value": net_equity, "label": _("Total Equity"), "datatype": "Currency", "currency": currency},
		{"value": net_income, "label": _("Total Income"), "datatype": "Currency", "currency": currency},
		{"value": net_expense, "label": _("Total Expense"), "datatype": "Currency", "currency": currency},
	], (net_asset - net_liability + net_equity)


def get_chart_data(filters, columns, asset, liability, equity, income, expense, currency):
	labels = [d.get("label") for d in columns[2:]]

	asset_data, liability_data, equity_data, income_data, expense_data = [], [],[], [], []

	for p in columns[2:]:
		if asset:
			asset_data.append(asset[-2].get(p.get("fieldname")))
		if liability:
			liability_data.append(liability[-2].get(p.get("fieldname")))
		if equity:
			equity_data.append(equity[-2].get(p.get("fieldname")))
		if income:
			income_data.append(income[-2].get(p.get("fieldname")))
		if expense:
			expense_data.append(expense[-2].get(p.get("fieldname")))

	datasets = []
	if asset_data:
		datasets.append({"name": _("Assets"), "values": asset_data})
	if liability_data:
		datasets.append({"name": _("Liabilities"), "values": liability_data})
	if equity_data:
		datasets.append({"name": _("Equity"), "values": equity_data})
	if income_data:
		datasets.append({"name": _("Income"), "values": income_data})
	if expense_data:
		datasets.append({"name": _("Expense"), "values": expense_data})

	chart = {"data": {"labels": labels, "datasets": datasets}}

	if not filters.accumulated_values:
		chart["type"] = "bar"
	else:
		chart["type"] = "line"

	chart["fieldtype"] = "Currency"
	chart["options"] = "currency"
	chart["currency"] = currency

	return chart
