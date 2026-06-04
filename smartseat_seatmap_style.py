from __future__ import annotations

import html
import re

BLANK_NOTE = "空白"

BLOCK_STYLES: dict[str, dict[str, str]] = {
    "黑板": {"class": "block-board", "bg": "#e8e6df", "label": "黑板"},
    "門": {"class": "block-door", "bg": "#dfe6ee", "label": "門"},
    "柱子": {"class": "block-pillar", "bg": "#e8dfe6", "label": "柱子"},
}

ASSIGNED_BG = "#dbeafe"
EMPTY_BG = "#f9fafb"
LABEL_BG = "#f3f4f6"


def column_indices(max_cols: int, col_reverse: bool) -> list[int]:
    xs = list(range(1, max_cols + 1))
    return list(reversed(xs)) if col_reverse else xs


def compute_seat_labels(
    matrix: dict[tuple[int, int], dict],
    max_rows: int,
    max_cols: int,
    col_reverse: bool = False,
) -> tuple[dict[int, int], dict[int, int]]:
    """依「實際會坐學生的橫排與直排」重新編號。

    - 整橫排有黑板 → 跳過
    - 整橫排 / 整直排都是 block（門、柱子等）→ 跳過
    - col_reverse=True 時，直排編號由右往左
    """
    blackboard_rows: set[int] = set()
    for (x, y), seat in matrix.items():
        if (seat.get("block_note") or "").strip() == "黑板":
            blackboard_rows.add(y)

    def is_seatable(seat: dict | None) -> bool:
        if not seat:
            return False
        if seat.get("is_usable") != 1:
            return False
        if seat.get("grid_y") in blackboard_rows:
            return False
        return True

    usable_rows: list[int] = []
    for y in range(1, max_rows + 1):
        if any(is_seatable(matrix.get((x, y))) for x in range(1, max_cols + 1)):
            usable_rows.append(y)

    usable_cols: list[int] = []
    for x in range(1, max_cols + 1):
        if any(is_seatable(matrix.get((x, y))) for y in range(1, max_rows + 1)):
            usable_cols.append(x)

    row_label = {y: idx + 1 for idx, y in enumerate(usable_rows)}
    total = len(usable_cols)
    col_label = {
        x: (total - idx if col_reverse else idx + 1)
        for idx, x in enumerate(usable_cols)
    }
    return row_label, col_label


def is_blank_block(note: str | None) -> bool:
    return (note or "").strip() == BLANK_NOTE


def is_structural_block(note: str | None) -> bool:
    if not note:
        return False
    note = note.strip()
    if is_blank_block(note):
        return True
    if note in BLOCK_STYLES:
        return True
    return note.startswith("其他")


def block_note_class(note: str | None) -> str:
    if is_blank_block(note):
        return "empty"
    if not note:
        return "block-other"
    note = note.strip()
    if note in BLOCK_STYLES:
        return BLOCK_STYLES[note]["class"]
    if note.startswith("其他"):
        return "block-other"
    return "block-other"


def block_note_label(note: str | None) -> str:
    if is_blank_block(note):
        return ""
    if not note:
        return ""
    note = note.strip()
    if note in BLOCK_STYLES:
        return BLOCK_STYLES[note]["label"]
    if note.startswith("其他:"):
        return note[3:].strip() or "其他"
    if note.startswith("其他"):
        custom = note.replace("其他", "", 1).strip(": ").strip()
        return custom or "其他"
    return note


def block_inline_style(note: str | None) -> str:
    if is_blank_block(note):
        return f"background:{EMPTY_BG}"
    if not note:
        return f"background:{EMPTY_BG}"
    note = note.strip()
    if note in BLOCK_STYLES:
        return f"background:{BLOCK_STYLES[note]['bg']}"
    return "background:#e5e5e0"


def has_valid_student(seat: dict) -> bool:
    sid = (seat.get("student_id") or "").strip()
    name = (seat.get("student_name") or "").strip()
    if not sid or not name:
        return False
    if sid == name:
        return False
    if len(sid) < 4:
        return False
    return True


