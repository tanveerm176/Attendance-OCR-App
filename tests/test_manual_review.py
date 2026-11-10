import base64
from pathlib import Path

import cv2
import numpy as np
import pytest

from ocr_pipeline import manual_review
from ocr_pipeline.constants import RESOLVED_MANUALLY_FLAG, REVIEW_FLAGS
from ocr_pipeline.manual_review import (
    _encode_preview,
    review_flagged_records,
)
from ocr_pipeline.models import AttendanceRecord, DailyAttendance


def _review_attendance() -> DailyAttendance:
    names = ["", "Tyler Ciutron", "Unknown", "WRITTEN NAME DETECTED", "Student Four"]
    matches = [None, "Tyler Cituon", None, None, "Student Four"]
    scores = [0.0, 72.0, 12.0, 0.0, 100.0]
    flags = [
        "OCRExtractionError",
        "Low Match - Needs Review",
        "NoMatchFoundError",
        "NEED-MANUAL-ENTRY",
        "Strong Match",
    ]
    records = [
        AttendanceRecord(
            page_index=0,
            record_index=index + 1,
            ocr_name=name,
            cleaned_name=name,
            matched_name=match,
            match_score=score,
            match_flag=flag,
            attendance_status="Present",
            is_handwritten=flag == "NEED-MANUAL-ENTRY",
            review_crop=(
                np.full((12, 20, 3), 255, dtype=np.uint8)
                if flag in REVIEW_FLAGS else None
            ),
        )
        for index, (name, match, score, flag) in enumerate(
            zip(names, matches, scores, flags)
        )
    ]
    return DailyAttendance(source_pdf=Path("sheet.pdf"), records=records)


def test_review_flagged_records_updates_in_place_and_preserves_skips():
    attendance = _review_attendance()
    original_records = list(attendance.records)
    skipped_crop = attendance.records[1].review_crop
    selections = iter(["Tyler Ciutron", None, "Student Two", "Student Three"])
    seen = []

    def choose_name(image, flag, text, score, roster, suggestion):
        assert isinstance(image, np.ndarray)
        seen.append((flag, text, score, suggestion))
        assert roster == ["Tyler Ciutron", "Student Two", "Student Three"]
        return next(selections)

    result = review_flagged_records(
        attendance,
        ["Tyler Ciutron", "Student Two", "Student Three"],
        dialog=choose_name,
    )

    assert result is None
    assert all(a is b for a, b in zip(attendance.records, original_records))
    assert seen == [
        ("OCRExtractionError", "", 0.0, None),
        ("Low Match - Needs Review", "Tyler Ciutron", 72.0, "Tyler Cituon"),
        ("NoMatchFoundError", "Unknown", 12.0, None),
        ("NEED-MANUAL-ENTRY", "WRITTEN NAME DETECTED", 0.0, None),
    ]
    assert [r.matched_name for r in attendance.records] == [
        "Tyler Ciutron", "Tyler Cituon", "Student Two", "Student Three", "Student Four"
    ]
    assert [r.match_flag for r in attendance.records] == [
        RESOLVED_MANUALLY_FLAG, "Low Match - Needs Review",
        RESOLVED_MANUALLY_FLAG, RESOLVED_MANUALLY_FLAG, "Strong Match",
    ]
    assert [r.reviewed for r in attendance.records] == [True, False, True, True, False]
    assert [r.needs_review for r in attendance.records] == [False, True, False, False, False]
    assert all(attendance.records[i].review_crop is None for i in (0, 2, 3, 4))
    assert attendance.records[1].review_crop is skipped_crop
    assert attendance.records[3].is_handwritten is True


def test_review_flagged_records_skips_gui_when_no_rows_need_review(monkeypatch):
    monkeypatch.setattr(
        manual_review.tk, "Tk",
        lambda: pytest.fail("Tk should not be created when there are no reviews"),
    )
    attendance = _review_attendance()
    already_reviewed = attendance.records[0]
    already_reviewed.reviewed = True
    attendance.records = [already_reviewed, attendance.records[4]]

    assert review_flagged_records(attendance, []) is None
    assert [record.match_flag for record in attendance.records] == [
        "OCRExtractionError", "Strong Match"
    ]


def test_review_flagged_records_uses_visible_root_and_original_records(monkeypatch):
    class FakeRoot:
        destroyed = False

        def withdraw(self):
            pytest.fail("The review root must not be withdrawn")

        def destroy(self):
            self.destroyed = True

    root = FakeRoot()
    shown = []
    attendance = _review_attendance()
    monkeypatch.setattr(manual_review.tk, "Tk", lambda: root)
    monkeypatch.setattr(
        manual_review, "_show_review_queue",
        lambda sheet, records, roster, *, parent: shown.append((sheet, records, roster, parent)),
    )

    assert review_flagged_records(attendance, ["Student A"]) is None
    sheet, records, roster, parent = shown[0]
    assert sheet is attendance
    assert len(records) == 4
    assert all(record is attendance.records[i] for i, record in enumerate(records))
    assert roster == ["Student A"]
    assert parent is root
    assert root.destroyed


