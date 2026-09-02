import pytest

from ocr_pipeline.exceptions import (
    OCRPipelineError,
    TableDetectionError,
    OCRExtractionError,
    NoMatchFoundError,
)


def test_exception_hierarchy():
    assert issubclass(TableDetectionError, OCRPipelineError)
    assert issubclass(OCRExtractionError, OCRPipelineError)
    assert issubclass(NoMatchFoundError, OCRPipelineError)


def test_exceptions_can_be_raised():
    with pytest.raises(TableDetectionError):
        raise TableDetectionError("No table grid found")

    with pytest.raises(OCRExtractionError):
        raise OCRExtractionError("OCR returned empty text")

    with pytest.raises(NoMatchFoundError):
        raise NoMatchFoundError("No roster match above threshold")
