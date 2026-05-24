from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from smartseat_allocator import assign_seats_serial_checkerboard
from smartseat_db import fetch_all_students, get_conn
from smartseat_student_shuffle import disperse_group_order


def fetch_exam_context(conn: sqlite3.Connection, exam_id: int) -> tuple[list[dict], list[dict]]:
    exam = conn.execute(
        "SELECT exam_id, classroom_id FROM exams WHERE exam_id = ?",
        (exam_id,),
    ).fetchone()
    if not exam:
        raise ValueError(f"找不到 exam_id={exam_id}")

    room_rows = conn.execute(
        """
        SELECT classroom_id
        FROM exam_classrooms
        WHERE exam_id = ?
        ORDER BY classroom_id
        """,
        (exam_id,),
    ).fetchall()
    room_ids = [r["classroom_id"] for r in room_rows] or [exam["classroom_id"]]
    placeholders = ",".join("?" for _ in room_ids)

    seats = [
        dict(r)
        for r in conn.execute(
            f"""
            SELECT seat_id, classroom_id, grid_x, grid_y, is_usable
            FROM seats
            WHERE classroom_id IN ({placeholders}) AND is_usable = 1
            ORDER BY classroom_id, grid_y, grid_x
            """,
            room_ids,
        ).fetchall()
    ]
    return fetch_all_students(conn), seats


def save_assignments(conn: sqlite3.Connection, exam_id: int, assignments: list[dict]) -> None:
    conn.execute("DELETE FROM seating_assignments WHERE exam_id = ?", (exam_id,))
    conn.executemany(
        """
        INSERT INTO seating_assignments(exam_id, student_id, seat_id, violation_flag)
        VALUES(?, ?, ?, ?)
        """,
        [(exam_id, a["student_id"], a["seat_id"], a["violation_flag"]) for a in assignments],
    )
    conn.commit()


def main() -> None:
    exam_id = 1
    if len(sys.argv) >= 2:
        exam_id = int(sys.argv[1])

    conn = get_conn(BASE / "smartseat.db")
    students, seats = fetch_exam_context(conn, exam_id)
    shuffled = disperse_group_order(students, seed=42)
    assignments, unassigned = assign_seats_serial_checkerboard(shuffled, seats)
    save_assignments(conn, exam_id, assignments)

    print(f"exam_id={exam_id}")
    print(f"assigned={len(assignments)} students")
    print(f"unassigned={len(unassigned)} students")


if __name__ == "__main__":
    main()
