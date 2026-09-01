from pathlib import Path
import cv2
from ocr_pipeline.classification import classify_attendance

PRESENT_CELL = Path('tests/sample_scans/present_cell.png')
ABSENT_CELL = Path('tests/sample_scans/absent_cell.png')

present_img = cv2.imread(PRESENT_CELL)
assert present_img is not None
present_img_rgb = cv2.cvtColor(present_img, cv2.COLOR_BGR2RGB)

absent_img = cv2.imread(ABSENT_CELL)
assert absent_img is not None
absent_img_rgb = cv2.cvtColor(absent_img, cv2.COLOR_BGR2RGB)

def test_present_classification():
    assert present_img_rgb is not None
    assert classify_attendance(present_img_rgb) == 'Present'

def test_absent_classification():
    assert absent_img_rgb is not None
    assert classify_attendance(absent_img_rgb) == 'Absent'

