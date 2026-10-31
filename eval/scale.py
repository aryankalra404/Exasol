"""Scale run: generate, load and audit a large book in separate SCALE_* schemas, and record what was measured.

Demo schemas are untouched. Writes eval/reports/scale_<dataset_id>.json with timings, row counts and hardware.

Usage: python -m eval.scale --seed 7 --loans 1000000
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def hardware() -> str:
    try:
        cpu = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
        mem = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)) // 2**30
        return f"{cpu}, {mem} GB, {platform.system()}"
    except (OSError, subprocess.CalledProcessError, ValueError):
        return platform.platform()


def check_disk(min_free_gb: float) -> None:
    """Stop before the host disk fills: the Exasol VM image grows with temp data and does not shrink."""
    free = shutil.disk_usage(ROOT).free / 2**30
    if free < min_free_gb:
        raise SystemExit(f"only {free:.1f} GB free on the host disk (need {min_free_gb} GB); stopping")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--loans", type=int, default=1000000)
    p.add_argument("--skip-generate", action="store_true", help="reuse data/s<seed>_n<loans>")
    p.add_argument("--min-free-gb", type=float, default=6.0)
    args = p.parse_args()
    for key in ("RAW", "POLICY", "OUT", "TRUTH", "WORK"):
        os.environ[f"EXASOL_SCHEMA_{key}"] = f"SCALE_{key}"
    from generator.generate import generate
    from scripts.audit import run_audit
    from scripts.db import connect, schemas
    from scripts.load import load

    report: dict = {"date": date.today().isoformat(), "hardware": hardware(), "seed": args.seed, "loans": args.loans}
    book = ROOT / "data" / f"s{args.seed}_n{args.loans}"
    check_disk(args.min_free_gb)
    if not args.skip_generate:
        t0 = time.perf_counter()
        book = generate(args.seed, args.loans, date(2026, 10, 1), 1.0, ROOT / "data")
        report["generate_s"] = round(time.perf_counter() - t0, 1)
        print("generated", report["generate_s"], "s", flush=True)
    check_disk(args.min_free_gb)
    t0 = time.perf_counter()
    loaded = load(book)
    report["load_s"] = round(time.perf_counter() - t0, 1)
    report["rows"] = loaded["rows"]
    print("loaded", report["load_s"], "s", flush=True)
    check_disk(args.min_free_gb)
    run = run_audit(f"scale {book.name}")
    report["audit_s"] = round(run["duration_ms"] / 1000, 1)
    report["steps"] = run["steps"]
    print("audited", report["audit_s"], "s", flush=True)
    s = schemas()
    conn = connect()
    report["summary"] = dict(zip(
        ["loans", "tranches", "periods", "postings", "refund_paise", "refund_loans"],
        [int(v) for v in conn.execute(f"SELECT loans_audited, tranches, periods_audited, posting_rows, refund_paise, refund_loans "
                                      f"FROM {s['OUT']}.run_summary WHERE run_id = {{r}}", {"r": run["run_id"]}).fetchone()]))
    report["work_rows"] = {t: int(n) for t, n in conn.execute(
        "SELECT table_name, table_row_count FROM EXA_ALL_TABLES WHERE table_schema = {s} ORDER BY 1", {"s": s["WORK"]}).fetchall()}
    conn.close()
    out = ROOT / "eval" / "reports" / f"scale_{book.name}.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"]), "->", out)


if __name__ == "__main__":
    main()
