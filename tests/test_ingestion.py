import numpy as np
import pytest
from pathlib import Path
from ocr_pipeline.ingestion import load_pdf

SAMPLE_PDF = Path("tests/sample_scans/sonyc-test.pdf")

"Test the PDF loaded is returned as a np array"
def test_load_pdf_returns_numpy_array():
    img = load_pdf(str(SAMPLE_PDF))
    assert isinstance(img, np.ndarray)

"Test the PDF loaded has 3 dimensiins (Height, Width, Color Channels)"
def test_load_pdf_correct_dimensions():
    img = load_pdf(str(SAMPLE_PDF))
    # RGB image must be 3 dimensional — height, width, channels
    assert img.ndim == 3

"Test the PDF loaded has 3 channels (RGB)"
def test_load_pdf_correct_channels():
    img = load_pdf(str(SAMPLE_PDF))
    # Must be 3 channel RGB
    assert img.shape[2] == 3

"Test the loaded PDF has the correct data type"
def test_load_pdf_correct_dtype():
    img = load_pdf(str(SAMPLE_PDF))
    assert img.dtype == np.uint8

"Test the PDF loaded has Height & Width > 0"
def test_load_pdf_nonzero_dimensions():
    img = load_pdf(str(SAMPLE_PDF))
    height, width, _ = img.shape
    assert height > 0 and width > 0

"Test that an Exception will be raised with an invalid PDF Path"
def test_load_pdf_invalid_path_raises():
    with pytest.raises(Exception):
        load_pdf("./nonexistent.pdf")