def split_name(full_name: str) -> tuple[str, str]:
    """Return (chinese_name, english_name). english_name is empty if not present."""
    name = full_name.strip()
    # "陳大文(David Chen)" or "陳大文 (David Chen)"
    m = re.match(r'^([一-鿿]+)\s*\(([^)]+)\)$', name)
    if m:
        return m.group(1), m.group(2).strip()
    # "陳大文 David Chen"
    m = re.match(r'^([一-鿿]{2,4})\s+([A-Za-z].+)$', name)
    if m:
        return m.group(1), m.group(2).strip()
    # "David Chen 陳大文"
    m = re.match(r'^([A-Za-z][A-Za-z\s]+)\s+([一-鿿]{2,4})$', name)
    if m:
        return m.group(2), m.group(1).strip()
    return name, ""


def render_seat_cell_html(seat: dict) -> str:
    center = "text-align:center;vertical-align:middle;"
    if seat.get("is_usable") == 0:
        if is_blank_block(seat.get("block_note")):
            return (
                f'<td class="block-blank" style="{center}background:#fee2e2;'
                f'color:#dc2626;font-weight:700;font-size:14px">✕</td>'
            )
        note = seat.get("block_note") or ""
        cls = block_note_class(note)
        label = html.escape(block_note_label(note))
        style = block_inline_style(note)
        return f'<td class="{cls}" style="{center}{style}">{label}</td>'
    if not has_valid_student(seat):
        return f'<td class="empty" style="{center}background:{EMPTY_BG}"></td>'
    sid = html.escape(seat["student_id"].strip())
    chinese_name, english_name = split_name(seat["student_name"].strip())
    en_div = f'<div class="cell-name-en">{html.escape(english_name)}</div>' if english_name else ""
    return (
        f'<td class="assigned" style="{center}background:{ASSIGNED_BG}">'
        f'<div class="cell-id">{sid}</div>'
        f'<div class="cell-name">{html.escape(chinese_name)}</div>'
        f'{en_div}</td>'
    )


def _compute_block_merges(
    matrix: dict[tuple[int, int], dict],
    show_rows: int,
    show_cols: int,
) -> dict[tuple[int, int], dict | None]:
    """Compute colspan/rowspan merges for named block cells (not blank/空白)."""

    def _block_note(x: int, y: int) -> str | None:
        seat = matrix.get((x, y))
        if not seat or seat.get("is_usable") != 0:
            return None
        note = (seat.get("block_note") or "").strip()
        if is_blank_block(note):
            return None  # 不坐人不合併
        return note or None

    merged: dict[tuple[int, int], dict | None] = {}
    skip: set[tuple[int, int]] = set()

    for y in range(1, show_rows + 1):
        for x in range(1, show_cols + 1):
            if (x, y) in skip:
                continue
            note = _block_note(x, y)
            if note is None:
                continue
            # 橫向延伸
            cx = x + 1
            while cx <= show_cols and _block_note(cx, y) == note and (cx, y) not in skip:
                cx += 1
            colspan = cx - x
            # 縱向延伸
            cy = y + 1
            while cy <= show_rows and all(
                _block_note(x + dx, cy) == note and (x + dx, cy) not in skip
                for dx in range(colspan)
            ):
                cy += 1
            rowspan = cy - y
            for dy in range(rowspan):
                for dx in range(colspan):
                    if dx == 0 and dy == 0:
                        continue
                    skip.add((x + dx, y + dy))
                    merged[(x + dx, y + dy)] = None
            merged[(x, y)] = {"colspan": colspan, "rowspan": rowspan, "note": note}

    return merged


def build_seatmap_table_html(
    matrix: dict[tuple[int, int], dict],
    max_rows: int,
    max_cols: int,
    col_reverse: bool = False,
) -> str:
    row_label, col_label = compute_seat_labels(
        matrix, max_rows, max_cols, col_reverse
    )
    show_rows, show_cols = _bounds_with_students(matrix, max_rows, max_cols)
    cols = list(range(1, show_cols + 1))
    merged = _compute_block_merges(matrix, show_rows, show_cols)

    parts: list[str] = ['<table class="seatmap-table">']

    header = ['<tr><th class="axis"></th>']
    for x in cols:
        header.append(f'<th class="axis">{col_label.get(x, "")}</th>')
    header.append("</tr>")
    parts.append("".join(header))

    for y in range(1, show_rows + 1):
        parts.append(f'<tr><th class="axis">{row_label.get(y, "")}</th>')
        for x in cols:
            merge = merged.get((x, y), "NOT_BLOCKED")
            if merge is None:
                # 被合併掉的格，跳過
                continue
            if isinstance(merge, dict):
                note = merge["note"]
                cs_attr = f' colspan="{merge["colspan"]}"' if merge["colspan"] > 1 else ""
                rs_attr = f' rowspan="{merge["rowspan"]}"' if merge["rowspan"] > 1 else ""
                center = "text-align:center;vertical-align:middle;"
                label = html.escape(block_note_label(note))
                style = block_inline_style(note)
                cls = block_note_class(note)
                parts.append(
                    f'<td{cs_attr}{rs_attr} class="{cls}" style="{center}{style}">{label}</td>'
                )
            else:
                parts.append(render_seat_cell_html(matrix[(x, y)]))
        parts.append("</tr>")

    parts.append("</table>")
    return "".join(parts)


