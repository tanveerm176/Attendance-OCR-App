from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from openpyxl import load_workbook

from io_utils.excel_output import export_attendance
from ocr_pipeline import batch_cli
from ocr_pipeline.batch_cli import process_pdf_folder
from ocr_pipeline.models import AttendanceBatch, AttendanceRecord, DailyAttendance


def make_record(name, attendance="Present"):
    return AttendanceRecord(
        page_index=0,
        record_index=1,
        ocr_name=name,
        cleaned_name=name,
        matched_name=name,
        match_score=100.0,
        match_flag="Strong Match",
        attendance_status=attendance,
        review_crop=np.ones((2, 2), dtype=np.uint8),
    )


class FakePipeline:
    def run(self, pdf_path: Path) -> DailyAttendance:
        return DailyAttendance(
            source_pdf=pdf_path,
            sheet_date=datetime(2026, 10, 21),
            records=[
                make_record(pdf_path.stem),
                make_record(f"{pdf_path.stem} Student", "Absent"),
            ],
        )


def test_batch_processes_pdfs_and_records_source_paths_without_review_crops(tmp_path):
    (tmp_path / "b.pdf").touch()
    (tmp_path / "A.PDF").touch()

    result = process_pdf_folder(
        tmp_path, FakePipeline(), source_path_root=r"C:\Attendance\Input"
    )

    assert isinstance(result, AttendanceBatch)
    assert result.source_folder == tmp_path
    assert [record.ocr_name for sheet in result.attendance_sheets for record in sheet.records] == [
        "A", "A Student", "b", "b Student"
    ]
    assert [sheet.source_pdf_display_path for sheet in result.attendance_sheets] == [
        r"C:\Attendance\Input\A.PDF", r"C:\Attendance\Input\b.pdf"
    ]
    assert all(
        record.review_crop is None
        for sheet in result.attendance_sheets
        for record in sheet.records
    )


def test_batch_rejects_empty_or_missing_directory(tmp_path):
    with pytest.raises(ValueError, match="No PDF files found"):
        process_pdf_folder(tmp_path, FakePipeline())
    with pytest.raises(ValueError, match="does not exist"):
        process_pdf_folder(tmp_path / "missing", FakePipeline())


def test_batch_uses_local_resolved_path_without_override(tmp_path):
    pdf_path = tmp_path / "sheet.pdf"
    pdf_path.touch()

    batch = process_pdf_folder(tmp_path, FakePipeline())

    assert batch.attendance_sheets[0].source_pdf_display_path == str(pdf_path.resolve())


def test_export_attendance_merges_source_path_by_pdf_group(tmp_path):
    output_path = tmp_path / "attendance.xlsx"
    one_path = r"C:\Attendance\Input\one class.pdf"
    two_path = r"C:\Attendance\Input\two.pdf"
    batch = AttendanceBatch(
        source_folder=tmp_path,
        attendance_group=None,
        attendance_sheets=[
            DailyAttendance(
                source_pdf=tmp_path / "one.pdf",
                sheet_date=datetime(2026, 10, 21),
                source_pdf_display_path=one_path,
                records=[make_record("A"), make_record("B", "Absent")],
            ),
            DailyAttendance(
                source_pdf=tmp_path / "two.pdf",
                sheet_date=datetime(2026, 10, 21),
                source_pdf_display_path=two_path,
                records=[make_record("C"), make_record("D", "Absent")],
            ),
            DailyAttendance(
                source_pdf=tmp_path / "two.pdf",
                sheet_date=datetime(2026, 10, 22),
                source_pdf_display_path=two_path,
                records=[make_record("E")],
            ),
        ],
    )

    export_attendance(batch, output_path)

    workbook = load_workbook(output_path)
    worksheet = workbook["10-21-2026"]
    assert worksheet["H1"].value == "Source PDF Path"
    assert worksheet["H2"].value == "one class.pdf"
    assert worksheet["H2"].hyperlink.target == "file:///C:/Attendance/Input/one%20class.pdf"
    assert worksheet["H4"].value == "two.pdf"
    assert worksheet["H4"].hyperlink.target == "file:///C:/Attendance/Input/two.pdf"
    assert {str(merged) for merged in worksheet.merged_cells.ranges} >= {"H2:H3", "H4:H5"}
    next_date_sheet = workbook["10-22-2026"]
    assert next_date_sheet["H1"].value == "Source PDF Path"
    assert next_date_sheet["H2"].value == "two.pdf"
    assert next_date_sheet["H2"].hyperlink.target == "file:///C:/Attendance/Input/two.pdf"


def test_export_uses_local_path_when_other_sheet_has_display_path(tmp_path):
    local_pdf = tmp_path / "local.pdf"
    batch = AttendanceBatch(
        source_folder=tmp_path,
        attendance_group=None,
        attendance_sheets=[
            DailyAttendance(
                source_pdf=local_pdf,
                sheet_date=datetime(2026, 10, 21),
                records=[make_record("A")],
            ),
            DailyAttendance(
                source_pdf=tmp_path / "other.pdf",
                sheet_date=datetime(2026, 10, 21),
                source_pdf_display_path=r"C:\Attendance\Input\other.pdf",
                records=[make_record("B")],
            ),
        ],
    )
    output_path = tmp_path / "mixed.xlsx"

    export_attendance(batch, output_path)

    worksheet = load_workbook(output_path)["10-21-2026"]
    assert worksheet["H2"].value == "local.pdf"
    assert worksheet["H2"].hyperlink.target == local_pdf.resolve().as_uri()
    assert worksheet["H3"].value == "other.pdf"


def test_run_batch_creates_workbook_with_host_source_paths(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "sheet.pdf").touch()
    output_path = tmp_path / "output" / "attendance.xlsx"
    monkeypatch.setattr(batch_cli, "build_roster", lambda: ["Student"])
    monkeypatch.setattr(batch_cli, "OCRPipeline", lambda config: FakePipeline())

    result = batch_cli.run_batch(
        input_dir, output_path, source_path_root=r"C:\Attendance\Input"
    )

    assert result == output_path
    worksheet = load_workbook(output_path)["10-21-2026"]
    assert worksheet["B2"].value == "sheet"
    assert worksheet["H2"].value == "sheet.pdf"
    assert worksheet["H2"].hyperlink.target == "file:///C:/Attendance/Input/sheet.pdf"
