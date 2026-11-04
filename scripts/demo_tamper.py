"""Rehearsal helper for the one-paisa moment: add a paisa to Meena's March 2025 posting, or take it back.

Only ever moves the posting between its two known values, so running either direction twice is harmless and it can
never drift. The statement it runs is printed, so what happens is visible on screen. Re-run the audit afterwards.
"""

from __future__ import annotations

import argparse

from scripts.db import connect, schemas

POSTING_ID = "PDM0001010"
ORIGINAL = 2190497
TAMPERED = ORIGINAL + 1


def statement(raw: str, undo: bool) -> str:
    old, new = (TAMPERED, ORIGINAL) if undo else (ORIGINAL, TAMPERED)
    return f"UPDATE {raw}.interest_postings SET posted_paise = {new} WHERE posting_id = '{POSTING_ID}' AND posted_paise = {old}"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--undo", action="store_true", help="restore the original posting")
    args = p.parse_args()
    raw = schemas()["RAW"]
    sql = statement(raw, args.undo)
    print(sql)
    conn = connect()
    try:
        st = conn.execute(sql)
        conn.commit()
        now = conn.execute(f"SELECT posted_paise FROM {raw}.interest_postings WHERE posting_id = '{POSTING_ID}'").fetchall()
    finally:
        conn.close()
    print(f"{st.rowcount()} row changed. {POSTING_ID} now holds {now[0][0] if now else 'nothing'} paise")


if __name__ == "__main__":
    main()