def _bounds_with_students(
    matrix: dict[tuple[int, int], dict],
    max_rows: int,
    max_cols: int,
) -> tuple[int, int]:
    """回傳 (show_rows, show_cols)：剛好涵蓋所有已排學生的最小範圍。"""
    student_xs: list[int] = []
    student_ys: list[int] = []
    for (x, y), seat in matrix.items():
        if (seat.get("student_id") or "").strip():
            student_xs.append(x)
            student_ys.append(y)
    if not student_xs:
        return max_rows, max_cols
    return max(student_ys), max(student_xs)


def seatmap_print_css() -> str:
    block_rules = "\n".join(
        f"    td.{s['class']} {{ background: {s['bg']} !important; }}"
        for s in BLOCK_STYLES.values()
    )
    center = "text-align:center;vertical-align:middle;"
    return f"""
    * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #111; }}
    .meta {{ font-size: 15px; margin: 6px 0; }}
    table {{ border-collapse: collapse; margin-top: 12px; page-break-inside: avoid; }}
    td, th {{
      border: 1px solid #d1d5db; {center}
      font-size: 10px; padding: 4px 2px;
    }}
    th.axis {{ background: {LABEL_BG} !important; font-weight: 600; width: 32px; min-width: 32px; }}
    td {{ width: 110px; height: 110px; padding: 4px 6px; }}
    td.assigned {{ background: {ASSIGNED_BG} !important; }}
    td.empty {{ background: {EMPTY_BG} !important; color: #9ca3af; }}
    td.block-other {{ background: #e5e5e0 !important; }}
{block_rules}
    .cell-id {{ font-weight: 600; font-size: 11px; color: #374151; white-space: nowrap; }}
    .cell-name {{ font-weight: 600; font-size: 11px; white-space: nowrap; }}
    .cell-name-en {{ font-size: 9px; font-weight: 500; color: #6b7280; white-space: normal; word-break: break-word; }}
    .no-print {{ margin-bottom: 12px; }}
    @media print {{ .no-print {{ display: none; }} body {{ margin: 12px; }} }}
"""


def seatmap_excel_css() -> str:
    return seatmap_print_css()


def normalize_group_value(raw: str) -> str:
    g = raw.strip()
    if re.fullmatch(r"\d+", g):
        return g
    m = re.search(r"\d+", g)
    if m:
        return m.group()
    # Pure-text group label (e.g. "Group TA", "助教") — return as-is;
    # the caller is responsible for batch-normalizing all group labels to
    # consistent integer strings via normalize_group_labels_to_int().
    return g


_group_label_cache: dict[str, str] = {}


def normalize_group_labels_to_int(students: list[dict]) -> list[dict]:
    """Map arbitrary group label strings to stable integer strings.

    Labels that already look like integers are kept.  Pure-text labels
    (e.g. "Group TA", "助教") are assigned the next available integer in
    the order they are first encountered, so the mapping is deterministic
    within a single call.
    """
    label_map: dict[str, str] = {}
    next_int: list[int] = [1]

    def _assign(label: str) -> str:
        if label == "":        # 空組別保持空字串，不分配整數
            return ""
        if label in label_map:
            return label_map[label]
        if re.fullmatch(r"\d+", label):
            label_map[label] = label
            return label
        m = re.search(r"\d+", label)
        if m:
            label_map[label] = m.group()
            return m.group()
        # Pure text — assign the next available integer
        while str(next_int[0]) in label_map.values():
            next_int[0] += 1
        assigned = str(next_int[0])
        next_int[0] += 1
        label_map[label] = assigned
        return assigned

    result = []
    for s in students:
        s = dict(s)
        s["group_name"] = _assign(s.get("group_name", ""))
        result.append(s)
    return result
