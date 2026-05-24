from __future__ import annotations

import csv
import io
import re

from smartseat_db import normalize_students_payload
from smartseat_seatmap_style import normalize_group_value

HEADER_ALIASES = {
    "group_name": {"組別", "group", "group_name", "group id", "groupid"},
    "student_id": {"學號", "student_id", "student id", "id", "帳號", "學生學號"},
    "student_name": {"姓名", "student_name", "name", "學生姓名"},
    "department_grade": {"系級", "department_grade", "department", "grade", "科系", "系所"},
}

# Default column order without header: 組別, 學號, 系級, 姓名
DEFAULT_COLUMN_ORDER = ("group_name", "student_id", "department_grade", "student_name")


def _norm_header(cell: str) -> str:
    return re.sub(r"\s+", "", cell.strip().lower())


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


def _map_headers(header_cells: list[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(header_cells):
        key = _norm_header(raw)
        for field, aliases in HEADER_ALIASES.items():
            if key in {_norm_header(a) for a in aliases}:
                mapping[field] = idx
    required = {"group_name", "student_id", "student_name"}
    if required.issubset(mapping.keys()):
        return mapping
    return None


def _record_from_cells(cells: list[str], header_map: dict[str, int] | None, row_no: int) -> dict:
    if header_map:

        def get(field: str, required: bool = False) -> str:
            if field not in header_map:
                return ""
            idx = header_map[field]
            if idx >= len(cells):
                if required:
                    raise ValueError(f"第 {row_no} 列缺少欄位")
                return ""
            return cells[idx].strip()

        return {
            "group_name": get("group_name", True),
            "student_id": get("student_id", True),
            "department_grade": get("department_grade"),
            "student_name": get("student_name", True),
        }

    if len(cells) < 3:
        raise ValueError(f"第 {row_no} 列欄位不足（至少需要：組別, 學號, 姓名）")
    # 組別, 學號, 系級, 姓名（系級可省略）
    if len(cells) >= 4:
        return {
            "group_name": cells[0].strip(),
            "student_id": cells[1].strip(),
            "department_grade": cells[2].strip(),
            "student_name": cells[3].strip(),
        }
    return {
        "group_name": cells[0].strip(),
        "student_id": cells[1].strip(),
        "department_grade": "",
        "student_name": cells[2].strip(),
    }


def parse_roster_text(text: str) -> list[dict]:
    rows = _parse_rows(text)
    if not rows:
        raise ValueError("名單內容為空，請貼上或上傳資料")

    header_map = _map_headers(rows[0])
    data_rows = rows[1:] if header_map else rows

    students: list[dict] = []
    for i, cells in enumerate(data_rows, start=1):
        row_no = i + (1 if header_map else 0)
        record = _record_from_cells(cells, header_map, row_no)
        if not any(record.values()):
            continue
        record["group_name"] = normalize_group_value(record["group_name"])
        students.append(record)

    return normalize_students_payload(students)


ROSTER_TEMPLATE_CSV = "組別,學號,系級,姓名\n1,114098000,資管一,王小明\n1,114098001,資管一,李佳蓉\n"
