from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np
from ocr_pipeline.constants import REVIEW_FLAGS

@dataclass
class AttendanceRecord:
    page_index: int
    ocr_name: str
    cleaned_name: str
    matched_name: str | None
    match_score: float
    match_flag: str
    attendance_status: Literal["Present", "Absent", "EMPTY CELL"] 
    is_handwritten: bool = False
    reviewed: bool = False
    # Review crops only populated for records that need manual review; crops are cleared afterwards
    review_crop: np.ndarray | None = field(default=None, repr=False, compare=False)

    @property
    def needs_review(self) -> bool:
        return self.match_flag in REVIEW_FLAGS and not self.reviewed

@dataclass
class DailyAttendance:
    source_pdf: Path
    sheet_date: datetime | None = None
    # Path written to Excel hyperlinks (e.g. a host path when running Docker)
    source_pdf_display_path: str | None = None
    records: list[AttendanceRecord] = field(default_factory=list)
