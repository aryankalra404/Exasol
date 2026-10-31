"""Robustness: the same book at defect levels from none to heavy, audited in Exasol, scored against the truth tables.

Each level is generated with the same seed into data/robustness/, loaded into separate schemas (ROB_*), audited,
and compared with SAHI_TRUTH-style expected values read from the generated truth CSVs. Demo schemas are not touched.

Usage: python -m eval.robustness --loans 10000 --levels 0 1 3
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from datetime import date
from pathlib import Path

from generator.generate import generate
from scripts.audit import run_audit
from scripts.db import connect, schemas
from scripts.load import load

ROOT = Path(__file__).resolve().parent.parent
FAIR = "MIH|DIS|NET|EXACT"
NOT_UNFAIR = {FAIR, "CFEE"}


def rows(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def score(book: Path, run_id: str) -> dict:
    s = schemas()
    conn = connect()
    summary = conn.execute(f"SELECT refund_paise, refund_loans, ambiguous_paise, gap_tranches, gap_loans, unexplained_periods, "
                           f"undercharge_periods, conflict_tranches, periods_audited FROM {s['OUT']}.run_summary WHERE run_id = {{r}}",
                           {"r": run_id}).fetchone()
    fp = conn.execute(f"SELECT loan_id, TO_CHAR(period_start, 'YYYY-MM-DD'), match_status, excess_paise FROM {s['OUT']}.fingerprints "
                      f"WHERE run_id = {{r}}", {"r": run_id}).fetchall()
    conn.close()
    truth = {(r["loan_id"], r["period_start"]): r for r in rows(book / "truth" / "expected.csv")}
    true_excess = sum(int(t["true_posted_paise"]) - int(t["true_fair_paise"]) for t in truth.values()
                      if t["true_convention_id"] not in NOT_UNFAIR)
    wrong = [(k, int(x)) for *k, st, x in ((a, b, st, x) for a, b, st, x in fp)
             if st in ("MATCHED", "AMBIGUOUS") and truth.get(tuple(k), {}).get("true_convention_id") in NOT_UNFAIR]
    refund, refund_loans, amb, gap_t, gap_l, unexpl, under, conflict, periods = (int(v) for v in summary)
    return {
        "planted_defects": len(rows(book / "truth" / "planted_defects.csv")),
        "periods_audited": periods,
        "refund_paise": refund,
        "refund_loans": refund_loans,
        "ambiguous_paise": amb,
        "true_unfair_excess_paise": true_excess,
        "refund_share_of_true_excess_pct": round(100 * refund / true_excess, 2) if true_excess else None,
        "wrongly_refunded_periods": len(wrong),
        "wrongly_refunded_paise": sum(x for _, x in wrong),
        "evidence_gap_tranches": gap_t,
        "evidence_gap_loans": gap_l,
        "unexplained_periods": unexpl,
        "undercharge_periods": under,
        "conflict_tranches": conflict,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--loans", type=int, default=10000)
    p.add_argument("--levels", type=float, nargs="+", default=[0, 1, 3])
    p.add_argument("--out", default=str(ROOT / "eval" / "reports" / "robustness.json"))
    args = p.parse_args()
    for key in ("RAW", "POLICY", "OUT", "TRUTH", "WORK"):
        os.environ[f"EXASOL_SCHEMA_{key}"] = f"ROB_{key}"
    report = {"seed": args.seed, "loans": args.loans, "date": date.today().isoformat(), "levels": {}}
    for level in args.levels:
        t0 = time.perf_counter()
        book = generate(args.seed, args.loans, date(2026, 10, 1), level, ROOT / "data" / "robustness" / f"d{level:g}")
        load(book)
        run = run_audit(f"robustness defects={level:g}")
        result = score(book, run["run_id"])
        result["audit_ms"] = run["duration_ms"]
        result["wall_s"] = round(time.perf_counter() - t0, 1)
        report["levels"][f"{level:g}"] = result
        print(f"defects={level:g}", json.dumps(result))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
