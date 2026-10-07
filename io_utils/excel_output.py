import pandas as pd
from pathlib import Path

from io_utils.excel_formatting import format_attendance_worksheet


OUTPUT_COLUMNS = {
    "Date": "Date",
    "ocr_raw": "OCR Raw",
    "attendance": "Attendance Status",
    "cleaned_name": "OCR Cleaned",
    "matched_name": "Matched Name",
    "matched_score": "Matched Score",
    "flag": "Flag",
}


def export_attendance(df: pd.DataFrame, output_path: Path) -> None:
    if "Date" not in df.columns:
        raise ValueError("Attendance data must contain a 'Date' column")
    if df.empty:
        raise ValueError("Cannot export an empty attendance DataFrame")

    missing_columns = set(OUTPUT_COLUMNS).difference(df.columns)
    if missing_columns:
        raise ValueError(
            f"Attendance data is missing required columns: {sorted(missing_columns)}"
        )

    attendance = df[list(OUTPUT_COLUMNS)].rename(columns=OUTPUT_COLUMNS).copy()
    attendance["Date"] = pd.to_datetime(attendance["Date"], errors="raise").dt.normalize()
    if attendance["Date"].isna().any():
        raise ValueError("Attendance data contains rows without a date")

    with pd.ExcelWriter(
        output_path,
        engine="openpyxl",
        date_format="MM/DD/YYYY",
        datetime_format="MM/DD/YYYY",
    ) as writer:
        for sheet_date, date_df in attendance.groupby("Date", sort=True):
            # Excel worksheet names cannot contain "/", so use hyphens here.
            sheet_name = sheet_date.strftime("%m-%d-%Y")
            date_df.to_excel(writer, sheet_name=sheet_name, index=False)

            date_column = date_df.columns.get_loc("Date") + 1
            worksheet = writer.sheets[sheet_name]
            for row in worksheet.iter_rows(
                min_row=2,
                min_col=date_column,
                max_col=date_column,
                max_row=worksheet.max_row,
            ):
                row[0].number_format = "MM/DD/YYYY"
            format_attendance_worksheet(worksheet)

        worksheets = list(writer.sheets.values())
        column_count = max(worksheet.max_column for worksheet in worksheets)
        for column_index in range(1, column_count + 1):
            column_letter = worksheets[0].cell(
                row=1, column=column_index
            ).column_letter
            shared_width = max(
                worksheet.column_dimensions[column_letter].width
                for worksheet in worksheets
            )
            for worksheet in worksheets:
                worksheet.column_dimensions[column_letter].width = shared_width
