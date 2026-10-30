"""Independent oracle for Sahi Byaaj.

Recomputes money-in-hand dates, fair interest and the convention fingerprint for every loan directly from the
generated CSV extracts, walking the loan day by day. It implements docs/DOMAIN.md on its own and shares no code
with sql/ or generator/. Its only job is to disagree with the SQL pipeline when either is wrong.

Integer arithmetic throughout: one day of interest is balance_paise * rate_micro * weight, accumulated per
period and divided once (half up) by 100 * 1,000,000 * divisor. Default policy from DOMAIN.md.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from itertools import product
from pathlib import Path

START = {"MIH": "MONEY_IN_HAND", "CHQ": "CHEQUE_DATE", "SNC": "SANCTION_DATE", "AGR": "AGREEMENT_DATE"}
FAIR_ID = "MIH|DIS|NET|EXACT"


def conventions() -> list[str]:
    ids = ["|".join(p) for p in product(["MIH", "CHQ", "SNC", "AGR"], ["DIS", "SAN"], ["NET", "IGN"], ["EXACT", "FULL"])]
    return ids + ["CFEE"]


def practices(conv: str) -> frozenset[str]:
    if conv == "CFEE":
        return frozenset({"P1"})
    s, p, a, m = conv.split("|")
    out = set()
    if s == "CHQ":
        out.add("P2")
    if s in ("SNC", "AGR"):
        out.add("P1")
    if p == "SAN":
        out.add("P5")
    if a == "IGN":
        out.add("P4")
    if m == "FULL":
        out.add("P3")
    return frozenset(out)


def dims(conv: str) -> int:
    return 1 if conv == "CFEE" else sum(1 for x in conv.split("|") if x not in ("MIH", "DIS", "NET", "EXACT"))


def d(s: str) -> date | None:
    return date.fromisoformat(s) if s else None


def first_of_month(x: date) -> date:
    return date(x.year, x.month, 1)


def add_month(x: date) -> date:
    return date(x.year + (x.month == 12), x.month % 12 + 1, 1)


@dataclass
class Tr:
    no: int
    amount: int
    mode: str
    mih: date | None
    confidence: str
    cheque: date | None
    ev_min: date
    ev_max: date

    @property
    def start(self) -> date:
        return self.mih or self.ev_max


def read(path: Path) -> list[dict]:
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


class Book:
    def __init__(self, dataset_dir: Path):
        raw = dataset_dir / "raw"
        self.loans = {r["loan_id"]: r for r in read(raw / "loans.csv")}
        self.kfs = {r["loan_id"]: r for r in read(raw / "kfs.csv")}
        self.rates = defaultdict(list)
        for r in read(raw / "rate_history.csv"):
            self.rates[r["loan_id"]].append((d(r["effective_date"]), Decimal(r["annual_rate_pct"])))
        for v in self.rates.values():
            v.sort()
        evidence = defaultdict(lambda: defaultdict(list))
        for r in read(raw / "disbursement_evidence.csv"):
            evidence[(r["loan_id"], int(r["tranche_no"]))][r["evidence_source"]].append(d(r["event_date"]))
        self.tranches = defaultdict(list)
        for r in read(raw / "tranches.csv"):
            key = (r["loan_id"], int(r["tranche_no"]))
            ev = evidence[key]
            earliest = {src: min(ds) for src, ds in ev.items()}
            mode = r["payment_mode"]
            mih, conf = None, "GAP"
            if mode in ("CHEQUE", "DD"):
                if "HANDOVER_ACK" in earliest:
                    mih = max(earliest["HANDOVER_ACK"], earliest.get("CHEQUE_DATE", earliest["HANDOVER_ACK"]))
                    conf = "CONFIRMED"
            elif "RAIL_CREDIT" in earliest:
                mih, conf = earliest["RAIL_CREDIT"], "CONFIRMED"
            elif "LMS_DISB" in earliest:
                mih, conf = earliest["LMS_DISB"], "FALLBACK"
            all_dates = [x for ds in ev.values() for x in ds]
            self.tranches[r["loan_id"]].append(Tr(int(r["tranche_no"]), int(r["amount_paise"]), mode, mih, conf,
                                                  earliest.get("CHEQUE_DATE"), min(all_dates), max(all_dates)))
        for v in self.tranches.values():
            v.sort(key=lambda t: t.no)
        self.receipts = defaultdict(list)
        for r in read(raw / "receipts.csv"):
            self.receipts[r["loan_id"]].append(r)
        self.posted = defaultdict(int)
        self.posted_periods = defaultdict(set)
        for r in read(raw / "interest_postings.csv"):
            ps = d(r["period_start"])
            self.posted[(r["loan_id"], ps)] += int(r["posted_paise"])
            self.posted_periods[r["loan_id"]].add(ps)
        self.audit_end = max(add_month(p) for ps in self.posted_periods.values() for p in ps)

    # ---- balance path per convention, as a list of (date, delta_balance, delta_fee) ----
    def path(self, loan_id: str, conv: str) -> list[tuple[date, int, int]]:
        loan = self.loans[loan_id]
        trs = self.tranches[loan_id]
        cfee = conv == "CFEE"
        s, p, a, m = FAIR_ID.split("|") if cfee else conv.split("|")
        sanction, agreement = d(loan["sanction_date"]), d(loan["agreement_date"])
        sanctioned = int(loan["sanctioned_paise"])
        disbursed = sum(t.amount for t in trs)
        ev: list[tuple[date, int, int]] = []

        def tranche_start(t: Tr) -> date:
            x = t.start
            if s == "CHQ" and t.mode in ("CHEQUE", "DD") and t.cheque:
                x = t.cheque
            elif s == "SNC" and t.no == 1:
                x = sanction
            elif s == "AGR" and t.no == 1:
                x = agreement
            return first_of_month(x) if m == "FULL" else x

        if p == "SAN":
            ev.append((tranche_start(trs[0]), sanctioned, 0))
        else:
            ev += [(tranche_start(t), t.amount, 0) for t in trs]
        closure = None
        for r in self.receipts[loan_id]:
            prin = int(r["principal_paise"])
            if prin == 0:
                continue
            when = d(r["value_date"])
            if r["kind"] == "ADVANCE_EMI" and a == "IGN" and r["due_date"]:
                when = d(r["due_date"])
            if r["kind"] == "CLOSURE":
                closure = d(r["value_date"]) if closure is None else min(closure, d(r["value_date"]))
                if m == "FULL" and when.day != 1:
                    when = add_month(first_of_month(when))
            ev.append((when, -prin, 0))
        if p == "SAN" and closure and sanctioned != disbursed:
            cd = add_month(first_of_month(closure)) if (m == "FULL" and closure.day != 1) else closure
            ev.append((cd, -(sanctioned - disbursed), 0))
        if cfee:
            ev.append((sanction, 0, sanctioned))
            ev += [(t.start, 0, -t.amount) for t in trs]
            if closure and sanctioned != disbursed:
                ev.append((closure, 0, -(sanctioned - disbursed)))
        return ev

    def period_interest(self, loan_id: str, conv: str, periods: list[date]) -> dict[date, int]:
        """Walk the loan day by day across the given periods and return rounded interest per period."""
        kfs = self.kfs[loan_id]
        basis = kfs["day_count_basis"]
        divisor = 360 if basis == "30E_360" else 365
        fee_micro = int(Decimal(kfs["commitment_fee_rate_pct"] or "0") * 1000000)
        rates = self.rates[loan_id]
        ev = sorted(self.path(loan_id, conv))
        out = {}
        for ps in periods:
            pe = add_month(ps)
            bal = sum(db for t, db, _ in ev if t <= ps)
            fee = sum(df for t, _, df in ev if t <= ps)
            todays = defaultdict(lambda: [0, 0])
            for t, db, df in ev:
                if ps < t < pe:
                    todays[t][0] += db
                    todays[t][1] += df
            n = 0
            day = ps
            while day < pe:
                if day in todays:
                    bal += todays[day][0]
                    fee += todays[day][1]
                rate = rates[0][1]
                for eff, r in rates:
                    if eff <= day:
                        rate = r
                nxt = day + timedelta(days=1)
                w = weight_30e(day, nxt) if basis == "30E_360" else 1
                n += (bal * int(rate * 1000000) + fee * fee_micro) * w
                day = nxt
            den = 100 * 1000000 * divisor
            # half up, away from zero (negative only in a provisional evidence-gap period)
            out[ps] = (1 if n >= 0 else -1) * ((2 * abs(n) + den) // (2 * den))
        return out


def weight_30e(a: date, b: date) -> int:
    def f(x: date) -> int:
        return 360 * x.year + 30 * x.month + min(x.day, 30)

    return f(b) - f(a)


@dataclass
class Result:
    loan_id: str
    period_start: date
    posted: int
    fair: int
    status: str
    convention: str | None


def audit(dataset_dir: Path, loan_ids: list[str] | None = None) -> list[Result]:
    book = Book(dataset_dir)
    convs = [c for c in conventions() if c != FAIR_ID]
    results: list[Result] = []
    for loan_id in loan_ids or sorted(book.loans):
        sanction = d(book.loans[loan_id]["sanction_date"])
        months = []
        ps = first_of_month(sanction)
        while ps < book.audit_end:
            months.append(ps)
            ps = add_month(ps)
        fair = book.period_interest(loan_id, FAIR_ID, months)
        periods = [p for p in months if fair[p] != 0 or p in book.posted_periods[loan_id]]
        gaps = [t for t in book.tranches[loan_id] if t.confidence == "GAP"]
        has_fee = bool(book.kfs[loan_id]["commitment_fee_rate_pct"])
        differing = [p for p in periods if book.posted[(loan_id, p)] != fair[p]
                     and not any(t.ev_min < add_month(p) and t.ev_max >= p for t in gaps)]
        cand = {c: book.period_interest(loan_id, c, differing) for c in convs if c != "CFEE" or has_fee}
        matches = {p: [c for c in cand if cand[c][p] == book.posted[(loan_id, p)]] for p in differing}
        support = defaultdict(int)
        for p, ms in matches.items():
            for c in ms:
                if c != "CFEE":  # CFEE is permitted under default policy, so it never competes as unfair
                    support[c] += 1
        for p in periods:
            posted = book.posted[(loan_id, p)]
            status, conv = "FAIR", FAIR_ID
            if any(t.ev_min < add_month(p) and t.ev_max >= p for t in gaps):
                status, conv = "EVIDENCE_GAP", None
            elif posted != fair[p]:
                ms = matches[p]
                unfair = [c for c in ms if c != "CFEE"]
                if "CFEE" in ms:
                    status, conv = "PERMITTED", "CFEE"
                elif unfair:
                    best = max(support[c] for c in unfair)
                    top = [c for c in unfair if support[c] == best]
                    fewest = min(dims(c) for c in top)
                    top = sorted(c for c in top if dims(c) == fewest)
                    if posted < fair[p]:
                        status, conv = "UNDERCHARGE", None
                    elif len({practices(c) for c in top}) == 1:
                        status, conv = "MATCHED", top[0]
                    else:
                        status, conv = "AMBIGUOUS", None
                else:
                    status, conv = ("UNDERCHARGE" if posted < fair[p] else "UNEXPLAINED"), None
            results.append(Result(loan_id, p, posted, fair[p], status, conv))
    return results
