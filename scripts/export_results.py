from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from smartseat_db import get_conn
from smartseat_seatmap_style import (
    BLANK_NOTE,
    _bounds_with_students,
    block_inline_style,
    block_note_class,
    block_note_label,
    build_seatmap_table_html,
    column_indices,
    compute_seat_labels,
    has_valid_student,
    is_blank_block,
    seatmap_excel_css,
)


def _fetch_seatmap_data(conn, exam_id: int) -> tuple[dict, dict, list[dict]]:
    exam = conn.execute(
        """
        SELECT e.exam_id, e.course_name, e.classroom_id,
               COALESCE(e.col_reverse, 0) AS col_reverse
        FROM exams e WHERE e.exam_id = ?
        """,
        (exam_id,),
    ).fetchone()
    if not exam:
        raise ValueError(f"找不到 exam_id={exam_id}")

    room_id = exam["classroom_id"]
    ec = conn.execute(
        "SELECT classroom_id FROM exam_classrooms WHERE exam_id = ? ORDER BY classroom_id LIMIT 1",
        (exam_id,),
    ).fetchone()
    if ec:
        room_id = ec["classroom_id"]

    room = conn.execute(
        """
        SELECT classroom_id, room_name, max_rows, max_cols
        FROM classrooms WHERE classroom_id = ?
        """,
        (room_id,),
    ).fetchone()

    seat_rows = conn.execute(
        """
        SELECT
            se.grid_x, se.grid_y, se.is_usable, se.block_note,
            s.student_id, s.student_name
        FROM seats se
        LEFT JOIN seating_assignments a
            ON a.seat_id = se.seat_id AND a.exam_id = ?
        LEFT JOIN students s ON s.student_id = a.student_id
        WHERE se.classroom_id = ?
        ORDER BY se.grid_y, se.grid_x
        """,
        (exam_id, room_id),
    ).fetchall()
    return dict(exam), dict(room), [dict(r) for r in seat_rows]


def _excel_cell_html(seat: dict) -> str:
    center = "text-align:center;vertical-align:middle;"
    if seat.get("is_usable") == 0:
        if is_blank_block(seat.get("block_note")):
            return (
                f'<td style="{center}background:#fee2e2;color:#dc2626;'
                f'font-weight:700;font-size:14px">✕</td>'
            )
        note = seat.get("block_note") or ""
        cls = block_note_class(note)
        label = block_note_label(note)
        style = block_inline_style(note)
        return f'<td class="{cls}" style="{center}{style}">{label}</td>'
    if not has_valid_student(seat):
        return f'<td style="{center}background:#f9fafb"></td>'
    sid = seat["student_id"].strip().replace("&", "&amp;").replace("<", "&lt;")
    name = seat["student_name"].strip().replace("&", "&amp;").replace("<", "&lt;")
    return (
        f'<td style="{center}background:#dbeafe;padding:6px 10px;white-space:nowrap">'
        f'<div style="font-size:11px;font-weight:600;white-space:nowrap">{sid}</div>'
        f'<div style="font-size:11px;font-weight:600;white-space:nowrap">{name}</div></td>'
    )


