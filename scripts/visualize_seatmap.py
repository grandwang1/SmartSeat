from __future__ import annotations

import html
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from smartseat_db import get_conn


def build_html(exam_id: int) -> str:
    conn = get_conn(BASE / "smartseat.db")
    exam = conn.execute(
        """
        SELECT e.exam_id, e.course_name, e.exam_date, c.classroom_id, c.room_name, c.max_rows, c.max_cols
        FROM exams e
        JOIN classrooms c ON c.classroom_id = e.classroom_id
        WHERE e.exam_id = ?
        """,
        (exam_id,),
    ).fetchone()
    if not exam:
        raise ValueError(f"找不到 exam_id={exam_id}")

    seat_rows = conn.execute(
        """
        SELECT
            se.seat_id, se.grid_x, se.grid_y, se.is_usable, se.block_note,
            s.student_id, s.student_name, s.department_grade,
            a.violation_flag
        FROM seats se
        LEFT JOIN seating_assignments a
            ON a.seat_id = se.seat_id AND a.exam_id = ?
        LEFT JOIN students s
            ON s.student_id = a.student_id
        WHERE se.classroom_id = ?
        ORDER BY se.grid_y, se.grid_x
        """,
        (exam_id, exam["classroom_id"]),
    ).fetchall()

    matrix = {}
    for r in seat_rows:
        matrix[(r["grid_x"], r["grid_y"])] = r

    cells = []
    for y in range(1, exam["max_rows"] + 1):
        row_cells = []
        for x in range(1, exam["max_cols"] + 1):
            s = matrix[(x, y)]
            cls = "usable"
            text = ""
            title = f"({x},{y})"
            if s["is_usable"] == 0:
                cls = "blocked"
                note = s["block_note"] or ""
                text = html.escape(note[:2] if note else "X")
                title += f" 不可用 {note}".strip()
            elif s["student_id"] is None:
                cls = "empty"
                text = "-"
                title += " 尚未安排"
            else:
                dep = s["department_grade"]
                name = s["student_name"]
                sid = s["student_id"]
                text = (
                    f'<div class="cell-id">{html.escape(sid)}</div>'
                    f'<div class="cell-name">{html.escape(name)}</div>'
                )
                title += f" {sid} {name} {dep}"
                cls = "assigned"
            row_cells.append(
                f'<td class="{cls}" title="{html.escape(title)}">{text}</td>'
            )
        cells.append("<tr>" + "".join(row_cells) + "</tr>")

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <title>SmartSeat Exam {exam_id}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; }}
    td {{ width: 88px; height: 52px; border: 1px solid #d5d5d5; text-align: center; font-size: 11px; padding: 2px; line-height: 1.15; }}
    .blocked {{ background: #3f3f46; color: #fff; }}
    .empty {{ background: #fafafa; color: #999; }}
    .assigned {{ background: #dbeafe; color: #1e3a8a; }}
    .violation {{ background: #fee2e2; color: #991b1b; }}
    .cell-name {{ font-weight: 600; white-space: nowrap; }}
    .cell-id {{ font-size: 10px; color: #374151; }}
  </style>
</head>
<body>
  <h2>SmartSeat 座位圖</h2>
  <p>考試: {html.escape(exam["course_name"])} | 時間: {html.escape(exam["exam_date"])} | 教室: {html.escape(exam["room_name"])}</p>
  <p>圖例: X=不可用, -=可用但未安排, 淺藍=已安排, 紅底=衝突座位</p>
  <table>{"".join(cells)}</table>
</body>
</html>"""


def main() -> None:
    exam_id = int(sys.argv[1]) if len(sys.argv) >= 2 else 1
    output = BASE / "outputs" / f"exam_{exam_id}_seatmap.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(exam_id), encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
