from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from io_utils.excel_output import export_attendance


def test_export_attendance_creates_date_sheets_and_formats_date_column(tmp_path):
    output_path = tmp_path / "attendance.xlsx"
    dataframe = pd.DataFrame(
        {
            "Date": [
                datetime(2026, 10, 2),
                datetime(2026, 9, 15),
                datetime(2026, 10, 2, 15, 30),
            ],
            "Student": ["A", "B", "C"],
        }
    )

    export_attendance(dataframe, output_path)

    workbook = load_workbook(output_path, data_only=False)
    assert workbook.sheetnames == ["09-15-2026", "10-02-2026"]
    assert list(workbook["09-15-2026"].values) == [
        ("Date", "Student"),
        (datetime(2026, 9, 15), "B"),
    ]
    assert workbook["09-15-2026"]["A2"].number_format == "MM/DD/YYYY"
    assert workbook["10-02-2026"]["A2"].number_format == "MM/DD/YYYY"
    assert workbook["10-02-2026"]["A3"].number_format == "MM/DD/YYYY"


@pytest.mark.parametrize(
    "dataframe, message",
    [
        (pd.DataFrame({"Student": ["A"]}), "must contain a 'Date' column"),
        (pd.DataFrame({"Date": [datetime(2026, 10, 2)], "Student": ["A"]}).iloc[0:0], "empty"),
        (pd.DataFrame({"Date": [None], "Student": ["A"]}), "without a date"),
    ],
)
def test_export_attendance_rejects_invalid_data(tmp_path, dataframe, message):
    with pytest.raises(ValueError, match=message):
        export_attendance(dataframe, tmp_path / "attendance.xlsx")
