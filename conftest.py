import pytest
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

def pytest_sessionfinish(session, exitstatus):

    try:
        from scenarios.test_premium import results_summary
    except:
        return

    if not results_summary:
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "Premium Report"

    headers = list(results_summary[0].keys())

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)

    for row_num, row_data in enumerate(results_summary, 2):
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=row_num, column=col_num, value=row_data[header])

            if row_data["Status"] == "FAILED":
                cell.fill = PatternFill(start_color="FFC7CE", fill_type="solid")
            else:
                cell.fill = PatternFill(start_color="C6EFCE", fill_type="solid")

    for col in ws.columns:
        max_length = 0
        column = col[0].column
        for cell in col:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[get_column_letter(column)].width = max_length + 2

    wb.save("reports/premium_report.xlsx")

    print("\nPremium Excel Report Generated: reports/premium_report.xlsx\n")