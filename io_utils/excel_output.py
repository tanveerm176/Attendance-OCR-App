import pandas as pd
from pathlib import Path


def export_attendance(df: pd.DataFrame, output_path: Path) -> None:
    if "Date" not in df.columns:
        raise ValueError("Attendance data must contain a 'Date' column")
    if df.empty:
        raise ValueError("Cannot export an empty attendance DataFrame")

    attendance = df.copy()
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