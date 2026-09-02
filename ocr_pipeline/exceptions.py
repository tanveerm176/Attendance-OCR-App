"""Custom exceptions for pipeline failures.

These exceptions are intentionally small and specific. The idea is to fail
with a clear message at the correct layer instead of letting generic Python
errors bubble up from deep inside the OCR logic.
"""


class OCRPipelineError(Exception):
    """Base class for all attendance OCR pipeline failures."""


class TableDetectionError(OCRPipelineError):
    """Raised when the page grid cannot be detected reliably."""


class OCRExtractionError(OCRPipelineError):
    """Raised when a cell OCR result is empty or unusable."""


class NoMatchFoundError(OCRPipelineError):
    """Raised when no roster name is close enough to a detected OCR name."""
