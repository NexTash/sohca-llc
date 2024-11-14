# Copyright (c) 2024, Socha LLc and contributors
# For license information, please see license.txt

# import frappe

import frappe
from frappe import _
from frappe.utils import flt, cint
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
    currency = filters.presentation_currency or frappe.get_cached_value("Company", filters.company, "default_currency")

    # Fetch data for balance sheet components
    asset = get_data(filters.company, "Asset", "Debit", period_list, only_current_fiscal_year=False, filters=filters, accumulated_values=filters.accumulated_values)
    liability = get_data(filters.company, "Liability", "Credit", period_list, only_current_fiscal_year=False, filters=filters, accumulated_values=filters.accumulated_values)
    equity = get_data(filters.company, "Equity", "Credit", period_list, only_current_fiscal_year=False, filters=filters, accumulated_values=filters.accumulated_values)

    # Fetch data for income statement components
    income = get_data(filters.company, "Income", "Credit", period_list, filters=filters, accumulated_values=filters.accumulated_values, ignore_closing_entries=True, ignore_accumulated_values_for_fy=True)
    expense = get_data(filters.company, "Expense", "Debit", period_list, filters=filters, accumulated_values=filters.accumulated_values, ignore_closing_entries=True, ignore_accumulated_values_for_fy=True)

    # Calculate net profit/loss and provisional profit/loss
    net_profit_loss = get_net_profit_loss(income, expense, period_list, filters.company, currency)
    provisional_profit_loss, total_credit = get_provisional_profit_loss(asset, liability, equity, period_list, filters.company, currency)

    # Prepare the final data list
    data = []
    data.extend(asset or [])
    data.extend(liability or [])
    data.extend(equity or [])
    data.extend(income or [])
    data.extend(expense or [])

    # Add unclosed balance and provisional/net profit to data
    message, opening_balance = check_opening_balance(asset, liability, equity)
    if opening_balance and round(opening_balance, 2) != 0:
        unclosed = {
            "account_name": "'" + _("Unclosed Fiscal Years Profit / Loss (Credit)") + "'",
            "account": "'" + _("Unclosed Fiscal Years Profit / Loss (Credit)") + "'",
            "warn_if_negative": True,
            "currency": currency,
        }
        for period in period_list:
            unclosed[period.key] = opening_balance
            if provisional_profit_loss:
                provisional_profit_loss[period.key] = provisional_profit_loss[period.key] - opening_balance
        unclosed["total"] = opening_balance
        data.append(unclosed)

    if provisional_profit_loss:
        data.append(provisional_profit_loss)
    if net_profit_loss:
        data.append(net_profit_loss)
    if total_credit:
        data.append(total_credit)

    # Prepare columns, chart data, and report summary
    columns = get_columns(filters.periodicity, period_list, filters.accumulated_values, filters.company)
    chart = get_chart_data(filters, columns, asset, liability, equity, income, expense, net_profit_loss, currency)
    report_summary, primitive_summary = get_report_summary(period_list, asset, liability, equity, income, expense, net_profit_loss, provisional_profit_loss, currency, filters)

    return columns, data, message, chart, report_summary, primitive_summary

def get_net_profit_loss(income, expense, period_list, company, currency=None, consolidated=False):
    total = 0
    net_profit_loss = {
        "account_name": "'" + _("Profit for the year") + "'",
        "account": "'" + _("Profit for the year") + "'",
        "warn_if_negative": True,
        "currency": currency or frappe.get_cached_value("Company", company, "default_currency"),
    }

    has_value = False
    for period in period_list:
        key = period if consolidated else period.key
        total_income = flt(income[-2][key], 3) if income else 0
        total_expense = flt(expense[-2][key], 3) if expense else 0
        net_profit_loss[key] = total_income - total_expense
        if net_profit_loss[key]:
            has_value = True
        total += flt(net_profit_loss[key])
    net_profit_loss["total"] = total
    return net_profit_loss if has_value else None

