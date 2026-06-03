from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

DB_PATH = Path("smartseat.db")
SCHEMA_PATH = Path("schema.sql")


def get_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def migrate_db(conn: sqlite3.Connection) -> None:
    student_cols = _table_columns(conn, "students")
    if "group_name" not in student_cols:
        conn.execute(
            "ALTER TABLE students ADD COLUMN group_name TEXT NOT NULL DEFAULT ''"
        )

    seat_cols = _table_columns(conn, "seats")
    if "block_note" not in seat_cols:
        conn.execute("ALTER TABLE seats ADD COLUMN block_note TEXT")

    exam_cols = _table_columns(conn, "exams")
    if "col_reverse" not in exam_cols:
        conn.execute(
            "ALTER TABLE exams ADD COLUMN col_reverse INTEGER NOT NULL DEFAULT 0"
        )
    conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    migrate_db(conn)
    conn.commit()


def import_students(conn: sqlite3.Connection, students_csv: Path) -> int:
    with students_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            group = (
                r.get("group_name")
                or r.get("group")
                or r.get("組別")
                or ""
            ).strip()
            name = (r.get("name") or r.get("student_name") or r.get("姓名") or "").strip()
            dept = (r.get("department_grade") or r.get("系級") or "").strip()
            rows.append(
                (
                    r["student_id"].strip(),
                    name,
                    dept,
                    group,
                )
            )
    conn.executemany(
        """
        INSERT INTO students(student_id, student_name, department_grade, group_name)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(student_id) DO UPDATE SET
            student_name = excluded.student_name,
            department_grade = excluded.department_grade,
            group_name = excluded.group_name
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def import_classrooms_and_seats(conn: sqlite3.Connection, map_json: Path) -> tuple[int, int]:
    data = json.loads(map_json.read_text(encoding="utf-8"))
    classroom_rows = []
    seat_rows = []
    seat_id = 1
    for c in data["classrooms"]:
        classroom_rows.append((c["classroom_id"], c["room_name"], c["max_rows"], c["max_cols"]))
        for y, line in enumerate(c["seat_map"], start=1):
            for x, ch in enumerate(line, start=1):
                seat_rows.append(
                    (seat_id, c["classroom_id"], x, y, 1 if ch == "O" else 0, None)
                )
                seat_id += 1

    conn.executemany(
        """
        INSERT OR REPLACE INTO classrooms(classroom_id, room_name, max_rows, max_cols)
        VALUES(?, ?, ?, ?)
        """,
        classroom_rows,
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO seats(seat_id, classroom_id, grid_x, grid_y, is_usable, block_note)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        seat_rows,
    )
    conn.commit()
    return len(classroom_rows), len(seat_rows)


def create_classroom_from_layout(
    conn: sqlite3.Connection,
    room_name: str,
    rows: int,
    cols: int,
    blocked_cells: list[dict] | None = None,
) -> tuple[int, list[dict]]:
    """Create a classroom and all seat cells. blocked_cells use 1-based grid_x/grid_y."""
    blocked_map = {
        (int(b["x"]), int(b["y"])): (b.get("note") or "").strip()
        for b in (blocked_cells or [])
    }

    next_room = conn.execute(
        "SELECT COALESCE(MAX(classroom_id), 0) + 1 AS nid FROM classrooms"
    ).fetchone()["nid"]
    next_seat = conn.execute(
        "SELECT COALESCE(MAX(seat_id), 0) + 1 AS nid FROM seats"
    ).fetchone()["nid"]

    conn.execute(
        """
        INSERT INTO classrooms(classroom_id, room_name, max_rows, max_cols)
        VALUES(?, ?, ?, ?)
        """,
        (next_room, room_name, rows, cols),
    )

    seat_rows = []
    seat_id = next_seat
    all_seats: list[dict] = []
    for y in range(1, rows + 1):
        for x in range(1, cols + 1):
            note = blocked_map.get((x, y))
            is_usable = 0 if note is not None else 1
            seat_rows.append((seat_id, next_room, x, y, is_usable, note))
            all_seats.append(
                {
                    "seat_id": seat_id,
                    "classroom_id": next_room,
                    "grid_x": x,
                    "grid_y": y,
                    "is_usable": is_usable,
                    "block_note": note,
                }
            )
            seat_id += 1

    conn.executemany(
        """
        INSERT INTO seats(seat_id, classroom_id, grid_x, grid_y, is_usable, block_note)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        seat_rows,
    )
    conn.commit()
    return next_room, all_seats


def create_exam(
    conn: sqlite3.Connection,
    course_name: str,
    exam_date: str,
    classroom_id: int,
    classroom_ids: list[int] | None = None,
    col_reverse: bool = False,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO exams(course_name, exam_date, classroom_id, col_reverse)
        VALUES(?, ?, ?, ?)
        """,
        (course_name, exam_date, classroom_id, 1 if col_reverse else 0),
    )
    exam_id = cur.lastrowid
    cted_rooms = classroom_ids[:] if classroom_ids else [classroom_id]
    cted_rooms = sorted(set(int(cid) for cid in cted_rooms))
    conn.executemany(
        """
        INSERT INTO exam_classrooms(exam_id, classroom_id)
        VALUES(?, ?)
        ON CONFLICT(exam_id, classroom_id) DO NOTHING
        """,
        [(exam_id, cid) for cid in cted_rooms],
    )
    conn.commit()
    return exam_id


def fetch_all_students(conn: sqlite3.Connection) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT student_id, student_name, department_grade, group_name
            FROM students
            ORDER BY student_id
            """
        ).fetchall()
    ]


def normalize_students_payload(raw_students: list) -> list[dict]:
    """Validate roster from frontend. group_name, student_id, student_name are required."""
    if not raw_students:
        raise ValueError("請至少輸入一名學生")

    result: list[dict] = []
    seen_ids: set[str] = set()
    for i, row in enumerate(raw_students):
        if not isinstance(row, dict):
            raise ValueError(f"第 {i + 1} 列資料格式錯誤")
        group = (row.get("group_name") or row.get("group") or row.get("組別") or "").strip()
        sid = (row.get("student_id") or row.get("學號") or "").strip()
        name = (
            row.get("student_name") or row.get("name") or row.get("姓名") or ""
        ).strip()
        dept = (row.get("department_grade") or row.get("系級") or "").strip()

        if not group or not sid or not name:
            raise ValueError(f"第 {i + 1} 列：組別、學號、姓名為必填")
        if len(sid) < 4:
            raise ValueError(f"第 {i + 1} 列：學號格式不正確（{sid}）")
        if sid == group:
            raise ValueError(f"第 {i + 1} 列：學號不可與組別相同")
        if sid in seen_ids:
            raise ValueError(f"學號重複：{sid}")
        seen_ids.add(sid)
        from smartseat_seatmap_style import normalize_group_value

        result.append(
            {
                "student_id": sid,
                "student_name": name,
                "department_grade": dept if dept else "-",
                "group_name": normalize_group_value(group),
            }
        )
    return result


def upsert_students_list(conn: sqlite3.Connection, students: list[dict]) -> int:
    conn.executemany(
        """
        INSERT INTO students(student_id, student_name, department_grade, group_name)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(student_id) DO UPDATE SET
            student_name = excluded.student_name,
            department_grade = excluded.department_grade,
            group_name = excluded.group_name
        """,
        [
            (s["student_id"], s["student_name"], s["department_grade"], s["group_name"])
            for s in students
        ],
    )
    conn.commit()
    return len(students)
