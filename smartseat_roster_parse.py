from __future__ import annotations

import csv
import io

from smartseat_db import normalize_students_payload
from smartseat_seatmap_style import normalize_group_labels_to_int, normalize_group_value

# Column order is fixed: Group Number, Student ID, Major/Grade, Name
# The first row is always treated as a header and skipped regardless of its content.

# Keys used in column_mapping dicts
FIELD_GROUP = "group_name"
FIELD_STUDENT_ID = "student_id"
FIELD_DEPT = "department_grade"
FIELD_NAME = "student_name"
# student_name may also be supplied as two columns: first_name + last_name
FIELD_LAST_NAME = "last_name"
FIELD_FIRST_NAME = "first_name"
REQUIRED_FIELDS = (FIELD_GROUP, FIELD_STUDENT_ID, FIELD_NAME)


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


def extract_csv_headers(text: str) -> list[str]:
    """Return the header row of a CSV as a list of column name strings."""
    rows = _parse_rows(text)
    if not rows:
        return []
    return [cell.strip() for cell in rows[0]]


def extract_csv_rows(text: str) -> list[dict]:
    """Return all data rows as dicts keyed by header name, for the pre-parse exclusion UI."""
    rows = _parse_rows(text)
    if len(rows) < 2:
        return []
    headers = [cell.strip() for cell in rows[0]]
    result = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        result.append({headers[i]: row[i].strip() if i < len(row) else "" for i in range(len(headers))})
    return result


def parse_roster_with_mapping(
    text: str,
    column_mapping: dict,
    excluded_ids: set[str] | None = None,
) -> list[dict]:
    """Parse CSV text using a caller-supplied column mapping.

    column_mapping maps SmartSeat field names to the CSV header name(s):
        {
            "group_name":        "班級",
            "student_id":        "學號",
            "department_grade":  "系所年級",
            # Either a single name column:
            "student_name":      "姓名",
            # Or split into two columns (last_name + first_name):
            "last_name":         "姓",
            "first_name":        "名",
        }
    All four destination fields (group, student_id, dept, name) are required.
    Name may be supplied either as student_name OR as last_name + first_name.
    """
    # Validate: name must come from student_name OR (last_name + first_name)
    has_full_name = bool(column_mapping.get(FIELD_NAME))
    has_split_name = bool(column_mapping.get(FIELD_LAST_NAME)) and bool(column_mapping.get(FIELD_FIRST_NAME))
    if not has_full_name and not has_split_name:
        raise ValueError("欄位對應缺少姓名欄位：請選擇「姓名」或同時選擇「姓」與「名」")

    for field in (FIELD_GROUP, FIELD_STUDENT_ID):
        if not column_mapping.get(field):
            label = {"group_name": "組別", "student_id": "學號"}[field]
            raise ValueError(f"欄位對應缺少必填項目：{label}")

    rows = _parse_rows(text)
    if not rows:
        raise ValueError("名單內容為空，請貼上或上傳資料")

    header = [cell.strip() for cell in rows[0]]
    data_rows = rows[1:]

    # Build index map: SmartSeat field → column index in CSV
    col_index: dict[str, int] = {}
    for field, csv_col in column_mapping.items():
        if not csv_col:
            continue
        try:
            col_index[field] = header.index(csv_col)
        except ValueError:
            raise ValueError(f"CSV 中找不到欄位「{csv_col}」，請確認欄位名稱是否正確")

    def _get(cells: list[str], field: str, default: str = "") -> str:
        idx = col_index.get(field)
        if idx is None or idx >= len(cells):
            return default
        return cells[idx].strip()

    students: list[dict] = []
    for i, cells in enumerate(data_rows, start=2):
        if has_full_name:
            name = _get(cells, FIELD_NAME)
        else:
            last = _get(cells, FIELD_LAST_NAME)
            first = _get(cells, FIELD_FIRST_NAME)
            name = (last + first).strip()

        dept = _get(cells, FIELD_DEPT) or "-"
        record = {
            "group_name":       _get(cells, FIELD_GROUP),
            "student_id":       _get(cells, FIELD_STUDENT_ID),
            "department_grade": dept,
            "student_name":     name,
        }
        if not any(record.values()):
            continue
        for key, label in [("student_id", "學號"), ("student_name", "姓名")]:
            if not record[key]:
                raise ValueError(f"第 {i} 列「{label}」欄位為空")
        # 組別允許為空（例如旁聽生、助教未填組別），排除面板中會以「無組別」顯示
        raw_group = record["group_name"]
        record["group_name"] = normalize_group_value(raw_group) if raw_group else ""
        students.append(record)

    # Exclude before group-label normalisation so excluded groups don't
    # consume integer slots (e.g. "Group TA" must not become group "1").
    if excluded_ids:
        students = [s for s in students if s["student_id"] not in excluded_ids]

    students = normalize_group_labels_to_int(students)
    return normalize_students_payload(students)


ROSTER_TEMPLATE_CSV = "Group Number,Student ID,Major/Grade,Name\n1,114098000,資管一,王小明\n1,114098001,資管一,李佳蓉\n"
