import numpy as np
import pytest
from ocr_pipeline.img_cropping import vertical_img_crop, horizontal_img_crop

@pytest.fixture
def sample_img():
    return np.zeros((100, 200, 3), dtype=np.uint8)

"""TEST vertical_img_crop()"""
def test_vertical_crop_returns_correct_width(sample_img):
    result = vertical_img_crop(sample_img, 50, 150)
    assert result.shape[1] == 100


def test_vertical_crop_preserves_height(sample_img):
    result = vertical_img_crop(sample_img, 50, 150)
    assert result.shape[0] == 100


def test_vertical_crop_invalid_bounds_raises(sample_img):
    with pytest.raises(ValueError):
        vertical_img_crop(sample_img, 150, 50)


def test_vertical_crop_out_of_bounds_raises(sample_img):
    with pytest.raises(ValueError):
        vertical_img_crop(sample_img, 0, 300)


"""TEST horizontal_img_crop()"""
def test_horizontal_crop_returns_correct_height(sample_img):
    result = horizontal_img_crop(sample_img, 25, 75)
    assert result.shape[0] == 50


def test_horizontal_crop_preserves_width(sample_img):
    result = horizontal_img_crop(sample_img, 25, 75)
    assert result.shape[1] == 200


def test_horizontal_crop_invalid_bounds_raises(sample_img):
    with pytest.raises(ValueError):
        horizontal_img_crop(sample_img, 75, 25)


def test_horizontal_crop_out_of_bounds_raises(sample_img):
    with pytest.raises(ValueError):
        horizontal_img_crop(sample_img, 0, 150)


