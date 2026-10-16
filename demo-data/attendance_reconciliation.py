"""Run the demo comparison between DYCD attendance and OCR attendance.

From the repository root, run:

    python demo-data/attendance_reconciliation.py

The input workbooks default to the examples beside this script. The output is
a timestamped Excel report in the same directory.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from attendance_audit.comparison import compare_attendance
from attendance_audit.reporting import write_report
from attendance_audit.workbook_io import (
    DYCD_COLUMNS,
    OCR_COLUMNS,
    read_attendance_workbook,
    read_roster,
)


DEMO_DIR = Path(__file__).resolve().parent
DEFAULT_DYCD_FILE = DEMO_DIR / "SONYC_DYCD_Attendance_Results.xlsx"
DEFAULT_OCR_FILE = DEMO_DIR / "SONYC_OCR_Results.xlsx"
DEFAULT_ROSTER_FILE = DEMO_DIR / "SONYC_DYCD-Internal_Roster_DB.xlsx"


def reconcile_workbooks(
    dycd_path: str | Path = DEFAULT_DYCD_FILE,
    ocr_path: str | Path = DEFAULT_OCR_FILE,
    roster_path: str | Path = DEFAULT_ROSTER_FILE,
) -> pd.DataFrame:
    """Read the input files and return one row per comparison or review issue."""
    # Keep file reading here so the comparison logic can work directly with dataframes.
    dycd_attendance = read_attendance_workbook(dycd_path, DYCD_COLUMNS)
    ocr_attendance = read_attendance_workbook(ocr_path, OCR_COLUMNS)
    roster = read_roster(roster_path)

    return compare_attendance(dycd_attendance, ocr_attendance, roster)


def _default_output_path() -> Path:
    """Build a unique output filename using the current date and time."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"DYCD_OCR_Attendance_Reconciliation_{timestamp}.xlsx"
    return DEMO_DIR / filename


def main() -> None:
    """Read command-line options, run the audit, and save its Excel report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dycd", type=Path, default=DEFAULT_DYCD_FILE)
    parser.add_argument("--ocr", type=Path, default=DEFAULT_OCR_FILE)
    parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER_FILE)
    parser.add_argument("--output", type=Path, default=_default_output_path())
    args = parser.parse_args()

    results = reconcile_workbooks(args.dycd, args.ocr, args.roster)
    output_path = write_report(results, args.output)

    # These counts are a quick console summary; the workbook contains row-level details.
    matching_count = results["Result"].eq("Match").sum()
    review_count = results["Result"].ne("Match").sum()
    print(f"Compared records: {len(results)}")
    print(f"Matching records: {matching_count}")
    print(f"Records requiring review: {review_count}")
    print(f"Report written to: {output_path}")


if __name__ == "__main__":
    main()
