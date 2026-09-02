import re
from pathlib import Path

ROSTER_PATH = Path("data/student_roster.txt")

def build_roster() -> list[str]:
    student_roster: list[str] = []

    with open(ROSTER_PATH, 'r', encoding='utf-8') as file:
        for line in file:
            # remove all commas & newline chars
            cleaned_name = re.sub(r'[\n\r,]', '', line)
            student_roster.append(cleaned_name.strip())

    print(student_roster)
    return student_roster