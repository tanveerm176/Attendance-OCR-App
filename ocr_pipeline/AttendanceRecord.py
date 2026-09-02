from dataclasses import dataclass
from typing import Literal, Optional
from datetime import datetime
from pathlib import Path

@dataclass
class AttendanceRecord:
    date: datetime 
    ocr_name: str
    cleaned_name: str
    matched_name: Optional[str]
    match_score: float
    status: Literal["Present", "Absent", "EMPTY CELL"] 
    flag: str

@dataclass
class DailySheet:
    sheet_date: datetime
    source_pdf: Path
    records: list[AttendanceRecord]
