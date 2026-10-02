import pytest
import cv2
import numpy as np
from ocr_pipeline.ingestion import pdf_to_image
from ocr_pipeline.table_detection import (
    get_vertical_line_positions,
    get_horizontal_line_positions,
    split_student_rows_and_handwritten_region,
)
from pathlib import Path

SAMPLE_PDF = Path("tests/sample_data/sonyc-test.pdf")

### pytest.fixture, for image loading and dependency injection
# @pytest.fixture
# def sample_image():
#     img_rgb = pdf_to_image(SAMPLE_PDF)
#     img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
#     return img_gray

"""TEST get_vertical_line_positions()"""
def test_vertical_returns_list(sample_image):
    img_gray = sample_image
    result = get_vertical_line_positions(img_gray)
    assert isinstance(result, list)

def test_vertical_list_returns_correct_count(sample_image):
    img_gray = sample_image
    result = get_vertical_line_positions(img_gray)
    assert len(result) == 9

def test_vertical_positions_are_sorted(sample_image):
    img_gray = sample_image
    result = get_vertical_line_positions(img_gray)
    assert result == sorted(result)

def test_vertical_positions_within_image_bounds(sample_image):
    img_gray = sample_image
    result = get_vertical_line_positions(img_gray)
    width = img_gray.shape[1]
    assert all(0 <= x < width for x in result)

"""TEST get_horizontal_line_positions()"""
def test_horizontal_returns_list(sample_image):
    img_gray = sample_image
    result = get_horizontal_line_positions(img_gray)
    assert isinstance(result, list)

def test_horizontal_list_returns_correct_count(sample_image):
    img_gray = sample_image
    result = get_horizontal_line_positions(img_gray)
    assert len(result) > 10

def test_horizontal_positions_are_sorted(sample_image):
    img_gray = sample_image
    result = get_horizontal_line_positions(img_gray)
    assert result == sorted(result)

def test_horizontal_positions_within_image_bounds(sample_image):
    img_gray = sample_image
    result = get_horizontal_line_positions(img_gray)
    height = img_gray.shape[0]
    assert all(0 <= y < height for y in result)


def test_split_student_rows_uses_terminal_large_gap_for_handwriting():
    horizontal_lines = [2000, 2073, 2146, 2366, 2386]

    rows, handwritten_region = split_student_rows_and_handwritten_region(
        horizontal_lines, image_height=2550
    )

    assert rows == [(2000, 2073), (2073, 2146)]
    assert handwritten_region == (2146, 2365)


def test_split_student_rows_caps_handwriting_region_in_very_large_gap():
    horizontal_lines = [2000, 2073, 2146, 2700]

    rows, handwritten_region = split_student_rows_and_handwritten_region(
        horizontal_lines, image_height=2800
    )

    assert rows == [(2000, 2073), (2073, 2146)]
    assert handwritten_region == (2146, 2365)


def test_split_student_rows_bounds_handwriting_below_table():
    horizontal_lines = [2000, 2073, 2146]

    rows, handwritten_region = split_student_rows_and_handwritten_region(
        horizontal_lines, image_height=2250
    )

    assert rows == [(2000, 2073), (2073, 2146)]
    assert handwritten_region == (2146, 2250)