def build_colored_excel_html(
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
    row_label, col_label = compute_seat_labels(
        matrix, room["max_rows"], room["max_cols"], col_reverse
    )
    show_rows, show_cols = _bounds_with_students(
        matrix, room["max_rows"], room["max_cols"]
    )
    cols = list(range(1, show_cols + 1))

    # 計算不可用格的合併範圍（橫向優先，再縱向擴展成矩形）
    # 「不坐人（空白）」不參與合併，只合併黑板、門等具名原因
    def _get_block_note(x, y):
        seat = matrix.get((x, y))
        if seat and seat.get("is_usable") == 0:
            note = seat.get("block_note") or ""
            if is_blank_block(note):
                return None  # 不坐人不合併
            return note
        return None

    merged_cells = {}  # (x,y) -> {colspan, rowspan, note} 或 None（被合併掉）
    skip = set()
    for y in range(1, show_rows + 1):
        for x in range(1, show_cols + 1):
            if (x, y) in skip:
                continue
            note = _get_block_note(x, y)
            if note is None:
                continue
            # 橫向延伸
            cx = x + 1
            while cx <= show_cols and _get_block_note(cx, y) == note and (cx, y) not in skip:
                cx += 1
            colspan = cx - x
            # 縱向延伸
            cy = y + 1
            while cy <= show_rows:
                if all(
                    _get_block_note(x + dx, cy) == note and (x + dx, cy) not in skip
                    for dx in range(colspan)
                ):
                    cy += 1
                else:
                    break
            rowspan = cy - y
            # 標記被合併格
            for dy in range(rowspan):
                for dx in range(colspan):
                    if dx == 0 and dy == 0:
                        continue
                    skip.add((x + dx, y + dy))
                    merged_cells[(x + dx, y + dy)] = None
            merged_cells[(x, y)] = {"colspan": colspan, "rowspan": rowspan, "note": note}

    rows_html = []
    header = "<tr><td style='background:#f3f4f6;text-align:center;font-weight:600'></td>"
    for x in cols:
        header += (
            "<td style='background:#f3f4f6;text-align:center;font-weight:600'>"
            f"{col_label.get(x, '')}</td>"
        )
    rows_html.append(header + "</tr>")

    for y in range(1, show_rows + 1):
        row = (
            "<tr><td style='background:#f3f4f6;text-align:center;font-weight:600'>"
            f"{row_label.get(y, '')}</td>"
        )
        for x in cols:
            merge = merged_cells.get((x, y), "NOT_BLOCKED")
            if merge is None:
                # 被合併掉的格，跳過
                continue
            if isinstance(merge, dict):
                # 合併格左上角：輸出含 colspan/rowspan 的 td
                note = merge["note"]
                cs = merge["colspan"]
                rs = merge["rowspan"]
                cs_attr = f' colspan="{cs}"' if cs > 1 else ""
                rs_attr = f' rowspan="{rs}"' if rs > 1 else ""
                center = "text-align:center;vertical-align:middle;"
                if is_blank_block(note):
                    row += (
                        f'<td{cs_attr}{rs_attr} style="{center}background:#fee2e2;'
                        f'color:#dc2626;font-weight:700;font-size:14px">✕</td>'
                    )
                else:
                    label = block_note_label(note)
                    style = block_inline_style(note)
                    row += f'<td{cs_attr}{rs_attr} style="{center}{style}">{label}</td>'
            else:
                row += _excel_cell_html(matrix[(x, y)])
        rows_html.append(row + "</tr>")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8" />
<style>{seatmap_excel_css()}</style></head>
<body>
<p>考試名稱：{exam["course_name"]}</p>
<p>考場名稱：{room["room_name"]}</p>
<table border="1" cellspacing="0" cellpadding="2">{"".join(rows_html)}</table>
</body></html>"""


def export_seatmap_colored(
    exam_id: int,
    output_path: Path,
    col_reverse_override: bool | None = None,
) -> None:
    content = build_colored_excel_html(
        exam_id, col_reverse_override=col_reverse_override
    ).encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)


def export_assignment_csv(
    exam_id: int,
    output_path: Path,
    col_reverse_override: bool | None = None,
) -> int:
    """Colored seatmap as Excel-compatible HTML (.xls)."""
    export_seatmap_colored(exam_id, output_path, col_reverse_override=col_reverse_override)
    conn = get_conn(BASE / "smartseat.db")
    return conn.execute(
        "SELECT COUNT(*) AS c FROM seating_assignments WHERE exam_id = ?",
        (exam_id,),
    ).fetchone()["c"]


def main() -> None:
    exam_id = int(sys.argv[1]) if len(sys.argv) >= 2 else 1
    output_path = BASE / "outputs" / f"exam_{exam_id}_seatmap.xls"
    export_seatmap_colored(exam_id, output_path)
    print(f"Exported colored seatmap to {output_path}")


if __name__ == "__main__":
    main()
