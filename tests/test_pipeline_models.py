from datetime import datetime
from pathlib import Path

import numpy as np

from ocr_pipeline import pipeline as pipeline_module
from ocr_pipeline.config import PipelineConfig
from ocr_pipeline.models import AttendanceRecord
from ocr_pipeline.pipeline import OCRPipeline


def test_pipeline_populates_model_records_and_isolates_dates_and_crops(monkeypatch):
    image = np.full((600, 300, 3), 255, dtype=np.uint8)
    monkeypatch.setattr(pipeline_module.ingestion, "pdf_to_image", lambda _path: [image])
    monkeypatch.setattr(pipeline_module.deskew, "get_skew_angle", lambda _image: 0.0)
    monkeypatch.setattr(
        pipeline_module.table_detection, "get_vertical_line_positions",
        lambda _image: [60, 90, 140, 170, 200, 250],
    )
    monkeypatch.setattr(
        pipeline_module.table_detection, "get_horizontal_line_positions",
        lambda _image: [410, 440, 470, 500, 530, 570],
    )
    monkeypatch.setattr(
        pipeline_module.table_detection, "split_student_rows_and_handwritten_region",
        lambda _lines, _height: ([(470, 500), (500, 530)], (530, 570)),
    )
    dates = iter([datetime(2026, 10, 21), None])
    monkeypatch.setattr(
        pipeline_module.detect_date, "detect_sheet_date", lambda *_args: next(dates)
    )
    monkeypatch.setattr(pipeline_module.ocr, "remove_red_strikethrough", lambda crop: crop)
    names = iter(["Student A", "", "Student A", ""])
    monkeypatch.setattr(pipeline_module.ocr, "tesseract_ocr", lambda _crop: next(names))
    monkeypatch.setattr(
        pipeline_module.classification, "classify_attendance", lambda _crop: "Present"
    )
    monkeypatch.setattr(pipeline_module.ocr, "detect_handwritten_names", lambda _crop: True)
    pipeline = OCRPipeline(PipelineConfig(roster=["Student A"]))

    first = pipeline.run(Path("first.pdf"))
    second = pipeline.run(Path("second.pdf"))

    assert first.sheet_date == datetime(2026, 10, 21)
    assert second.sheet_date is None
    assert [record.record_index for record in first.records] == [1, 2, 3]
    strong, flagged, handwritten = first.records
    assert strong.matched_name == "Student A"
    assert strong.match_score == 100.0
    assert strong.review_crop is None
    assert flagged.needs_review and flagged.review_crop is not None
    assert not np.shares_memory(flagged.review_crop, image)
    assert handwritten.is_handwritten and handwritten.needs_review
    assert handwritten.review_crop is not None
    assert not np.shares_memory(handwritten.review_crop, image)


def test_record_equality_does_not_compare_numpy_crops():
    fields = dict(
        page_index=0,
        record_index=1,
        ocr_name="A",
        cleaned_name="A",
        matched_name=None,
        match_score=0.0,
        match_flag="OCRExtractionError",
        attendance_status="Present",
    )
    left = AttendanceRecord(**fields, review_crop=np.ones((2, 2)))
    right = AttendanceRecord(**fields, review_crop=np.zeros((2, 2)))

    assert left == right
