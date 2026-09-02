from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class AttendanceRecord:
    ocr_name: str
    cleaned_name: str
    matched_name: Optional[str]
    match_score: float
    # Should we account for classification error == EMPTY_CELL?
    status: Literal["Present", "Absent"] 
    flag: str