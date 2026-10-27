from dataclasses import dataclass, field
from typing import Literal, Optional
from datetime import datetime
from pathlib import Path
import numpy as np


@dataclass(frozen=True)
class ImageBox:
    x0: int
    y0: int
    x1: int
    y1: int


@dataclass
class AttendanceRecord:
    page_index: int
    name_box: ImageBox
    ocr_name: str
    cleaned_name: str
    matched_name: str | None
    match_score: float
    match_flag: str
    attendance_status: Literal["Present", "Absent", "EMPTY CELL"]


@dataclass
class AttendancePage:
    page_index: int
    name_table_image: np.ndarray
    attendance_table_image: np.ndarray
    skew_angle: float


@dataclass
class DailyAttendance:
    source_pdf: Path
    sheet_date: datetime | None = None
    pages: list[AttendancePage] = field(default_factory=list)
    attendance_records: list[AttendanceRecord] = field(default_factory=list)