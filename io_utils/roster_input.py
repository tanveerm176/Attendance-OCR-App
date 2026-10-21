import re
from pathlib import Path

ROSTER_PATH = Path(__file__).resolve().parents[1] / "data" / "student_roster_26.txt"

def build_roster(roster_path: Path = ROSTER_PATH) -> list[str]:
    student_roster: list[str] = []

    with open(roster_path, 'r', encoding='utf-8') as file:
        for line in file:
            # remove all commas & newline chars
            cleaned_name = re.sub(r'[\n\r,]', '', line)
            student_roster.append(cleaned_name.strip())

    return student_roster