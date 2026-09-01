from ocr_pipeline.reconciliation import clean_ocr_name, fuzzy_match_names
import pandas as pd
import re

SAMPLE_OCR_NAME = 'Ciutron, Tyler 7 |'
SAMPLE_DF = pd.read_csv('tests/sample_scans/OCR_Name_Attendance.csv')

def build_roster():
    student_roster = []
    with open("data/student_roster.txt", "r", encoding="utf-8") as file:
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
    df_fuzzy_names.to_csv("./tests/sample_scans/df_fuzzy_names.csv", index=False)