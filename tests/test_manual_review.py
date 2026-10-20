import base64

import cv2
import numpy as np
import pandas as pd
import pytest

from ocr_pipeline.manual_review import (
    RESOLVED_MANUALLY_FLAG,
    REVIEW_CROP_COLUMN,
    REVIEW_FLAGS,
    _encode_preview,
    review_flagged_records,
)


def _review_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ocr_raw": [
                "",
                "Tyler Ciutron",
                "Unknown",
                "WRITTEN NAME DETECTED",
                "Student Four",
            ],
            "matched_name": [None, "Tyler Cituon", None, None, "Student Four"],
            "matched_score": [0.0, 72.0, 12.0, 0.0, 100.0],
            "attendance": ["Present", "Present", "Present", "Present", "Present"],
            "flag": [
                "OCRExtractionError",
                "Low Match - Needs Review",
                "NoMatchFoundError",
                "NEED-MANUAL-ENTRY",
                "Strong Match",
            ],
            REVIEW_CROP_COLUMN: [
                np.full((12, 20, 3), 255, dtype=np.uint8) for _ in range(5)
            ],
        }
    )


def test_review_flagged_records_updates_selections_and_preserves_skips():
    dataframe = _review_dataframe()
    selections = iter(["Tyler Ciutron", None, "Student Two", "Student Three"])
    seen_flags = []

    def choose_name(image, flag, _text, _score, _roster, _suggestion):
        assert isinstance(image, np.ndarray)
        seen_flags.append(flag)
        return next(selections)

    result = review_flagged_records(
        dataframe,
        ["Tyler Ciutron", "Student Two", "Student Three"],
        dialog=choose_name,
    )

    assert seen_flags == [
        "OCRExtractionError",
        "Low Match - Needs Review",
        "NoMatchFoundError",
        "NEED-MANUAL-ENTRY",
    ]
    assert result["matched_name"].tolist() == [
        "Tyler Ciutron",
        "Tyler Cituon",
        "Student Two",
        "Student Three",
        "Student Four",
    ]
    assert result["flag"].tolist() == [
        RESOLVED_MANUALLY_FLAG,
        "Low Match - Needs Review",
        RESOLVED_MANUALLY_FLAG,
        RESOLVED_MANUALLY_FLAG,
        "Strong Match",
    ]
    assert dataframe["flag"].tolist()[0] == "OCRExtractionError"


def test_review_flagged_records_skips_gui_when_no_rows_need_review(monkeypatch):
    import tkinter

    monkeypatch.setattr(
        tkinter,
        "Tk",
        lambda: pytest.fail("Tk should not be created when there are no reviews"),
    )
    dataframe = _review_dataframe().iloc[[4]].copy()

    result = review_flagged_records(dataframe, [])

    assert result["flag"].tolist() == ["Strong Match"]


def test_review_flagged_records_uses_visible_root_for_review_window(monkeypatch):
    from ocr_pipeline import manual_review

    class FakeRoot:
        destroyed = False

        def withdraw(self):
            pytest.fail("The review root must not be withdrawn")

        def destroy(self):
            self.destroyed = True

    root = FakeRoot()
    shown_roots = []
    monkeypatch.setattr(manual_review.tk, "Tk", lambda: root)
    monkeypatch.setattr(
        manual_review,
        "_show_review_queue",
        lambda _dataframe, _positions, _roster, *, parent: shown_roots.append(parent),
    )

    manual_review.review_flagged_records(_review_dataframe(), ["Student A"])

    assert shown_roots == [root]
    assert root.destroyed


def test_empty_attendance_rows_are_not_queued_for_review():
    dataframe = pd.DataFrame(
        {
            "ocr_raw": [""],
            "matched_name": [None],
            "matched_score": [0.0],
            "attendance": ["EMPTY CELL"],
            "flag": ["EMPTY CELL"],
            REVIEW_CROP_COLUMN: [np.full((12, 20, 3), 255, dtype=np.uint8)],
        }
    )

    result = review_flagged_records(
        dataframe,
        [],
        dialog=lambda *_args: pytest.fail("Empty table row should not be reviewed"),
    )

    assert result["flag"].tolist() == ["EMPTY CELL"]


def test_review_flagged_records_rejects_selection_outside_roster():
    with pytest.raises(ValueError, match="not present in the roster"):
        review_flagged_records(
            _review_dataframe().iloc[[0]],
            ["Student A"],
            dialog=lambda *_args: "Not In Roster",
        )


def test_all_manual_review_triggers_are_supported():
    assert REVIEW_FLAGS == {
        "OCRExtractionError",
        "NoMatchFoundError",
        "Low Match - Needs Review",
        "NEED-MANUAL-ENTRY",
    }


def test_encode_preview_returns_decodable_png():
    image = np.full((20, 40, 3), 255, dtype=np.uint8)

    encoded = _encode_preview(image)

    png = np.frombuffer(base64.b64decode(encoded), dtype=np.uint8)
    decoded = cv2.imdecode(png, cv2.IMREAD_COLOR)
    assert decoded.shape == (20, 40, 3)
