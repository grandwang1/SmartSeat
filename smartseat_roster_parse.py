from __future__ import annotations

import csv
import io

from smartseat_db import normalize_students_payload
from smartseat_seatmap_style import normalize_group_value

# Column order is fixed: Group Number, Student ID, Major/Grade, Name
# The first row is always treated as a header and skipped regardless of its content.


def _detect_delimiter(line: str) -> str:
    if "\t" in line and line.count("\t") >= line.count(","):
        return "\t"
    return ","


def _parse_rows(text: str) -> list[list[str]]:
    text = text.strip()
    if not text:
        return []
    first_line = text.splitlines()[0]
    delim = _detect_delimiter(first_line)
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    return [list(row) for row in reader if any(cell.strip() for cell in row)]


def _record_from_cells(cells: list[str], row_no: int) -> dict:
    if len(cells) < 3:
        raise ValueError(f"第 {row_no} 列欄位不足（至少需要：組別, 學號, 姓名）")
    return {
        "group_name": cells[0].strip(),
        "student_id": cells[1].strip(),
        "department_grade": cells[2].strip() if len(cells) >= 4 else "",
        "student_name": cells[3].strip() if len(cells) >= 4 else cells[2].strip(),
    }


def parse_roster_text(text: str) -> list[dict]:
    rows = _parse_rows(text)
    if not rows:
        raise ValueError("名單內容為空，請貼上或上傳資料")

    # Always skip the first row as header
    data_rows = rows[1:]

    students: list[dict] = []
    for i, cells in enumerate(data_rows, start=2):
        record = _record_from_cells(cells, row_no=i)
        if not any(record.values()):
            continue
        record["group_name"] = normalize_group_value(record["group_name"])
        students.append(record)

    return normalize_students_payload(students)


ROSTER_TEMPLATE_CSV = "Group Number,Student ID,Major/Grade,Name\n1,114098000,資管一,王小明\n1,114098001,資管一,李佳蓉\n"
