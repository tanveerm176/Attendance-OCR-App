import numpy as np
import pytest
from pathlib import Path
from ocr_pipeline.ocr import preprocess_for_ocr, tesseract_ocr
import cv2

# Pass in image of text, verify str matches 
# Pass in image of text, verify that output of preprocess is image (np.ndarray)

SAMPLE_NAME_SCAN = Path("tests/sample_scans/cell_student_name.png")

def test_img_to_str():
    img_array = cv2.imread(SAMPLE_NAME_SCAN)
    assert img_array is not None
    ocr_name = tesseract_ocr(img_array)
    assert isinstance(ocr_name, str)