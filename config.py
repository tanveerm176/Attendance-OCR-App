import os
from dataclasses import dataclass

DPI = int(os.getenv("DPI", 300))
BUCKET_NAME = os.getenv("S3_BUCKET", None)   # None = local mode
OUTPUT_DIR  = os.getenv("OUTPUT_DIR", "./output")

@dataclass
class PipelineConfig:
    roster: list[str]

    name_col_index_start: int = 1
    name_col_index_end: int = 2

    attendance_col_index_start: int = 3
    attendance_col_index_end: int = 5

    fuzzy_match_threshold: int = 80
    tesseract_config: str = "--oem 1 --psm 7"
    

