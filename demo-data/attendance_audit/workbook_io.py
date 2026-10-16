"""Read and validate the Excel workbooks used by the demo attendance audit."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


DYCD_COLUMNS = ["Date", "ID", "Name", "Attendance"]
OCR_COLUMNS = [
    "Date",
    "OCR Raw",
    "Attendance Status",
    "Matched Name",
    "Matched Score",
    "Flag",
]
ROSTER_COLUMNS = ["DYCD ID", "Internal Roster Name"]


def _parse_sheet_date(sheet_name: str, workbook_path: Path) -> pd.Timestamp:
    """Convert a worksheet title such as 09-14-2026 into a normalized date."""
    try:
        parsed_date = datetime.strptime(sheet_name, "%m-%d-%Y")
    except ValueError as error:
        message = (
            f"Expected date-named worksheet in {workbook_path.name}: "
            f"{sheet_name!r} (expected MM-DD-YYYY)."
        )
        raise ValueError(message) from error

    return pd.Timestamp(parsed_date).normalize()


def _validate_columns(
    dataframe: pd.DataFrame,
    required_columns: list[str],
    workbook_path: Path,
    sheet_name: str,
) -> None:
    """Raise a useful error when a worksheet does not have required headers."""
    missing_columns = []
    for column in required_columns:
        if column not in dataframe.columns:
            missing_columns.append(column)

    if missing_columns:
        missing_names = ", ".join(missing_columns)
        message = (
            f"{workbook_path.name}, worksheet {sheet_name!r}, is missing "
            f"required columns: {missing_names}."
        )
        raise ValueError(message)


def read_attendance_workbook(
    workbook_path: str | Path,
    required_columns: list[str],
) -> pd.DataFrame:
    """Read all date-named worksheets from one attendance workbook.

    The worksheet title supplies the authoritative date. If a Date column is
    also present in the worksheet, its values must agree with that title.
    """
    workbook_path = Path(workbook_path)
    daily_frames = []

    # Close the Excel file promptly after all of its worksheets have been read.
    with pd.ExcelFile(workbook_path) as workbook:
        if not workbook.sheet_names:
            raise ValueError(f"{workbook_path.name} does not contain worksheets.")

        for sheet_name in workbook.sheet_names:
            sheet_date = _parse_sheet_date(sheet_name, workbook_path)
            sheet_data = pd.read_excel(workbook, sheet_name=sheet_name)
            _validate_columns(
                sheet_data,
                required_columns,
                workbook_path,
                sheet_name,
            )

            # Keep only the columns needed by the reconciliation.
            sheet_data = sheet_data[required_columns].copy()
            cell_dates = pd.to_datetime(sheet_data["Date"]).dt.normalize()

            # A date column that conflicts with the worksheet title is likely
            # a source-data mistake, so stop instead of comparing the wrong day.
            if not sheet_data.empty and not cell_dates.eq(sheet_date).all():
                message = (
                    f"{workbook_path.name}, worksheet {sheet_name!r}, contains "
                    "Date values that do not match its date-based worksheet title."
                )
                raise ValueError(message)

            sheet_data["Date"] = cell_dates
            daily_frames.append(sheet_data)

    if not daily_frames:
        return pd.DataFrame(columns=required_columns)

    return pd.concat(daily_frames, ignore_index=True)


def read_roster(roster_path: str | Path) -> pd.DataFrame:
    """Read the DYCD-ID-to-internal-name crosswalk from the first worksheet."""
    roster_path = Path(roster_path)
    roster_data = pd.read_excel(roster_path, sheet_name=0)
    _validate_columns(
        roster_data,
        ROSTER_COLUMNS,
        roster_path,
        "first worksheet",
    )

    # Return only fields needed for the name-to-ID lookup.
    return roster_data[ROSTER_COLUMNS].copy()