def test_review_window_is_destroyed_when_queue_raises(monkeypatch):
    class FakeRoot:
        destroyed = False

        def destroy(self):
            self.destroyed = True

    root = FakeRoot()
    monkeypatch.setattr(manual_review.tk, "Tk", lambda: root)

    def fail(*args, **kwargs):
        raise RuntimeError("queue failed")

    monkeypatch.setattr(manual_review, "_show_review_queue", fail)
    with pytest.raises(RuntimeError, match="queue failed"):
        review_flagged_records(_review_attendance(), ["Student A"])
    assert root.destroyed


def test_review_queue_confirms_skips_and_preserves_unvisited_records(monkeypatch):
    attendance = _review_attendance()
    skipped_crop = attendance.records[1].review_crop
    buttons = {}

    class FakeVariable:
        value = ""

        def set(self, value):
            self.value = value

        def get(self):
            return self.value

    selected = FakeVariable()

    class FakeWidget:
        def __init__(self, parent, **kwargs):
            if "command" in kwargs:
                buttons[kwargs["text"]] = kwargs["command"]

        def pack(self, **kwargs):
            pass

        def configure(self, **kwargs):
            pass

        def bind(self, *args):
            pass

        def focus_set(self):
            pass

    class FakeRoot:
        quit_called = False
        destroyed = False

        def title(self, *args):
            pass

        def resizable(self, *args):
            pass

        def protocol(self, name, callback):
            self.close = callback

        def update_idletasks(self):
            pass

        def deiconify(self):
            pass

        def lift(self):
            pass

        def focus_force(self):
            pass

        def mainloop(self):
            selected.set("Student A")
            buttons["Use selected name"]()
            buttons["Skip"]()
            self.close()

        def quit(self):
            self.quit_called = True

        def destroy(self):
            self.destroyed = True

    root = FakeRoot()
    monkeypatch.setattr(manual_review.tk, "Tk", lambda: root)
    monkeypatch.setattr(manual_review.tk, "StringVar", lambda: selected)
    monkeypatch.setattr(manual_review.tk, "PhotoImage", lambda **kwargs: object())
    for widget in ("Label", "Combobox", "Frame", "Button"):
        monkeypatch.setattr(manual_review.ttk, widget, FakeWidget)

    assert review_flagged_records(attendance, ["Student A"]) is None
    confirmed, skipped, unvisited = attendance.records[:3]
    assert confirmed.matched_name == "Student A"
    assert confirmed.match_flag == RESOLVED_MANUALLY_FLAG
    assert confirmed.reviewed is True
    assert confirmed.review_crop is None
    assert skipped.match_flag == "Low Match - Needs Review"
    assert skipped.reviewed is False
    assert skipped.review_crop is skipped_crop
    assert unvisited.needs_review is True
    assert root.quit_called and root.destroyed


def test_empty_attendance_rows_are_not_queued_for_review():
    attendance = _review_attendance()
    record = attendance.records[0]
    record.attendance_status = "EMPTY CELL"
    record.match_flag = "EMPTY CELL"
    record.review_crop = None
    attendance.records = [record]

    assert review_flagged_records(
        attendance, [],
        dialog=lambda *_args: pytest.fail("Empty table row should not be reviewed"),
    ) is None
    assert record.match_flag == "EMPTY CELL"


def test_review_flagged_records_rejects_selection_outside_roster():
    attendance = _review_attendance()
    record = attendance.records[0]
    original_crop = record.review_crop
    with pytest.raises(ValueError, match="not present in the roster"):
        review_flagged_records(
            attendance, ["Student A"], dialog=lambda *_args: "Not In Roster"
        )
    assert record.match_flag == "OCRExtractionError"
    assert record.matched_name is None
    assert record.reviewed is False
    assert record.review_crop is original_crop


@pytest.mark.parametrize("use_dialog", [False, True])
def test_review_flagged_records_rejects_missing_crop(use_dialog):
    attendance = _review_attendance()
    attendance.records[0].review_crop = None
    dialog = (lambda *_args: None) if use_dialog else None
    with pytest.raises(ValueError, match="Missing image crop for OCR review row 1"):
        review_flagged_records(attendance, ["Student A"], dialog=dialog)


def test_review_flagged_records_rejects_empty_roster_for_gui():
    with pytest.raises(ValueError, match="empty roster"):
        review_flagged_records(_review_attendance(), [])


def test_all_manual_review_triggers_are_supported():
    assert REVIEW_FLAGS == {
        "OCRExtractionError", "NoMatchFoundError",
        "Low Match - Needs Review", "NEED-MANUAL-ENTRY",
    }


@pytest.mark.parametrize("shape", [(20, 40), (20, 40, 3)])
def test_encode_preview_returns_decodable_png(shape):
    image = np.full(shape, 255, dtype=np.uint8)
    encoded = _encode_preview(image)
    png = np.frombuffer(base64.b64decode(encoded), dtype=np.uint8)
    decoded = cv2.imdecode(png, cv2.IMREAD_COLOR)
    assert decoded.shape == (20, 40, 3)
