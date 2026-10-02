import numpy as np
import pytest
from pathlib import Path
from ocr_pipeline.ocr import (
    preprocess_for_ocr,
    remove_red_strikethrough,
    tesseract_ocr,
)
import cv2

# Pass in image of text, verify str matches 
# Pass in image of text, verify that output of preprocess is image (np.ndarray)

SAMPLE_NAME_SCAN = Path("tests/sample_data/cell_student_name.png")

def test_img_to_str():
    img_array = cv2.imread(SAMPLE_NAME_SCAN)
    assert img_array is not None
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    
    ocr_name = tesseract_ocr(img_array)
    assert isinstance(ocr_name, str)


def test_remove_red_strikethrough_inpaints_red_pixels():
    image_rgb = np.full((40, 120, 3), 255, dtype=np.uint8)
    cv2.putText(image_rgb, "Name", (5, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.line(image_rgb, (0, 20), (119, 20), (255, 0, 0), 2)
    original = image_rgb.copy()

    cleaned = remove_red_strikethrough(image_rgb)

    assert cleaned.shape == image_rgb.shape
    np.testing.assert_array_equal(image_rgb, original)
    hsv = cv2.cvtColor(cleaned, cv2.COLOR_RGB2HSV)
    red_pixels = cv2.inRange(hsv, np.array([0, 45, 50]), np.array([10, 255, 255]))
    red_pixels |= cv2.inRange(
        hsv, np.array([170, 45, 50]), np.array([180, 255, 255])
    )
    assert cv2.countNonZero(red_pixels) == 0


def test_remove_red_strikethrough_leaves_non_red_image_unchanged():
    image_rgb = np.full((20, 40, 3), 255, dtype=np.uint8)
    cv2.putText(image_rgb, "A", (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    cleaned = remove_red_strikethrough(image_rgb)

    np.testing.assert_array_equal(cleaned, image_rgb)
