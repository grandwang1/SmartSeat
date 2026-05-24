from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run_step(step: str) -> None:
    import subprocess
    import sys

    cmd = [sys.executable, str(ROOT / "scripts" / step)]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="SmartSeat MVP runner")
    parser.add_argument(
        "--only",
        choices=["setup", "assign", "export", "visualize", "all"],
        default="all",
        help="Run a single stage or all",
    )
    args = parser.parse_args()

    if args.only in ("setup", "all"):
        run_step("setup_project.py")
    if args.only in ("assign", "all"):
        run_step("run_assignment.py")
    if args.only in ("export", "all"):
        run_step("export_results.py")
    if args.only in ("visualize", "all"):
        run_step("visualize_seatmap.py")


if __name__ == "__main__":
    main()
