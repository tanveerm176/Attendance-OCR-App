import os
from dataclasses import dataclass

DPI = int(os.getenv("DPI", 300))
BUCKET_NAME = os.getenv("S3_BUCKET", None)   # None = local mode
OUTPUT_DIR  = os.getenv("OUTPUT_DIR", "./output")

@dataclass
class PipelineConfig:
    roster: list[str]

    # Used for initial image cropping from column 0 to column 5
    # Results in table columns: Number, Name, Grade, Well Check, Sign In
    img_crop_start: int = 0
    img_crop_end: int = 5

    # Skip Header if scanned pdf is 1st page of sign in sheet
    skip_header_start_row = 2

    # For pages other than 1st page
    default_start_row = 0

    # Used to isolate Name column for OCR pass
    name_col_start: int = 1
    name_col_end: int = 2

    # Used to isolate Sign In column for attendance status classification
    attendance_col_start: int = 3
    attendance_col_end: int = 5

    # Config for tesseract OCR to treat input as single line of text
    tesseract_config: str = "--oem 1 --psm 7"

    fuzzy_match_threshold: int = 80
    low_match_floor: int = 30