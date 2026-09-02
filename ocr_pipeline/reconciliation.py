import re
import pandas as pd
from rapidfuzz import process, fuzz

from ocr_pipeline.exceptions import OCRExtractionError, NoMatchFoundError

LOW_MATCH_SCORE_FLOOR = 30 # any match_score below this is treated as noise not a 
                           #    genuine match with a low confidence score
LOW_MATCH_LABEL = 'Low Match - Needs Review'                           
STRONG_MATCH_LABEL = 'Strong Match'

def clean_ocr_name(name: str) -> str:
    cleaned_name = re.sub(r'[^a-zA-Z\s\-\']', '', name).strip()
    cleaned_spaces_name = re.sub(r'\s+', ' ', cleaned_name).strip()
    return cleaned_spaces_name

def fuzzy_match_names(df: pd.DataFrame, roster: list[str],
                      name_col: str ='ocr_raw', threshold: int = 80) -> pd.DataFrame:

    cleaned_names = []
    matched_names = []
    matched_scores = []
    flags = []

    for raw_name in df[name_col]:
        cleaned = clean_ocr_name(raw_name)
        cleaned_names.append(cleaned)

        # Case 1: nothing usable survived cleaning (empty, numeric-only,
        #   punctuation-only). No point handing this to the fuzzy matcher, 
        #   add None as the match_name, 0 for match_score, 
        #   and flag with OCRExtractionError & move to next name in column 
        if not cleaned or len(cleaned)<2:
            matched_names.append(None)
            matched_scores.append(0)
            flags.append(OCRExtractionError.__name__)
            continue

        # For names that pass Case 1, send to fuzzy_matcher
        result = process.extractOne(raw_name, roster, scorer=fuzz.token_sort_ratio)

        if not result:
            # extractOne can return None if roster is empty — distinct from
            #   a low-scoring match, but flagged the same way for MVP
            matched_names.append(None)
            matched_scores.append(0)
            flags.append(NoMatchFoundError.__name__)
            continue

        # For names that pass Case 1 & return a result from fuzzy_match 
        #   match_score > 80 threshold applied here
        match_name, match_score, _ = result
        matched_names.append(match_name)
        matched_scores.append(match_score)

        # Case 2: a match was found, but the match_score is below the noise floor 
        #   flag is as effectively no match, but keep the best guess name/score 
        #   for manual review
        if match_score < LOW_MATCH_SCORE_FLOOR:
            flags.append(NoMatchFoundError.__name__)

        elif match_score < threshold:
            flags.append(LOW_MATCH_LABEL) # match_scores 30-79

        else:
            flags.append(STRONG_MATCH_LABEL) # match_score >= 80


    df['Cleaned Name'] = cleaned_names
    df['Matched Name'] = matched_names
    df['Matched Score'] = matched_scores
    df['Raised Flags'] = flags

    return df