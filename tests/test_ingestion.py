import fitz
import numpy as np
import pytest
from pathlib import Path
from ocr_pipeline.ingestion import pdf_to_image


def test_load_pdf_returns_rgb_numpy_arrays_for_each_page(tmp_path):
    pdf_path = tmp_path / "one-page.pdf"
    document = fitz.open()
    page = document.new_page(width=72, height=72)
    page.draw_rect(fitz.Rect(10, 10, 62, 62), color=(0, 0, 0), width=1)
    document.save(pdf_path)
    document.close()

    images = pdf_to_image(pdf_path)

    assert isinstance(images, list)
    assert len(images) == 1
    assert all(isinstance(image, np.ndarray) for image in images)
    assert all(image.ndim == 3 and image.shape[2] == 3 for image in images)
    assert all(image.dtype == np.uint8 for image in images)
    assert all(image.shape[0] > 0 and image.shape[1] > 0 for image in images)


def test_load_pdf_invalid_path_raises():
    with pytest.raises(Exception):
        pdf_to_image(Path(__file__).parent / "nonexistent.pdf")
