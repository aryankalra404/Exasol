"""Load a generated dataset into Exasol with IMPORT (via pyexasol).

Usage: python -m scripts.load data/s42_n10000
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from scripts.db import connect, schemas
from scripts.sqlrun import SQL_DIR, run_file

RAW_TABLES = ["branches", "borrowers", "loans", "kfs", "kfs_disbursal_schedule", "rate_history", "tranches",
              "disbursement_evidence", "demands", "receipts", "interest_postings"]
TRUTH_TABLES = ["lms_config", "planted_defects", "expected"]


def load(dataset_dir: Path) -> dict:
    s = schemas()
    conn = connect()
    run_file(conn, SQL_DIR / "01_raw_schema.sql")
    run_file(conn, SQL_DIR / "05_policy_and_out_schema.sql")
    counts = {}
    t0 = time.perf_counter()
    for sub, tables, schema in (("raw", RAW_TABLES, s["RAW"]), ("truth", TRUTH_TABLES, s["TRUTH"])):
        for table in tables:
            path = dataset_dir / sub / f"{table}.csv"
            conn.import_from_file(str(path), (schema, table.upper()),
                                  import_params={"skip": 1, "column_delimiter": "\"", "column_separator": ","})
            counts[f"{schema}.{table}"] = conn.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchval()
    manifest = json.loads((dataset_dir / "manifest.json").read_text())
    conn.execute(f"CREATE OR REPLACE TABLE {s['RAW']}.dataset_info (dataset_id VARCHAR(50), seed DECIMAL(10,0), "
                 f"loans DECIMAL(12,0), as_of DATE, generator_version VARCHAR(20))")
    conn.execute(f"INSERT INTO {s['RAW']}.dataset_info VALUES ({{id}}, {{seed}}, {{loans}}, {{as_of}}, {{ver}})",
                 {"id": manifest["dataset_id"], "seed": manifest["seed"], "loans": manifest["loans"],
                  "as_of": manifest["as_of"], "ver": manifest["generator_version"]})
    conn.close()
    return {"dataset_id": manifest["dataset_id"], "load_ms": int((time.perf_counter() - t0) * 1000), "rows": counts}


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(json.dumps(load(Path(sys.argv[1])), indent=2))


if __name__ == "__main__":
    main()
