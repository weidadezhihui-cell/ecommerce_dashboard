"""
Etsy-style 'Daily & Monthly Wealth Tracker' Excel generator.
Uses xlsxwriter. Theme: Minimalist Noir / Soft Sage.
Output: Professional_Daily_Budget_Planner.xlsx
"""

import os
import xlsxwriter
from datetime import datetime, timedelta

OUTPUT_DIR = r"C:\Users\Mark.Zhao\OneDrive - Government of Alberta\Documents\Etsy_Planner_Project"
OUTPUT_FILE = "Professional_Daily_Budget_Planner.xlsx"
TITLE_COLOR = "#2F4F4F"
ACCENT_COLOR = "#8FBC8F"
DAILY_LIMIT = 50
SAMPLE_DAYS = 5
CATEGORIES = ["Food", "Transport", "Rent", "Fun"]

# Sample data: (description, category, amount)
SAMPLE_EXPENSES = [
    ("Coffee & breakfast", "Food", 12.50),
    ("Bus pass", "Transport", 28.00),
    ("Groceries", "Food", 45.00),
    ("Movie night", "Fun", 25.00),
    ("Lunch", "Food", 15.00),
]


def add_setup_instructions(workbook, fmt):
    """Tab 1: Setup & Instructions with Welcome and Monthly Goals."""
    ws = workbook.add_worksheet("Setup & Instructions")
    ws.hide_gridlines(2)

    title_fmt = workbook.add_format({
        "bold": True, "font_size": 18, "font_color": TITLE_COLOR,
        "align": "center", "valign": "vcenter",
    })
    heading_fmt = workbook.add_format({
        "bold": True, "font_size": 12, "font_color": TITLE_COLOR,
        "bg_color": ACCENT_COLOR, "align": "center", "border": 1,
    })
    step_fmt = workbook.add_format({
        "font_size": 11, "text_wrap": True, "valign": "top",
    })
    label_fmt = workbook.add_format({
        "bold": True, "font_color": TITLE_COLOR,
    })

    ws.set_column("A:A", 6)
    ws.set_column("B:B", 60)
    ws.set_column("C:C", 20)

    ws.merge_range("B2:C2", "Daily & Monthly Wealth Tracker", title_fmt)
    ws.set_row(1, 28)
    ws.merge_range("B4:C4", "Welcome", heading_fmt)
    steps = [
        "1. Enter your Monthly Income and Monthly Savings Goal in the boxes below.",
        "2. Use the 'Daily Expense Tracker' sheet to log every expense (Date, Category, Description, Amount).",
        "3. Check the 'Monthly Dashboard' to see your Spending vs Savings and goal progress.",
        "4. Stay under the daily limit to build better habits.",
    ]
    for i, text in enumerate(steps):
        ws.merge_range(5 + i, 1, 5 + i, 2, text, step_fmt)

    ws.merge_range("B11:C11", "Monthly Goals", heading_fmt)
    ws.write("B12", "Monthly Income ($):", label_fmt)
    ws.write("B13", "Monthly Savings Goal ($):", label_fmt)
    ws.write("C12", 3000)
    ws.write("C13", 500)
    income_fmt = workbook.add_format({"num_format": "#,##0.00", "locked": False})
    ws.write("C12", 3000, income_fmt)
    ws.write("C13", 500, income_fmt)

    # Names for Dashboard references (same workbook, so we use sheet index/name)
    workbook.define_name("MonthlyIncome", "='Setup & Instructions'!$C$12")
    workbook.define_name("MonthlyGoal", "='Setup & Instructions'!$C$13")


def add_daily_tracker(workbook, fmt):
    """Tab 2: Daily Expense Tracker with validation, daily limit alert, sample data."""
    ws = workbook.add_worksheet("Daily Expense Tracker")
    ws.hide_gridlines(2)

    header_fmt = workbook.add_format({
        "bold": True, "font_color": TITLE_COLOR, "bg_color": ACCENT_COLOR,
        "align": "center", "border": 1,
    })
    unlocked_fmt = workbook.add_format({"locked": False})
    unlocked_currency = workbook.add_format({"locked": False, "num_format": "$#,##0.00"})
    date_fmt = workbook.add_format({"locked": False, "num_format": "yyyy-mm-dd"})
    alert_fmt = workbook.add_format({"font_color": "red", "bold": True})

    ws.set_column("A:A", 14)
    ws.set_column("B:B", 14)
    ws.set_column("C:C", 32)
    ws.set_column("D:D", 12)
    ws.set_column("E:E", 14)

    headers = ["Date", "Category", "Description", "Amount", "Daily Total"]
    for col, h in enumerate(headers):
        ws.write(0, col, h, header_fmt)

    # Data validation for Category
    dv = {"validate": "list", "source": ",".join(CATEGORIES)}
    ws.data_validation("B2:B500", dv)

    # Sample data for 5 days (one expense per day for simplicity)
    base_date = datetime.now().replace(day=1)
    for i in range(SAMPLE_DAYS):
        row = 1 + i
        day = base_date + timedelta(days=i)
        desc, cat, amt = SAMPLE_EXPENSES[i]
        ws.write(row, 0, day.date(), date_fmt)
        ws.write(row, 1, cat, unlocked_fmt)
        ws.write(row, 2, desc, unlocked_fmt)
        ws.write(row, 3, amt, unlocked_currency)
    # Daily total per row (sum of Amount for that row's date)
    locked_fmt = workbook.add_format({"locked": True})
    for row in range(1, 102):
        excel_row = row + 1
        ws.write(row, 4, f"=SUMIF(A:A,A{excel_row},D:D)", locked_fmt)

    # Daily limit alert: if Daily Total > $50, show red warning
    ws.write(0, 5, "Alert", header_fmt)
    alert_fmt = workbook.add_format({"locked": True, "font_color": "red"})
    for row in range(1, 102):
        excel_row = row + 1
        ws.write(row, 5, f'=IF(E{excel_row}>50,"Over $50 daily limit!","")', alert_fmt)

    # Empty rows for user input (rows 6–101)
    for row in range(6, 101):
        ws.write(row, 0, None, date_fmt)
        ws.write(row, 1, None, unlocked_fmt)
        ws.write(row, 2, None, unlocked_fmt)
        ws.write(row, 3, None, unlocked_currency)

    ws.set_column("F:F", 22)
    workbook.define_name("DailyTrackerAmounts", "='Daily Expense Tracker'!$D$2:$D$500")
    workbook.define_name("DailyTrackerDates", "='Daily Expense Tracker'!$A$2:$A$500")


