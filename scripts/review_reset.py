"""Clear review records for the loaded synthetic book, to rehearse the demo from a clean slate.

Refuses on an uploaded book: the review log is an audit trail, and this exists only for synthetic rehearsals.

Usage: python -m scripts.review_reset
"""

from __future__ import annotations

from scripts.db import connect, schemas


def main() -> None:
    s = schemas()
    conn = connect()
    dataset_id, version = conn.execute(f"SELECT dataset_id, generator_version FROM {s['RAW']}.dataset_info").fetchone()
    if version == "upload":
        raise SystemExit("The loaded book is an upload. Its review log is an audit trail and will not be cleared.")
    for table in ("review_decisions", "letter_releases", "release_batches"):
        st = conn.execute(f"DELETE FROM {s['POLICY']}.{table} WHERE dataset_id = {{d}}", {"d": dataset_id})
        print(f"{table}: {st.rowcount()} rows cleared for {dataset_id}")
    conn.close()


if __name__ == "__main__":
    main()
