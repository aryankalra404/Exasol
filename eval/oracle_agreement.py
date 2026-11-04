"""Compare the latest audit run in Exasol with the independent oracle, period by period.

Usage: python -m eval.oracle_agreement data/s42_n2000 [--loans 500]
"""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import date
from pathlib import Path

from oracle.oracle import audit
from scripts.db import connect, schemas


def latest_run(conn) -> str:
    s = schemas()
    return conn.execute(f"SELECT run_id FROM {s['OUT']}.audit_runs WHERE status = 'DONE' "
                        f"ORDER BY started_at DESC LIMIT 1").fetchval()


def entered_evidence(conn) -> list[dict]:
    """Dates a person entered from a branch reply are audit input, so the oracle reads them too."""
    s = schemas()
    cols = ["loan_id", "tranche_no", "evidence_source", "event_date"]
    return [dict(zip(cols, r)) for r in conn.execute(
        f"SELECT a.loan_id, a.tranche_no, a.evidence_source, TO_CHAR(a.event_date, 'YYYY-MM-DD') "
        f"FROM {s['POLICY']}.evidence_additions a JOIN {s['RAW']}.dataset_info i ON i.dataset_id = a.dataset_id "
        f"WHERE a.withdrawn_at IS NULL").fetchall()]


def compare(dataset_dir: Path, sample: int | None = None, seed: int = 7) -> dict:
    s = schemas()
    conn = connect()
    run_id = latest_run(conn)
    rows = conn.execute(f"SELECT loan_id, period_start, posted_paise, fair_paise, match_status, matched_convention_id "
                        f"FROM {s['OUT']}.fingerprints WHERE run_id = {{r}}", {"r": run_id}).fetchall()
    sql = {(r[0], date.fromisoformat(r[1])): r for r in rows}
    loan_ids = sorted({k[0] for k in sql})
    if sample and sample < len(loan_ids):
        demo = [x for x in loan_ids if x.startswith("LDM")]
        loan_ids = sorted(set(random.Random(seed).sample(loan_ids, sample)) | set(demo))
    t0 = time.perf_counter()
    results = audit(dataset_dir, loan_ids, entered_evidence(conn))
    oracle_s = time.perf_counter() - t0
    keys = {(r.loan_id, r.period_start) for r in results}
    sql_keys = {k for k in sql if k[0] in set(loan_ids)}
    fair_agree = status_agree = conv_agree = 0
    max_dev = 0
    disagreements = []
    for r in results:
        row = sql.get((r.loan_id, r.period_start))
        if row is None:
            disagreements.append({"loan": r.loan_id, "period": str(r.period_start), "issue": "missing in SQL"})
            continue
        _, _, posted, fair, status, conv = row
        dev = abs(int(fair) - r.fair)
        max_dev = max(max_dev, dev)
        fair_agree += dev == 0
        status_agree += status == r.status
        conv_ok = status != "MATCHED" or conv == r.convention
        conv_agree += conv_ok
        if dev or status != r.status or not conv_ok:
            disagreements.append({"loan": r.loan_id, "period": str(r.period_start), "sql": [str(fair), status, conv],
                                  "oracle": [r.fair, r.status, r.convention]})
    n = len(results)
    return {
        "run_id": run_id, "loans": len(loan_ids), "periods_compared": n,
        "periods_only_in_sql": len(sql_keys - keys),
        "fair_exact": fair_agree, "status_agree": status_agree, "matched_convention_agree": conv_agree,
        "fair_exact_pct": round(100 * fair_agree / n, 4) if n else None,
        "largest_fair_deviation_paise": max_dev,
        "oracle_seconds": round(oracle_s, 1),
        "disagreements": disagreements[:20],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("dataset_dir")
    p.add_argument("--loans", type=int, default=None, help="random sample of loans (demo loans always included)")
    a = p.parse_args()
    print(json.dumps(compare(Path(a.dataset_dir), a.loans), indent=2))


if __name__ == "__main__":
    main()
