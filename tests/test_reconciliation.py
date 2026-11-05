import re

import pandas as pd

from ocr_pipeline.constants import (
    EMPTY_ROW_LABEL,
    LOW_MATCH_LABEL,
    NEED_MANUAL_ENTRY_FLAG,
    STRONG_MATCH_LABEL,
    WRITTEN_NAME_MARKER,
)
from ocr_pipeline.exceptions import NoMatchFoundError, OCRExtractionError
from ocr_pipeline.reconciliation import clean_ocr_name, fuzzy_match_names, match_name

SAMPLE_OCR_NAME = 'Ciutron, Tyler 7 |'
SAMPLE_DF = pd.read_csv('tests/sample_data/OCR_Name_Attendance.csv')

def build_roster():
    student_roster = []
    with open("tests/sample_data/sample_roster.txt", "r", encoding="utf-8") as file:
        for line in file:
            comma_stripped_name = re.sub(r',', '', line)
            student_roster.append(comma_stripped_name)
    return student_roster

def test_clean_ocr_name():
    clean_sample_name = clean_ocr_name(SAMPLE_OCR_NAME)
    assert clean_sample_name == 'Ciutron Tyler'

def test_fuzzy_match_names():
    student_roster_list = build_roster()
    df_fuzzy_names = fuzzy_match_names(SAMPLE_DF, student_roster_list, name_col='OCR Names')
    df_fuzzy_names.to_csv("tests/sample_data/df_fuzzy_names.csv", index=False)


def test_blank_name_in_empty_attendance_cell_is_not_flagged_for_manual_review():
    dataframe = pd.DataFrame(
        {
            "ocr_raw": ["", ""],
            "attendance": ["EMPTY CELL", "Present"],
        }
    )

    result = fuzzy_match_names(dataframe, ["Student A"])

    assert result["flag"].tolist() == ["EMPTY CELL", "OCRExtractionError"]


def test_match_name_returns_strong_match_details():
    assert match_name("Student A", "Present", ["Student A"], 80, 30) == (
        "Student A",
        "Student A",
        100.0,
        STRONG_MATCH_LABEL,
    )


def test_match_name_preserves_special_case_flags():
    assert match_name(WRITTEN_NAME_MARKER, "Present", [], 80, 30) == (
        WRITTEN_NAME_MARKER,
        None,
        0.0,
        NEED_MANUAL_ENTRY_FLAG,
    )
    assert match_name("", EMPTY_ROW_LABEL, ["Student A"], 80, 30) == (
        "",
        None,
        0.0,
        EMPTY_ROW_LABEL,
    )
    assert match_name("", "Present", ["Student A"], 80, 30) == (
        "",
        None,
        0.0,
        OCRExtractionError.__name__,
    )
    assert match_name("Student A", "Present", [], 80, 30) == (
        "Student A",
        None,
        0.0,
        NoMatchFoundError.__name__,
    )


def test_match_name_applies_match_score_thresholds():
    low_confidence_match = match_name(
        "Jonathan Smith", "Present", ["Jonathan Smyth"], 100, 30
    )
    assert low_confidence_match[1] == "Jonathan Smyth"
    assert low_confidence_match[3] == LOW_MATCH_LABEL

    noise_match = match_name(
        "Jonathan Smith", "Present", ["Jonathan Smyth"], 100, 99
    )
    assert noise_match[1] == "Jonathan Smyth"
    assert noise_match[3] == NoMatchFoundError.__name__