from __future__ import annotations

from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from smartseat_db import (
    create_exam,
    get_conn,
    import_classrooms_and_seats,
    import_students,
    init_db,
)


def main() -> None:
    base = BASE
    db_path = base / "smartseat.db"
    students_csv = base / "mock_students_80.csv"
    map_json = base / "mock_classroom_maps.json"

    conn = get_conn(db_path)
    init_db(conn)

    n_students = import_students(conn, students_csv)
    n_rooms, n_seats = import_classrooms_and_seats(conn, map_json)

    exam_id = create_exam(
        conn=conn,
        course_name="資訊系統專案管理期中考",
        exam_date="2026-05-20 09:10:00",
        classroom_id=2,
    )

    print(f"DB initialized at: {db_path}")
    print(f"Imported students: {n_students}")
    print(f"Imported classrooms: {n_rooms}, seats: {n_seats}")
    print(f"Created exam_id: {exam_id} (classroom_id=2)")


if __name__ == "__main__":
    main()