def get_provisional_profit_loss(asset, liability, equity, period_list, company, currency=None, consolidated=False):
    provisional_profit_loss = {}
    total_row = {"account_name": _("Total (Credit)"), "account": _("Total (Credit)"), "warn_if_negative": True, "currency": currency}

    total = 0
    for period in period_list:
        key = period if consolidated else period.key
        total_assets = flt(asset[-2].get(key), 3) if asset else 0
        total_liabilities = flt(liability[-2].get(key), 3) if liability else 0
        total_equity = flt(equity[-2].get(key), 3) if equity else 0
        provisional_profit_loss[key] = total_assets - (total_liabilities + total_equity)
        total_row[key] = provisional_profit_loss[key] + total_liabilities + total_equity
        total += flt(provisional_profit_loss[key])
    provisional_profit_loss["total"] = total
    return provisional_profit_loss, total_row

def check_opening_balance(asset, liability, equity):
    asset_balance = flt(asset[-1].get("opening_balance", 0)) if asset else 0
    liability_balance = flt(liability[-1].get("opening_balance", 0)) if liability else 0
    equity_balance = flt(equity[-1].get("opening_balance", 0)) if equity else 0
    opening_balance = asset_balance - liability_balance - equity_balance
    return (_("Previous Financial Year is not closed"), opening_balance) if opening_balance else (None, None)

def get_report_summary(period_list, asset, liability, equity, income, expense, net_profit_loss, provisional_profit_loss, currency, filters, consolidated=False):
    net_asset, net_liability, net_equity, net_income, net_expense, net_profit = 0, 0, 0, 0, 0, 0
    for period in period_list:
        key = period if consolidated else period.key
        net_asset += flt(asset[-2].get(key)) if asset else 0
        net_liability += flt(liability[-2].get(key)) if liability else 0
        net_equity += flt(equity[-2].get(key)) if equity else 0
        net_income += flt(income[-2].get(key)) if income else 0
        net_expense += flt(expense[-2].get(key)) if expense else 0
        net_profit += flt(net_profit_loss.get(key)) if net_profit_loss else 0
    return [
        {"value": net_asset, "label": _("Total Asset"), "datatype": "Currency", "currency": currency},
        {"value": net_liability, "label": _("Total Liability"), "datatype": "Currency", "currency": currency},
        {"value": net_equity, "label": _("Total Equity"), "datatype": "Currency", "currency": currency},
        {"value": net_income, "label": _("Total Income"), "datatype": "Currency", "currency": currency},
        {"value": net_expense, "label": _("Total Expense"), "datatype": "Currency", "currency": currency},
        {"value": net_profit, "indicator": "Green" if net_profit > 0 else "Red", "label": _("Net Profit"), "datatype": "Currency", "currency": currency},
    ], net_profit

def get_chart_data(filters, columns, asset, liability, equity, income, expense, net_profit_loss, currency):
    labels = [d.get("label") for d in columns[2:]]
    asset_data, liability_data, equity_data, income_data, expense_data, net_profit = [], [], [], [], [], []
    for col in columns[2:]:
        asset_data.append(asset[-2].get(col.get("fieldname")) if asset else 0)
        liability_data.append(liability[-2].get(col.get("fieldname")) if liability else 0)
        equity_data.append(equity[-2].get(col.get("fieldname")) if equity else 0)
        income_data.append(income[-2].get(col.get("fieldname")) if income else 0)
        expense_data.append(expense[-2].get(col.get("fieldname")) if expense else 0)
        net_profit.append(net_profit_loss.get(col.get("fieldname")) if net_profit_loss else 0)

    datasets = [
        {"name": _("Assets"), "values": asset_data},
        {"name": _("Liabilities"), "values": liability_data},
        {"name": _("Equity"), "values": equity_data},
        {"name": _("Income"), "values": income_data},
        {"name": _("Expenses"), "values": expense_data},
        {"name": _("Net Profit"), "values": net_profit},
    ]

    return {
        "data": {"labels": labels, "datasets": datasets},
        "type": "line" if filters.presentation_currency else "bar",
        "fieldtype": "Currency",
        "currency": currency,
    }
