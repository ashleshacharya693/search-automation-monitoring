import pytest
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

def pytest_sessionfinish(session, exitstatus):

    results = getattr(pytest, "results_summary", [])

    if not results:
        print("No results found.")
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "Search Ranking Report"

    headers = list(results[0].keys())

    # Write header
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)

    # Write data rows
    for row_num, row_data in enumerate(results, 2):
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=row_num, column=col_num, value=row_data[header])

            if row_data["Status"] == "FAILED":
                cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
            elif row_data["Status"] == "PASSED":
                cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")

    # Auto adjust column width
    for col in ws.columns:
        max_length = 0
        column = col[0].column
        for cell in col:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[get_column_letter(column)].width = max_length + 2

    # Accuracy calculation
    total = len(results)
    passed = len([r for r in results if r["Status"] == "PASSED"])
    accuracy = (passed / total) * 100 if total > 0 else 0

    ws["A" + str(total + 3)] = f"Total Tests: {total}"
    ws["A" + str(total + 4)] = f"Passed: {passed}"
    ws["A" + str(total + 5)] = f"Accuracy: {accuracy:.2f}%"

    # Save file
    wb.save("reports/search_ranking_report.xlsx")

    print("\n========================================")
    print("Excel Report Generated: reports/search_ranking_report.xlsx")
    print(f"Ranking Accuracy: {accuracy:.2f}%")
    print("========================================\n")