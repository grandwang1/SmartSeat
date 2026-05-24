from __future__ import annotations

import html
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from scripts.export_results import _fetch_seatmap_data
from smartseat_db import get_conn
from smartseat_seatmap_style import build_seatmap_table_html, seatmap_print_css


def build_report_html(
    exam_id: int,
    db_path: Path | None = None,
    col_reverse_override: bool | None = None,
) -> str:
    conn = get_conn(db_path or BASE / "smartseat.db")
    exam, room, seat_rows = _fetch_seatmap_data(conn, exam_id)
    matrix = {(r["grid_x"], r["grid_y"]): r for r in seat_rows}
    col_reverse = (
        col_reverse_override
        if col_reverse_override is not None
        else bool(exam.get("col_reverse"))
    )
    table = build_seatmap_table_html(
        matrix, room["max_rows"], room["max_cols"], col_reverse=col_reverse
    )

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <title>{html.escape(exam["course_name"])} 座位表</title>
  <style>{seatmap_print_css()}</style>
</head>
<body>
  <div class="no-print">
    <button onclick="window.print()">列印／另存為 PDF</button>
  </div>
  <p class="meta">考試名稱：{html.escape(exam["course_name"])}</p>
  <p class="meta">考場名稱：{html.escape(room["room_name"])}</p>
  {table}
</body>
</html>"""
