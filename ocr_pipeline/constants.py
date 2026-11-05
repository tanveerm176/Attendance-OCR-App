from ocr_pipeline.exceptions import NoMatchFoundError, OCRExtractionError

STRONG_MATCH_LABEL = "Strong Match"
LOW_MATCH_LABEL = "Low Match - Needs Review"
EMPTY_ROW_LABEL = "EMPTY CELL"
RESOLVED_MANUALLY_FLAG = "Resolved - Manual Review"
NEED_MANUAL_ENTRY_FLAG = "NEED-MANUAL-ENTRY"
WRITTEN_NAME_MARKER = "WRITTEN NAME DETECTED"

REVIEW_FLAGS = {
    OCRExtractionError.__name__,
    NoMatchFoundError.__name__,
    LOW_MATCH_LABEL,
    NEED_MANUAL_ENTRY_FLAG,
}
