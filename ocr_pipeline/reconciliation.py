import re
import pandas as pd
from rapidfuzz import process, fuzz

def clean_ocr_name(name: str) -> str:
    cleaned_name = re.sub(r'[^a-zA-Z\s\-\']', '', name).strip()
    cleaned_spaces_name = re.sub(r'\s+', ' ', cleaned_name).strip()
    return cleaned_spaces_name

def fuzzy_match_names(df: pd.DataFrame, roster: list[str],
                      name_col: str ='ocr_raw', threshold: int = 80) -> pd.DataFrame:

    matched_names = []
    match_scores = []

    for raw_name in df[name_col]:
        result = process.extractOne(raw_name, roster, scorer=fuzz.token_sort_ratio)

        if result and result[1] >= threshold:
            matched_names.append(result[0])
            match_scores.append(result[1])

        else:
            matched_names.append(result[0])
            match_scores.append(result[1] if result else 0)

    df['matched_name'] = matched_names
    df['match_scores'] = match_scores

    return df