def add_monthly_dashboard(workbook, fmt):
    """Tab 3: Monthly Dashboard with donut chart and goal progress bar."""
    ws = workbook.add_worksheet("Monthly Dashboard")
    ws.hide_gridlines(2)

    title_fmt = workbook.add_format({
        "bold": True, "font_size": 14, "font_color": TITLE_COLOR,
        "align": "center",
    })
    heading_fmt = workbook.add_format({
        "bold": True, "font_color": TITLE_COLOR, "bg_color": ACCENT_COLOR,
        "align": "center", "border": 1,
    })
    label_fmt = workbook.add_format({"bold": True, "font_color": TITLE_COLOR})

    ws.set_column("A:A", 22)
    ws.set_column("B:B", 16)

    ws.merge_range("A1:B1", "Monthly Overview", title_fmt)
    ws.set_row(0, 24)
    ws.write("A3", "Total Spending (this month):", label_fmt)
    ws.write("A4", "Monthly Income:", label_fmt)
    ws.write("A5", "Savings:", label_fmt)
    ws.write("A6", "Monthly Goal Progress:", label_fmt)

    # Pull from Setup and Daily Tracker
    ws.write("B3", "=SUM('Daily Expense Tracker'!D:D)", workbook.add_format({"num_format": "$#,##0.00", "locked": True}))
    ws.write("B4", "='Setup & Instructions'!C12", workbook.add_format({"num_format": "$#,##0.00", "locked": True}))
    ws.write("B5", "=B4-B3", workbook.add_format({"num_format": "$#,##0.00", "locked": True}))
    # Progress: (Income - Spending) / Goal, cap at 1
    ws.write("B6", "=MIN(1,(B4-B3)/MAX(1,'Setup & Instructions'!C13))", workbook.add_format({"num_format": "0%", "locked": True}))

    # Horizontal progress bar: one stacked bar (Reached % + Remaining %)
    ws.write("A8", "Goal progress", heading_fmt)
    ws.merge_range("A8:B8", "Goal progress", heading_fmt)
    ws.write("A9", "Progress", label_fmt)
    ws.write("B9", "=B6", workbook.add_format({"locked": True, "num_format": "0%"}))
    ws.write("C9", "=1-B6", workbook.add_format({"locked": True, "num_format": "0%"}))

    chart = workbook.add_chart({"type": "bar", "subtype": "stacked"})
    chart.add_series({"name": "Reached", "categories": "='Monthly Dashboard'!$A$9", "values": "='Monthly Dashboard'!$B$9"})
    chart.add_series({"name": "Remaining", "categories": "='Monthly Dashboard'!$A$9", "values": "='Monthly Dashboard'!$C$9"})
    chart.set_title({"name": "Monthly Goal Progress"})
    chart.set_style(2)
    chart.set_size({"width": 480, "height": 120})
    ws.insert_chart("A11", chart)

    # Donut: Spending vs Savings
    ws.write("A23", "Spending vs Savings", heading_fmt)
    ws.merge_range("A23:B23", "Spending vs Savings", heading_fmt)
    ws.write("A24", "Spending")
    ws.write("B24", "=B3", workbook.add_format({"locked": True}))
    ws.write("A25", "Savings")
    ws.write("B25", "=B5", workbook.add_format({"locked": True}))
    donut = workbook.add_chart({"type": "doughnut"})
    donut.add_series({
        "name": "Spending vs Savings",
        "categories": "='Monthly Dashboard'!$A$24:$A$25",
        "values": "='Monthly Dashboard'!$B$24:$B$25",
    })
    donut.set_title({"name": "Spending vs Savings"})
    donut.set_style(2)
    donut.set_size({"width": 400, "height": 300})
    ws.insert_chart("A26", donut)

    # Protect sheet: only input cells editable (Setup C12:C13, Daily Tracker A:D)
    ws.protect("", {"sheet": True})


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    workbook = xlsxwriter.Workbook(out_path, {"nan_inf_to_errors": True})

    # Shared theme format (for any shared use)
    theme_fmt = workbook.add_format({
        "font_color": TITLE_COLOR,
    })

    add_setup_instructions(workbook, theme_fmt)
    add_daily_tracker(workbook, theme_fmt)
    add_monthly_dashboard(workbook, theme_fmt)

    # Protect Daily Tracker: only A:D editable
    daily = workbook.get_worksheet_by_name("Daily Expense Tracker")
    daily.protect("", {"sheet": True})

    workbook.close()
    print(f"Created {out_path}")


if __name__ == "__main__":
    main()
