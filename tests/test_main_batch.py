from datetime import date
from pathlib import Path

import numpy as np
import pytest

from main import build_excel_output, process_pdf_folder
from ocr_pipeline.models import AttendanceBatch, AttendanceRecord, DailyAttendance


class FakePipeline:
    def __init__(self):
        self.sheets = []
        self.events = []

    def run(self, pdf_path: Path) -> DailyAttendance:
        self.events.append(("process", pdf_path.name))
        record = AttendanceRecord(
            page_index=0,
            record_index=1,
            ocr_name=pdf_path.stem,
            cleaned_name=pdf_path.stem,
            matched_name=None,
            match_score=0.0,
            match_flag="NoMatchFoundError",
            attendance_status="Present",
            review_crop=np.ones((2, 2), dtype=np.uint8),
        )
        sheet = DailyAttendance(source_pdf=pdf_path, records=[record])
        self.sheets.append(sheet)
        return sheet


def test_process_pdf_folder_collects_sheets_in_filename_order(tmp_path):
    (tmp_path / "b.pdf").touch()
    (tmp_path / "A.PDF").touch()
    (tmp_path / "ignore.txt").touch()
    pipeline = FakePipeline()

    result = process_pdf_folder(tmp_path, pipeline)

    assert isinstance(result, AttendanceBatch)
    assert result.source_folder == tmp_path
    assert result.attendance_group is None
    assert [sheet.source_pdf.name for sheet in result.attendance_sheets] == [
        "A.PDF", "b.pdf"
    ]
    assert all(
        actual is expected
        for actual, expected in zip(result.attendance_sheets, pipeline.sheets)
    )
    assert all(sheet.records[0].review_crop is not None for sheet in result.attendance_sheets)


def test_process_pdf_folder_raises_when_folder_has_no_pdfs(tmp_path):
    with pytest.raises(ValueError, match="No PDF files found"):
        process_pdf_folder(tmp_path, FakePipeline())


def test_process_pdf_folder_reviews_each_sheet_in_place_before_next_pdf(tmp_path):
    (tmp_path / "a.pdf").touch()
    (tmp_path / "b.pdf").touch()
    pipeline = FakePipeline()

    def review(sheet: DailyAttendance) -> None:
        pipeline.events.append(("review", sheet.source_pdf.name))
        record = sheet.records[0]
        assert record.review_crop is not None
        record.matched_name = "Student"
        record.match_flag = "Resolved - Manual Review"
        record.reviewed = True
        record.review_crop = None

    result = process_pdf_folder(tmp_path, pipeline, review_callback=review)

    assert pipeline.events == [
        ("process", "a.pdf"), ("review", "a.pdf"),
        ("process", "b.pdf"), ("review", "b.pdf"),
    ]
    for sheet, original in zip(result.attendance_sheets, pipeline.sheets):
        assert sheet is original
        assert sheet.records[0].matched_name == "Student"
        assert sheet.records[0].reviewed is True
        assert sheet.records[0].review_crop is None


def test_build_excel_output_uses_folder_and_current_date(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder_path = tmp_path / "Attendance Batch"

    output_path = build_excel_output(folder_path, date(2026, 10, 2))

    assert output_path == Path("output/Attendance Batch_10-02-2026.xlsx")
    assert output_path.parent.is_dir()
