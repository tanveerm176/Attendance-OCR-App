from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import load_workbook

from io_utils.excel_output import export_attendance
from ocr_pipeline.models import AttendanceBatch, AttendanceRecord, DailyAttendance


def make_record(name, attendance="Present", cleaned=None, matched=None,
                score=100.0, flag="Strong Match"):
    return AttendanceRecord(
        page_index=0,
        record_index=1,
        ocr_name=name,
        cleaned_name=cleaned if cleaned is not None else name,
        matched_name=matched,
        match_score=score,
        match_flag=flag,
        attendance_status=attendance,
    )


def test_export_attendance_creates_date_sheets_and_formats_date_column(tmp_path):
    output_path = tmp_path / "attendance.xlsx"
    batch = AttendanceBatch(
        source_folder=tmp_path,
        attendance_group=None,
        attendance_sheets=[
            DailyAttendance(tmp_path / "a.pdf", datetime(2026, 10, 2), records=[
                make_record("A", matched="Student A"),
            ]),
            DailyAttendance(tmp_path / "b.pdf", datetime(2026, 9, 15), records=[
                make_record("B", attendance="Absent", matched="Student B"),
            ]),
            DailyAttendance(tmp_path / "c.pdf", datetime(2026, 10, 2, 15, 30), records=[
                make_record("An exceptionally long OCR name",
                            cleaned="An exceptionally long cleaned name",
                            matched="Student C", score=82.5,
                            flag="Low Match - Needs Review"),
            ]),
            DailyAttendance(tmp_path / "d.pdf", datetime(2026, 10, 2), records=[
                make_record("Write-in\nname", cleaned="Write-in name",
                            matched="Student D", score=0.0, flag="NEED-MANUAL-ENTRY"),
            ]),
        ],
    )

    export_attendance(batch, output_path)

    workbook = load_workbook(output_path, data_only=False)
    assert workbook.sheetnames == ["09-15-2026", "10-02-2026"]
    assert list(workbook["09-15-2026"].values) == [
        (
            "Date",
            "OCR Raw",
            "Attendance Status",
            "OCR Cleaned",
            "Matched Name",
            "Matched Score",
            "Flag",
        ),
        (
            datetime(2026, 9, 15),
            "B",
            "Absent",
            "B",
            "Student B",
            100.0,
            "Strong Match",
        ),
    ]
    assert workbook["09-15-2026"]["A2"].number_format == "MM/DD/YYYY"
    assert workbook["10-02-2026"]["A2"].number_format == "MM/DD/YYYY"
    assert workbook["10-02-2026"]["A3"].number_format == "MM/DD/YYYY"
    worksheet = workbook["10-02-2026"]
    assert [worksheet.cell(row=row, column=6).value for row in (2, 3, 4)] == [
        100.0, 82.5, 0.0
    ]
    assert worksheet["A1"].alignment.horizontal == "center"
    assert worksheet["A2"].alignment.horizontal == "center"
    assert worksheet["A1"].font.bold is True
    assert worksheet["A1"].fill.fgColor.rgb == "001F4E78"
    assert worksheet["A2"].border.left.style == "thin"
    assert worksheet["B2"].border.bottom.style == "thin"
    assert worksheet["A2"].fill.fgColor.rgb == "008DB4E2"
    assert worksheet["C2"].fill.fgColor.rgb == "008DB4E2"
    assert workbook["10-02-2026"]["A3"].fill.fgColor.rgb == "00FFC000"
    assert workbook["10-02-2026"]["A4"].fill.fgColor.rgb == "00FFC000"
    assert workbook["09-15-2026"]["A2"].fill.fgColor.rgb == "00DA9694"
    assert worksheet.column_dimensions["B"].width >= len("OCR Raw") + 2
    assert worksheet.column_dimensions["B"].width == workbook[
        "09-15-2026"
    ].column_dimensions["B"].width
    assert worksheet.column_dimensions["B"].width >= len(
        "An exceptionally long OCR name"
    ) + 2
    assert worksheet["B4"].alignment.wrap_text is not True
    assert worksheet.row_dimensions[4].height is None


def test_export_attendance_rejects_empty_batch(tmp_path):
    batch = AttendanceBatch(source_folder=tmp_path, attendance_group=None)
    with pytest.raises(ValueError, match="empty"):
        export_attendance(batch, tmp_path / "attendance.xlsx")


def test_export_attendance_rejects_missing_sheet_date(tmp_path):
    batch = AttendanceBatch(
        source_folder=tmp_path,
        attendance_group=None,
        attendance_sheets=[DailyAttendance(tmp_path / "sheet.pdf", records=[make_record("A")])],
    )
    with pytest.raises(ValueError, match="without a date"):
        export_attendance(batch, tmp_path / "attendance.xlsx")
