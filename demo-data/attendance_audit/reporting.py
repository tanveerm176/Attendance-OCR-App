"""Write the reconciliation result and its review summary to Excel."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from attendance_audit.formatting import format_report_workbook


def _build_issues_sheet(results: pd.DataFrame) -> pd.DataFrame:
    """Select every row that is not a successful attendance match."""
    issue_rows = results.loc[results["Result"].ne("Match")].copy()
    return issue_rows


def _build_summary_sheet(results: pd.DataFrame) -> pd.DataFrame:
    """Count each result category for each date."""
    summary = results.groupby(["Date", "Result"], dropna=False).size()
    summary = summary.rename("Records").reset_index()
    return summary


def write_report(results: pd.DataFrame, output_path: str | Path) -> Path:
    """Save detailed results, review items, and summary counts to an Excel file."""
    report_path = Path(output_path)
    issues = _build_issues_sheet(results)
    summary = _build_summary_sheet(results)

    # Keep all rows in the report, even when a row needs manual follow-up.
    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        results.to_excel(writer, sheet_name="All Results", index=False)
        issues.to_excel(writer, sheet_name="Issues", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)

        # Apply formatting after all three worksheets have been created.
        format_report_workbook(writer.sheets)

    return report_path
