from __future__ import annotations

import argparse
import json
import mimetypes
import socket
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scripts.export_report import build_report_html
from scripts.export_results import export_assignment_csv
from smartseat_roster_parse import (
    ROSTER_TEMPLATE_CSV,
    extract_csv_headers,
    extract_csv_rows,
    parse_roster_text,
    parse_roster_with_mapping,
)
from scripts.run_assignment import save_assignments
from smartseat_allocator import assign_seats_serial_checkerboard
from smartseat_db import (
    create_classroom_from_layout,
    create_exam,
    fetch_all_students,
    get_conn,
    import_classrooms_and_seats,
    import_students,
    init_db,
    migrate_db,
    normalize_students_payload,
    upsert_students_list,
)
from smartseat_student_shuffle import disperse_group_order


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "app" / "static"
DB_PATH = ROOT / "smartseat.db"


def ensure_initialized() -> None:
    conn = get_conn(DB_PATH)
    init_db(conn)
    migrate_db(conn)
    import_students(conn, ROOT / "mock_students_120.csv")
    room_count = conn.execute("SELECT COUNT(*) AS c FROM classrooms").fetchone()["c"]
    if room_count == 0:
        import_classrooms_and_seats(conn, ROOT / "mock_classroom_maps.json")


def json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length > 0 else b"{}"
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


class SmartSeatHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_file(STATIC_DIR / "index.html")
            return
        if parsed.path.startswith("/static/"):
            rel = parsed.path.replace("/static/", "", 1)
            self._serve_file(STATIC_DIR / rel)
            return
        if parsed.path == "/api/students":
            self._get_students()
            return
        if parsed.path == "/api/students/template.csv":
            self._download_roster_template()
            return
        if parsed.path.startswith("/api/exam/") and parsed.path.endswith("/report"):
            self._download_report(parsed.path)
            return
        if parsed.path.startswith("/api/exam/") and parsed.path.endswith("/seatmap"):
            self._get_seatmap(parsed.path)
            return
        if parsed.path.startswith("/api/exam/") and parsed.path.endswith("/download"):
            self._download_csv(parsed.path)
            return
        json_response(self, {"error": "Not Found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/run-assignment":
            self._run_assignment()
            return
        if parsed.path == "/api/preview-shuffle":
            self._preview_shuffle()
            return
        if parsed.path == "/api/parse-roster":
            self._parse_roster()
            return
        if parsed.path == "/api/csv-headers":
            self._get_csv_headers()
            return
        if parsed.path == "/api/csv-preview":
            self._get_csv_preview()
            return
        json_response(self, {"error": "Not Found"}, status=404)

    def _serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        content = path.read_bytes()
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _get_students(self) -> None:
        conn = get_conn(DB_PATH)
        students = fetch_all_students(conn)
        shuffled = disperse_group_order(students, seed=42)
        json_response(
            self,
            {
                "students": students,
                "shuffled_students": shuffled,
            },
        )

    def _resolve_students(self, payload: dict) -> list[dict]:
        use_mock = payload.get("use_mock_students", False)
        excluded = set(payload.get("excluded_ids") or [])
        if use_mock:
            conn = get_conn(DB_PATH)
            students = fetch_all_students(conn)
            if excluded:
                students = [s for s in students if s["student_id"] not in excluded]
            return students
        roster_text = (payload.get("roster_text") or "").strip()
        column_mapping = payload.get("column_mapping")
        if roster_text:
            if column_mapping:
                # Pass excluded_ids into parser so group-label normalisation
                # runs only on the students that will actually be seated.
                return parse_roster_with_mapping(roster_text, column_mapping, excluded_ids=excluded)
            students = parse_roster_text(roster_text)
            if excluded:
                students = [s for s in students if s["student_id"] not in excluded]
            return students
        raw = payload.get("students", [])
        if raw:
            students = normalize_students_payload(raw)
            if excluded:
                students = [s for s in students if s["student_id"] not in excluded]
            return students
        raise ValueError("請貼上學生名單並按「解析名單」，或選擇使用 mock 名單")

    def _download_roster_template(self) -> None:
        content = ROSTER_TEMPLATE_CSV.encode("utf-8-sig")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header(
            "Content-Disposition",
            'attachment; filename="student_roster_template.csv"',
        )
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _get_csv_headers(self) -> None:
        try:
            payload = parse_json_body(self)
            roster_text = (payload.get("roster_text") or "").strip()
            if not roster_text:
                raise ValueError("請提供 CSV 內容")
            headers = extract_csv_headers(roster_text)
            json_response(self, {"headers": headers})
        except Exception as exc:
            json_response(self, {"error": str(exc)}, status=400)

    def _get_csv_preview(self) -> None:
        """Return raw CSV headers + all data rows (as dicts) for the pre-parse exclusion UI."""
        try:
            payload = parse_json_body(self)
            roster_text = (payload.get("roster_text") or "").strip()
            if not roster_text:
                raise ValueError("請提供 CSV 內容")
            headers = extract_csv_headers(roster_text)
            rows = extract_csv_rows(roster_text)
            json_response(self, {"headers": headers, "rows": rows})
        except Exception as exc:
            json_response(self, {"error": str(exc)}, status=400)

    def _parse_roster(self) -> None:
        try:
            payload = parse_json_body(self)
            roster_text = (payload.get("roster_text") or "").strip()
            column_mapping = payload.get("column_mapping")
            excluded = set(payload.get("excluded_ids") or [])
            if column_mapping:
                students = parse_roster_with_mapping(roster_text, column_mapping, excluded_ids=excluded)
            else:
                students = parse_roster_text(roster_text)
                if excluded:
                    students = [s for s in students if s["student_id"] not in excluded]
            json_response(
                self,
                {
                    "student_count": len(students),
                    "students": students,
                    "preview": students[:15],
                },
            )
        except Exception as exc:
            json_response(self, {"error": str(exc)}, status=400)

    def _preview_shuffle(self) -> None:
        try:
            payload = parse_json_body(self)
            students = self._resolve_students(payload)
            seed = int(payload.get("seed", 42))
            shuffled = disperse_group_order(students, seed=seed)
            json_response(
                self,
                {
                    "student_count": len(students),
                    "shuffled_students": shuffled,
                },
            )
        except Exception as exc:
            json_response(self, {"error": str(exc)}, status=400)

    def _run_assignment(self) -> None:
        try:
            payload = parse_json_body(self)
            rows = int(payload.get("rows", 0))
            cols = int(payload.get("cols", 0))
            if rows < 1 or cols < 1:
                raise ValueError("請先在 20×20 格線上框選教室範圍")

            room_name = payload.get("room_name", "自訂教室")
            course_name = payload.get("course_name", "SmartSeat DEMO")
            exam_date = payload.get("exam_date") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            blocked = list(payload.get("blocked", []))
            # Blackboard 規則：黑板格本身保留原樣，但該整排視為「不排人」。
            board_rows = {int(b["y"]) for b in blocked if (b.get("note") or "").strip() == "黑板"}
            seed = int(payload.get("seed", 42))

            conn = get_conn(DB_PATH)
            classroom_id, all_seats = create_classroom_from_layout(
                conn,
                room_name=room_name,
                rows=rows,
                cols=cols,
                blocked_cells=blocked,
            )
            usable_seats = [s for s in all_seats if s["is_usable"] == 1]
            if board_rows:
                # 黑板整橫排不可坐人，從可指派座位池中剃除
                usable_seats = [s for s in usable_seats if s["grid_y"] not in board_rows]

            students = self._resolve_students(payload)
            upsert_students_list(conn, students)
            shuffled = disperse_group_order(students, seed=seed)
            assignments, unassigned = assign_seats_serial_checkerboard(shuffled, usable_seats)

            col_reverse = bool(payload.get("col_reverse", False))
            exam_id = create_exam(
                conn,
                course_name=course_name,
                exam_date=exam_date,
                classroom_id=classroom_id,
                classroom_ids=[classroom_id],
                col_reverse=col_reverse,
            )
            save_assignments(conn, exam_id, assignments)

            assigned_ids = {a["student_id"] for a in assignments}
            json_response(
                self,
                {
                    "exam_id": exam_id,
                    "assigned_count": len(assignments),
                    "unassigned_count": len(unassigned),
                    "usable_seats": len(usable_seats),
                    "classroom_id": classroom_id,
                    "rows": rows,
                    "cols": cols,
                    "student_count": len(students),
                    "assigned_students": [
                        {
                            "student_id": s["student_id"],
                            "student_name": s["student_name"],
                            "group_name": s["group_name"],
                        }
                        for s in shuffled if s["student_id"] in assigned_ids
                    ],
                    "unassigned_students": [
                        {
                            "student_id": s["student_id"],
                            "student_name": s["student_name"],
                            "group_name": s["group_name"],
                        }
                        for s in unassigned
                    ],
                    "shuffled_preview": [
                        {
                            "student_id": s["student_id"],
                            "student_name": s["student_name"],
                            "group_name": s["group_name"],
                        }
                        for s in shuffled[:20]
                    ],
                },
            )
        except Exception as exc:
            json_response(self, {"error": str(exc)}, status=400)

    def _get_seatmap(self, path: str) -> None:
        try:
            exam_id = int(path.split("/")[3])
            conn = get_conn(DB_PATH)
            exam = conn.execute(
                """
                SELECT e.exam_id, e.course_name, e.exam_date, e.classroom_id,
                       COALESCE(e.col_reverse, 0) AS col_reverse
                FROM exams e
                WHERE e.exam_id = ?
                """,
                (exam_id,),
            ).fetchone()
            if not exam:
                raise ValueError("exam 不存在")

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

            rooms_payload = []
            for room_id in room_ids:
                room = conn.execute(
                    """
                    SELECT classroom_id, room_name, max_rows, max_cols
                    FROM classrooms
                    WHERE classroom_id = ?
                    """,
                    (room_id,),
                ).fetchone()
                rows = conn.execute(
                    """
                    SELECT
                        se.seat_id, se.classroom_id, se.grid_x, se.grid_y,
                        se.is_usable, se.block_note,
                        s.student_id, s.student_name, s.department_grade, s.group_name,
                        a.violation_flag
                    FROM seats se
                    LEFT JOIN seating_assignments a
                        ON a.seat_id = se.seat_id AND a.exam_id = ?
                    LEFT JOIN students s
                        ON s.student_id = a.student_id
                    WHERE se.classroom_id = ?
                    ORDER BY se.grid_y, se.grid_x
                    """,
                    (exam_id, room_id),
                ).fetchall()
                rooms_payload.append({"room": dict(room), "seats": [dict(r) for r in rows]})

            json_response(self, {"exam": dict(exam), "rooms": rooms_payload})
        except Exception as exc:
            json_response(self, {"error": str(exc)}, status=400)

    def _col_reverse_from_query(self, parsed) -> bool | None:
        q = parse_qs(parsed.query)
        if "col_reverse" not in q:
            return None
        return q["col_reverse"][0] in ("1", "true", "yes")

    def _download_report(self, path: str) -> None:
        try:
            parsed = urlparse(self.path)
            exam_id = int(path.split("/")[3])
            col_override = self._col_reverse_from_query(parsed)
            content = build_report_html(
                exam_id, DB_PATH, col_reverse_override=col_override
            ).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                f'inline; filename="exam_{exam_id}_seatmap_report.html"',
            )
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as exc:
            json_response(self, {"error": str(exc)}, status=400)

    def _download_csv(self, path: str) -> None:
        import re
        from urllib.parse import quote as url_quote
        try:
            parsed = urlparse(self.path)
            exam_id = int(path.split("/")[3])
            col_override = self._col_reverse_from_query(parsed)

            # ── 1. 先把所有資料準備好，任何錯誤在此階段拋出，headers 尚未送出 ──
            output = ROOT / "outputs" / f"exam_{exam_id}_seatmap.xls"
            export_assignment_csv(exam_id, output, col_reverse_override=col_override)
            content = output.read_bytes()

            conn = get_conn(DB_PATH)
            exam_row = conn.execute(
                "SELECT course_name, classroom_id FROM exams WHERE exam_id = ?", (exam_id,)
            ).fetchone()
            if exam_row:
                ec = conn.execute(
                    "SELECT classroom_id FROM exam_classrooms WHERE exam_id = ? LIMIT 1",
                    (exam_id,),
                ).fetchone()
                room_id = ec["classroom_id"] if ec else exam_row["classroom_id"]
                room_row = conn.execute(
                    "SELECT room_name FROM classrooms WHERE classroom_id = ?", (room_id,)
                ).fetchone()
                course = exam_row["course_name"] or "exam"
                room = room_row["room_name"] if room_row else "room"
                safe = re.sub(r'[\\/:*?"<>|]', "_", f"{course}_{room}")
                dl_filename = f"{safe}.xls"
            else:
                dl_filename = f"seatmap_{exam_id}.xls"

            # RFC 5987：UTF-8 percent-encoded 檔名 + ASCII fallback
            ascii_fallback = re.sub(r"[^\x20-\x7E]", "_", dl_filename)
            encoded_name = url_quote(dl_filename, safe="")
            content_disposition = (
                f'attachment; filename="{ascii_fallback}"; '
                f"filename*=UTF-8''{encoded_name}"
            )

            # ── 2. 所有準備完成後才開始送 response，不再有拋出例外的機會 ──
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/vnd.ms-excel")
            self.send_header("Content-Disposition", content_disposition)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as exc:
            json_response(self, {"error": str(exc)}, status=400)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    ensure_initialized()
    try:
        server = ThreadingHTTPServer((host, port), SmartSeatHandler)
    except OSError as exc:
        if exc.errno == 48:
            alt_port = _find_available_port(host, port + 1, port + 50)
            msg = (
                f"Port {port} is already in use.\n"
                f"Try: python3 webapp.py --port {alt_port}\n"
                f"or stop existing process on port {port}."
            )
            raise SystemExit(msg) from exc
        raise
    print(f"SmartSeat demo server: http://{host}:{port}")
    server.serve_forever()


def _find_available_port(host: str, start: int, end: int) -> int:
    for p in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex((host, p)) != 0:
                return p
    return start


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SmartSeat demo web server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
