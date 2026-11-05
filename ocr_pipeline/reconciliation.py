import re
import pandas as pd
from rapidfuzz import process, fuzz, utils

from ocr_pipeline.constants import (
    EMPTY_ROW_LABEL,
    LOW_MATCH_LABEL,
    NEED_MANUAL_ENTRY_FLAG,
    STRONG_MATCH_LABEL,
    WRITTEN_NAME_MARKER,
)
from ocr_pipeline.exceptions import OCRExtractionError, NoMatchFoundError

def clean_ocr_name(name: str) -> str:
    """Remove OCR noise and normalize whitespace in a detected name."""
    cleaned_name = re.sub(r'[^a-zA-Z\s\-\']', '', name).strip()
    cleaned_spaces_name = re.sub(r'\s+', ' ', cleaned_name).strip()
    return cleaned_spaces_name


def fuzzy_match_names(df: pd.DataFrame, roster: list[str], name_col: str = "ocr_raw", 
                      threshold: int = 80, low_match_floor: int = 30) -> pd.DataFrame:
    """Apply per-name matching to a DataFrame and append its result columns."""
    cleaned_names = []
    matched_names = []
    matched_scores = []
    flags = []

    for row_position, raw_name in enumerate(df[name_col].tolist()):
        
        attendance_status = (df.iloc[row_position]["attendance"] if "attendance" in df.columns else None)

        cleaned, matched_name, matched_score, match_flag = match_name(
            raw_name,
            attendance_status,
            roster,
            threshold,
            low_match_floor,
        )
        cleaned_names.append(cleaned)
        matched_names.append(matched_name)
        matched_scores.append(matched_score)
        flags.append(match_flag)

    df['cleaned_name'] = cleaned_names
    df['matched_name'] = matched_names
    df['matched_score'] = matched_scores
    df['flag'] = flags

    return df


def match_name(raw_name: str, attendance_status: str | None, roster: list[str], 
               threshold: int, low_match_floor: int) -> tuple[str, str | None, float, str]:
    """Clean one OCR name, match it against the roster, and return its flag."""
    cleaned_name = clean_ocr_name(raw_name)

    # Handwritten-name regions are handled manually instead of roster matching.
    if cleaned_name == WRITTEN_NAME_MARKER:
        return cleaned_name, None, 0.0, NEED_MANUAL_ENTRY_FLAG

    # Empty or one-character OCR results cannot be matched reliably.
    # Preserve empty attendance rows as EMPTY CELL rather than review errors.
    if not cleaned_name or len(cleaned_name) < 2:
        flag = (
            EMPTY_ROW_LABEL
            if not cleaned_name and attendance_status == EMPTY_ROW_LABEL
            else OCRExtractionError.__name__
        )
        return cleaned_name, None, 0.0, flag

    # Token-sort matching tolerates OCR word-order differences; the processor
    # normalizes case and spacing before comparing roster names.
    result = process.extractOne(
        cleaned_name,
        roster,
        scorer=fuzz.token_sort_ratio,
        processor=utils.default_process,
    )
    # An empty roster produces no candidate, distinct from a low-scoring match.
    if result is None:
        return cleaned_name, None, 0.0, NoMatchFoundError.__name__

    matched_name, score, _ = result
    score = round(score, 2)

    # Keep the best candidate and score even below the noise floor for review.
    if score < low_match_floor:
        flag = NoMatchFoundError.__name__
    elif score < threshold:
        flag = LOW_MATCH_LABEL
    else:
        flag = STRONG_MATCH_LABEL

    return cleaned_name, matched_name, score, flag
