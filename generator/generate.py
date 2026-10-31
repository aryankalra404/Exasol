"""Synthetic loan book generator for Sahi Byaaj.

Writes one CSV per table to data/<dataset_id>/raw (what a lender extract would
hold) and data/<dataset_id>/truth (hidden LMS configuration, planted defects,
expected values; read by tests and eval only).

Deterministic for a given --seed and --loans. All names and ids are synthetic.

Usage: python -m generator.generate --seed 42 --loans 10000
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, getcontext
from pathlib import Path

from generator.lms import (
    CFEE,
    FAIR,
    LoanState,
    Receipt,
    Tranche,
    month_start,
    next_month,
    period_interest,
)

getcontext().prec = 60

GENERATOR_VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parent.parent

BRANCHES = [
    ("BR001", "Pune Kothrud", "Maharashtra", "WEST"),
    ("BR002", "Pune Hadapsar", "Maharashtra", "WEST"),
    ("BR003", "Nagpur Civil Lines", "Maharashtra", "WEST"),
    ("BR004", "Indore Vijay Nagar", "Madhya Pradesh", "CENTRAL"),
    ("BR005", "Jaipur Malviya Nagar", "Rajasthan", "NORTH"),
    ("BR006", "Lucknow Gomti Nagar", "Uttar Pradesh", "NORTH"),
    ("BR007", "Coimbatore RS Puram", "Tamil Nadu", "SOUTH"),
    ("BR008", "Mysuru Vijayanagar", "Karnataka", "SOUTH"),
    ("BR009", "Vadodara Alkapuri", "Gujarat", "WEST"),
    ("BR010", "Bhubaneswar Saheed Nagar", "Odisha", "EAST"),
    ("BR011", "Kochi Kakkanad", "Kerala", "SOUTH"),
    ("BR012", "Guwahati Dispur", "Assam", "EAST"),
]

# Hidden LMS configuration. (branch, valid_from, applies_to, convention).
# A loan's convention for a period is the latest row with valid_from <= period
# start that applies to it: ALL_LOANS rows apply to every loan, NEW_LOANS rows
# only to loans sanctioned on or after valid_from.
EPOCH = date(2000, 1, 1)
LMS_CONFIG = [
    # cheque date until mid-2024, then fixed for new loans only (never migrated)
    ("BR001", EPOCH, "ALL_LOANS", "CHQ|DIS|NET|EXACT"),
    ("BR001", date(2024, 7, 1), "NEW_LOANS", FAIR),
    ("BR002", EPOCH, "ALL_LOANS", "CHQ|DIS|NET|EXACT"),
    ("BR002", date(2024, 7, 1), "NEW_LOANS", FAIR),
    ("BR003", EPOCH, "ALL_LOANS", "CHQ|DIS|NET|FULL"),
    ("BR003", date(2024, 7, 1), "NEW_LOANS", FAIR),
    # sanction date, fixed for all loans from Jan 2025
    ("BR004", EPOCH, "ALL_LOANS", "SNC|DIS|NET|EXACT"),
    ("BR004", date(2025, 1, 1), "ALL_LOANS", FAIR),
    ("BR005", EPOCH, "ALL_LOANS", "MIH|DIS|NET|FULL"),
    ("BR006", EPOCH, "ALL_LOANS", "MIH|DIS|IGN|EXACT"),
    ("BR007", EPOCH, "ALL_LOANS", "MIH|SAN|NET|EXACT"),
    # commitment fee where the KFS discloses one, fair otherwise
    ("BR008", EPOCH, "ALL_LOANS", CFEE),
    ("BR009", EPOCH, "ALL_LOANS", FAIR),
    ("BR010", EPOCH, "ALL_LOANS", "AGR|DIS|NET|EXACT"),
    ("BR011", EPOCH, "ALL_LOANS", FAIR),
    ("BR012", EPOCH, "ALL_LOANS", FAIR),
]

FIRST = ["Aarav", "Diya", "Kabir", "Isha", "Rohan", "Ananya", "Vivaan", "Kavya", "Arjun", "Nisha",
         "Rahul", "Pooja", "Siddharth", "Lakshmi", "Farhan", "Neha", "Karthik", "Sneha", "Manoj", "Divya",
         "Imran", "Priyanka", "Suresh", "Anjali", "Varun", "Fatima", "Gaurav", "Meera", "Harish", "Ritu"]
LAST = ["Sharma", "Iyer", "Khan", "Patel", "Reddy", "Nair", "Gupta", "Das", "Joshi", "Menon",
        "Singh", "Kulkarni", "Banerjee", "Rao", "Pillai", "Mehta", "Chauhan", "Bose", "Shetty", "Yadav"]


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def next_working(d: date) -> date:
    while is_weekend(d):
        d += timedelta(days=1)
    return d


def add_working(d: date, n: int) -> date:
    while n > 0:
        d += timedelta(days=1)
        if not is_weekend(d):
            n -= 1
    return d


def emi_amount(principal: int, rate: Decimal, months: int) -> int:
    r = rate / Decimal(1200)
    f = (1 + r) ** months
    emi = Decimal(principal) * r * f / (f - 1)
    # rounded to the nearest rupee, as lenders usually do
    return int((emi / 100).quantize(Decimal(1))) * 100


def conv_for(branch: str, sanction: date, ps: date) -> str:
    chosen = FAIR
    for b, vf, applies, conv in LMS_CONFIG:
        if b != branch or vf > ps:
            continue
        if applies == "NEW_LOANS" and sanction < vf:
            continue
        chosen = conv
    return chosen


@dataclass
class LoanSpec:
    loan_id: str
    borrower_id: str
    branch_id: str
    product: str
    sanction_date: date
    agreement_date: date
    sanctioned: int
    tenure: int
    rate: Decimal
    tranches: list[Tranche]
    rail_credit: dict[int, date | None] = field(default_factory=dict)
    lms_disb: dict[int, date] = field(default_factory=dict)
    handover: dict[int, list[date]] = field(default_factory=dict)  # recorded acks
    rate_resets: list[tuple[date, Decimal]] = field(default_factory=list)
    kfs_basis: str = "ACT_365"
    lms_basis: str = "ACT_365"
    fee_rate: Decimal | None = None
    advance_emi: bool = False
    closure_date: date | None = None
    late_days: dict[date, int] = field(default_factory=dict)
    reversal_periods: set[date] = field(default_factory=set)
    manual_adj: dict[date, int] = field(default_factory=dict)
    defects: list[tuple[int | None, str, str]] = field(default_factory=list)


class Book:
    """Writes each row straight to its table's CSV, in insertion order, so memory stays flat at any book size."""

    def __init__(self, out: Path) -> None:
        self.out = out
        self.counts: dict[str, int] = {}
        self._files: dict = {}
        self._writers: dict = {}
        for sub in ("raw", "truth"):
            (out / sub).mkdir(parents=True, exist_ok=True)
        for table in TABLES_RAW + TABLES_TRUTH:
            sub = "raw" if table in TABLES_RAW else "truth"
            fh = open(out / sub / f"{table}.csv", "w", newline="")
            self._files[table] = fh
            self._writers[table] = csv.writer(fh, lineterminator="\n")
            self._writers[table].writerow(COLUMNS[table])
            self.counts[table] = 0

    def add(self, table: str, row: dict) -> None:
        self._writers[table].writerow([fmt(row.get(c)) for c in COLUMNS[table]])
        self.counts[table] += 1

    def close(self) -> None:
        for fh in self._files.values():
            fh.close()


def make_bulk_loan(rng: random.Random, i: int, as_of: date, defect_scale: float) -> LoanSpec:
    loan_id = f"L{i:06d}"
    borrower_id = f"B{i:06d}"
    branch_id = rng.choice(BRANCHES)[0]
    product = "HOME" if rng.random() < 0.55 else "PERSONAL"
    span = (date(2026, 3, 31) - date(2023, 1, 1)).days
    sanction = date(2023, 1, 1) + timedelta(days=rng.randrange(span))
    sanction = next_working(sanction)
    spec_kwargs: dict = {}
    if product == "HOME":
        sanctioned = rng.randrange(300, 1800) * 500000  # Rs 15L to 90L in Rs 5,000 steps
        tenure = rng.choice([180, 240, 300])
        rate = Decimal(rng.randrange(825, 1051, 5)) / 100
        agreement = sanction + timedelta(days=rng.randint(1, 10))
        staged = rng.random() < 0.6
        n = rng.randint(2, 4) if staged else 1
        amounts = _split(rng, sanctioned, n)
        first = agreement + timedelta(days=rng.randint(5, 40))
        dates = [first]
        for _ in range(n - 1):
            dates.append(dates[-1] + timedelta(days=rng.randint(60, 200)))
        if staged and rng.random() < 0.15:
            # last tranche not disbursed yet: sanctioned exceeds disbursed
            amounts, dates = amounts[:-1], dates[:-1]
        modes = [rng.choices(["CHEQUE", "DD", "NEFT", "RTGS"], [35, 10, 30, 25])[0] for _ in amounts]
    else:
        sanctioned = rng.randrange(100, 1500) * 100000  # Rs 1L to 15L
        tenure = rng.choice([12, 24, 36, 48, 60])
        rate = Decimal(rng.randrange(1100, 1801, 25)) / 100
        agreement = sanction
        amounts = [sanctioned]
        dates = [sanction + timedelta(days=rng.randint(0, 10))]
        modes = [rng.choices(["NEFT", "IMPS", "CHEQUE"], [55, 30, 15])[0]]
        spec_kwargs["advance_emi"] = rng.random() < 0.3
    tranches: list[Tranche] = []
    spec = LoanSpec(loan_id, borrower_id, branch_id, product, sanction, agreement, sanctioned,
                    tenure, rate, tranches, **spec_kwargs)
    for k, (amt, d, mode) in enumerate(zip(amounts, dates, modes), start=1):
        if mode in ("CHEQUE", "DD"):
            cheque = next_working(d)
            lag = 0 if rng.random() < 0.4 else rng.randint(1, 12)
            mih = cheque + timedelta(days=lag)
            if mih >= as_of:
                break
            spec.lms_disb[k] = cheque
            spec.handover[k] = [mih]
            spec.rail_credit[k] = add_working(mih, rng.randint(1, 3)) if rng.random() < 0.5 else None
            tranches.append(Tranche(k, amt, mode, mih, cheque))
        else:
            init = d
            mih = next_working(init)
            if mih >= as_of:
                break
            spec.lms_disb[k] = init
            spec.rail_credit[k] = mih
            tranches.append(Tranche(k, amt, mode, mih, None))
    if not tranches:
        return make_bulk_loan(rng, i, as_of, defect_scale)  # sanctioned too late, redraw
    if product == "HOME" and rng.random() < 0.3:
        eff = month_start(sanction + timedelta(days=rng.randint(180, 540)))
        if eff < as_of:
            spec.rate_resets.append((eff, rate + Decimal(rng.choice([-25, -15, -10, 10, 15, 25])) / 100))
    if product == "PERSONAL" and rng.random() < 0.05:
        spec.kfs_basis = spec.lms_basis = "30E_360"
    if branch_id == "BR008" and product == "HOME" and rng.random() < 0.5:
        spec.fee_rate = Decimal(rng.choice([50, 75, 100])) / 100
    if rng.random() < 0.08:
        last = tranches[-1].mih
        if (as_of - last).days > 120:
            spec.closure_date = next_working(last + timedelta(days=rng.randint(90, (as_of - last).days - 10)))
    _plant_defects(rng, spec, defect_scale)
    return spec


def _split(rng: random.Random, total: int, n: int) -> list[int]:
    if n == 1:
        return [total]
    unit = 500000
    units = total // unit
    cuts = sorted(rng.sample(range(1, units), n - 1))
    parts = [b - a for a, b in zip([0] + cuts, cuts + [units])]
    return [p * unit for p in parts]


def _plant_defects(rng: random.Random, spec: LoanSpec, scale: float) -> None:
    for t in spec.tranches:
        if t.mode in ("CHEQUE", "DD"):
            if rng.random() < 0.04 * scale:
                spec.handover[t.no] = []
                spec.defects.append((t.no, "MISSING_HANDOVER_ACK", "handover acknowledgement not recorded"))
            elif rng.random() < 0.02 * scale:
                shift = rng.choice([-3, -2, 2, 3, 4])
                spec.handover[t.no].append(t.mih + timedelta(days=shift))
                spec.defects.append((t.no, "DUPLICATE_HANDOVER_ACK", f"second ack {shift:+d} days from true date"))
        elif rng.random() < 0.03 * scale:
            spec.rail_credit[t.no] = None
            spec.defects.append((t.no, "MISSING_RAIL_CREDIT", "payment-rail credit not in extract"))
    if spec.kfs_basis == "ACT_365" and rng.random() < 0.005 * scale:
        spec.lms_basis = "30E_360"
        spec.defects.append((None, "UNRECOGNISED_DAY_COUNT", "LMS used 30E/360 although KFS discloses ACT/365"))


def simulate(spec: LoanSpec, book: Book, rng: random.Random, as_of: date) -> None:
    """Run the LMS month by month: post interest, collect receipts."""
    rates = [(spec.sanction_date, spec.rate)] + spec.rate_resets
    state = LoanState(spec.sanction_date, spec.agreement_date, spec.sanctioned, spec.tranches,
                      rates, spec.lms_basis, spec.fee_rate)
    truth_state = LoanState(spec.sanction_date, spec.agreement_date, spec.sanctioned, spec.tranches,
                            rates, spec.kfs_basis, spec.fee_rate, state.receipts)
    disbursed = sum(t.amount for t in spec.tranches)
    last_mih = max(t.mih for t in spec.tranches)
    emi_start = date(next_month(next_month(month_start(last_mih))).year,
                     next_month(next_month(month_start(last_mih))).month, 5)
    emi = emi_amount(disbursed, spec.rate, spec.tenure)
    advance_due = None
    principal_paid = 0
    if spec.advance_emi:
        advance_due = emi_start
        t1 = spec.tranches[0]
        state.receipts.append(Receipt(t1.mih, "ADVANCE_EMI", emi, emi_start))
        book.add("receipts", dict(receipt_id=f"R{spec.loan_id[1:]}A", loan_id=spec.loan_id,
                                  value_date=t1.mih, kind="ADVANCE_EMI", amount_paise=emi,
                                  principal_paise=emi, due_date=emi_start))
        principal_paid += emi
    closed = None
    ps = month_start(spec.sanction_date)
    seq = 0
    inst = 0
    while next_month(ps) <= as_of:
        pe = next_month(ps)
        conv = conv_for(spec.branch_id, spec.sanction_date, ps)
        if conv == CFEE and spec.fee_rate is None:
            conv = FAIR
        if spec.closure_date and ps <= spec.closure_date < pe:
            out = sum(t.amount for t in spec.tranches if t.mih <= spec.closure_date) - principal_paid
            state.receipts.append(Receipt(spec.closure_date, "CLOSURE", out))
            book.add("receipts", dict(receipt_id=f"R{spec.loan_id[1:]}C", loan_id=spec.loan_id,
                                      value_date=spec.closure_date, kind="CLOSURE",
                                      amount_paise=out, principal_paise=out, due_date=None))
            principal_paid += out
            closed = spec.closure_date
        posted = period_interest(state, conv, ps)
        fair = period_interest(truth_state, FAIR, ps)
        if posted > 0 or fair > 0:
            book.add("expected", dict(loan_id=spec.loan_id, period_start=ps, true_convention_id=conv,
                                      true_fair_paise=fair, true_posted_paise=posted))
        if posted > 0:
            seq += 1
            pid = f"P{spec.loan_id[1:]}{seq:03d}"
            if ps in spec.reversal_periods:
                wrong = posted + rng.randint(100, 50000)
                book.add("interest_postings", _posting(pid + "W", spec.loan_id, ps, wrong, pe, None, False))
                book.add("interest_postings", _posting(pid + "R", spec.loan_id, ps, -wrong, pe + timedelta(days=3), pid + "W", False))
                spec.defects.append((None, "REVERSED_REPOSTED", f"wrong posting reversed and re-posted for {ps.isoformat()}"))
            book.add("interest_postings", _posting(pid, spec.loan_id, ps, posted, pe, None, False))
            if ps in spec.manual_adj:
                book.add("interest_postings", _posting(pid + "M", spec.loan_id, ps, spec.manual_adj[ps],
                                                       pe + timedelta(days=5), None, True))
                spec.defects.append((None, "MANUAL_ADJUSTMENT", f"manual journal of {spec.manual_adj[ps]} paise on period {ps.isoformat()}"))
        if closed:
            break
        # receipts on the 5th of next month
        due = date(pe.year, pe.month, 5)
        if due >= as_of or posted == 0:
            ps = pe
            continue
        if due < emi_start:
            book.add("demands", dict(loan_id=spec.loan_id, due_date=due, instalment_no=None, kind="PRE_EMI", demand_paise=posted))
            book.add("receipts", dict(receipt_id=f"R{spec.loan_id[1:]}{seq:03d}", loan_id=spec.loan_id,
                                      value_date=due, kind="PRE_EMI", amount_paise=posted, principal_paise=0, due_date=due))
        elif due != advance_due:
            inst += 1
            outstanding = disbursed - principal_paid
            principal = min(max(emi - posted, 0), outstanding)
            vd = due + timedelta(days=spec.late_days.get(due, 0))
            kind = "CLOSURE" if principal == outstanding else "EMI"
            state.receipts.append(Receipt(vd, kind, principal))
            principal_paid += principal
            book.add("demands", dict(loan_id=spec.loan_id, due_date=due, instalment_no=inst, kind="EMI", demand_paise=emi))
            book.add("receipts", dict(receipt_id=f"R{spec.loan_id[1:]}{seq:03d}", loan_id=spec.loan_id,
                                      value_date=vd, kind=kind, amount_paise=principal + posted,
                                      principal_paise=principal, due_date=due))
            if kind == "CLOSURE":
                closed = vd
                spec.closure_date = vd
        ps = pe
        if closed and next_month(ps) <= as_of:
            # post the final (closure) period, then stop
            conv = conv_for(spec.branch_id, spec.sanction_date, ps)
            if conv == CFEE and spec.fee_rate is None:
                conv = FAIR
            posted = period_interest(state, conv, ps)
            fair = period_interest(truth_state, FAIR, ps)
            if posted > 0 or fair > 0:
                book.add("expected", dict(loan_id=spec.loan_id, period_start=ps, true_convention_id=conv,
                                          true_fair_paise=fair, true_posted_paise=posted))
            if posted > 0:
                seq += 1
                book.add("interest_postings", _posting(f"P{spec.loan_id[1:]}{seq:03d}", spec.loan_id, ps, posted, next_month(ps), None, False))
            break
    spec.closure_date = closed
    _write_static(spec, book, emi, emi_start)


def _posting(pid, loan_id, ps, amount, posted_on, rev, manual):
    return dict(posting_id=pid, loan_id=loan_id, period_start=ps, period_end=next_month(ps),
                posted_paise=amount, posted_on=posted_on, reverses_posting_id=rev, is_manual=manual)


def _write_static(spec: LoanSpec, book: Book, emi: int, emi_start: date) -> None:
    book.add("loans", dict(loan_id=spec.loan_id, borrower_id=spec.borrower_id, branch_id=spec.branch_id,
                           product=spec.product, sanction_date=spec.sanction_date,
                           agreement_date=spec.agreement_date, sanctioned_paise=spec.sanctioned,
                           tenure_months=spec.tenure, emi_start_date=emi_start,
                           status="CLOSED" if spec.closure_date else "ACTIVE", closed_date=spec.closure_date))
    book.add("kfs", dict(loan_id=spec.loan_id, issued_date=spec.sanction_date, annual_rate_pct=spec.rate,
                         day_count_basis=spec.kfs_basis, commitment_fee_rate_pct=spec.fee_rate,
                         broken_period_disclosed=True, disclosed_emi_paise=emi, disclosed_apr_pct=spec.rate))
    book.add("rate_history", dict(loan_id=spec.loan_id, effective_date=spec.sanction_date, annual_rate_pct=spec.rate))
    for d, r in spec.rate_resets:
        book.add("rate_history", dict(loan_id=spec.loan_id, effective_date=d, annual_rate_pct=r))
    payee = {"HOME": "BUILDER", "PERSONAL": "BORROWER"}[spec.product]
    for t in spec.tranches:
        book.add("kfs_disbursal_schedule", dict(loan_id=spec.loan_id, tranche_no=t.no,
                                                expected_date=t.mih, expected_paise=t.amount))
        book.add("tranches", dict(loan_id=spec.loan_id, tranche_no=t.no, amount_paise=t.amount,
                                  payment_mode=t.mode, payee_type=payee if t.no > 1 or spec.product == "PERSONAL" else ("SELLER" if len(spec.tranches) == 1 else "BUILDER")))
        ev = []
        ev.append(("LMS_DISB", spec.lms_disb[t.no], f"LMS{spec.loan_id[1:]}{t.no}", "LMS"))
        if t.cheque_date:
            ev.append(("CHEQUE_DATE", t.cheque_date, f"CHQ{spec.loan_id[1:]}{t.no}", "LMS"))
        for j, h in enumerate(spec.handover.get(t.no, [])):
            ev.append(("HANDOVER_ACK", h, f"ACK{spec.loan_id[1:]}{t.no}{j}", "BRANCH_REGISTER"))
        if spec.rail_credit.get(t.no):
            ev.append(("RAIL_CREDIT", spec.rail_credit[t.no], f"UTR{spec.loan_id[1:]}{t.no}", "PAYMENTS"))
        for j, (src, d, ref, rec) in enumerate(ev):
            book.add("disbursement_evidence", dict(evidence_id=f"E{spec.loan_id[1:]}{t.no}{j}", loan_id=spec.loan_id,
                                                   tranche_no=t.no, evidence_source=src, event_date=d, reference=ref, recorded_in=rec))
    for tranche_no, kind, detail in spec.defects:
        book.add("planted_defects", dict(defect_id=f"D{spec.loan_id[1:]}{book.counts['planted_defects']}",
                                         loan_id=spec.loan_id, tranche_no=tranche_no, kind=kind, detail=detail))


def demo_loans() -> list[tuple[LoanSpec, str, str]]:
    """Meena, Raghav and Asha, exactly as in docs/SPEC.md (synthetic)."""
    out = []
    # Meena: BR001, sanctioned before the July 2024 fix, so cheque-date posting continues
    meena = LoanSpec("LDM0001", "BDM0001", "BR001", "HOME", date(2024, 5, 20), date(2024, 5, 24),
                     450000000, 240, Decimal("8.75"), [
                         Tranche(1, 182500000, "NEFT", date(2024, 6, 10), None),
                         Tranche(2, 120000000, "CHEQUE", date(2025, 3, 11), date(2025, 3, 3)),
                     ])
    meena.lms_disb = {1: date(2024, 6, 10), 2: date(2025, 3, 3)}
    meena.rail_credit = {1: date(2024, 6, 10), 2: None}
    meena.handover = {2: [date(2025, 3, 11)]}
    out.append((meena, "Meena Iyer", "en"))
    # Raghav: BR008, KFS discloses a commitment fee at the loan rate; posting reproduces it
    raghav = LoanSpec("LDM0002", "BDM0002", "BR008", "HOME", date(2025, 1, 15), date(2025, 1, 20),
                      350000000, 240, Decimal("9.10"), [
                          Tranche(1, 350000000, "RTGS", date(2025, 2, 20), None),
                      ])
    raghav.lms_disb = {1: date(2025, 2, 20)}
    raghav.rail_credit = {1: date(2025, 2, 20)}
    raghav.fee_rate = Decimal("9.10")
    out.append((raghav, "Raghav Menon", "hi"))
    # Asha: BR002, cheque tranche with no handover record; cheque and rail credit 4 days apart
    asha = LoanSpec("LDM0003", "BDM0003", "BR002", "HOME", date(2025, 5, 12), date(2025, 5, 16),
                    280000000, 240, Decimal("8.90"), [
                        Tranche(1, 280000000, "CHEQUE", date(2025, 6, 5), date(2025, 6, 2)),
                    ])
    asha.lms_disb = {1: date(2025, 6, 2)}
    asha.rail_credit = {1: date(2025, 6, 6)}
    asha.handover = {1: []}
    asha.defects.append((1, "MISSING_HANDOVER_ACK", "handover acknowledgement not recorded"))
    out.append((asha, "Asha Kulkarni", "ta"))
    return out


TABLES_RAW = ["branches", "borrowers", "loans", "kfs", "kfs_disbursal_schedule", "rate_history", "tranches",
              "disbursement_evidence", "demands", "receipts", "interest_postings"]
TABLES_TRUTH = ["lms_config", "planted_defects", "expected"]


def fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def generate(seed: int, loans: int, as_of: date, defect_scale: float, out_root: Path) -> Path:
    rng = random.Random(seed)
    dataset_id = f"s{seed}_n{loans}"
    out = out_root / dataset_id
    book = Book(out)
    for b in BRANCHES:
        book.add("branches", dict(branch_id=b[0], branch_name=b[1], state_name=b[2], region=b[3]))
    specs: list[tuple[LoanSpec, str, str]] = demo_loans()
    for i in range(1, loans + 1):
        spec = make_bulk_loan(rng, i, as_of, defect_scale)
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        lang = rng.choices(["en", "hi", "ta"], [60, 30, 10])[0]
        specs.append((spec, name, lang))
    for spec, name, lang in specs:
        state = next(b[2] for b in BRANCHES if b[0] == spec.branch_id)
        book.add("borrowers", dict(borrower_id=spec.borrower_id, display_name=name, preferred_language=lang, state_name=state))
        if not spec.loan_id.startswith("LDM"):
            for k in range(36):
                if rng.random() < 0.10:
                    d = date(2023 + k // 12, k % 12 + 1, 5)
                    spec.late_days[d] = rng.randint(1, 6)
                if rng.random() < 0.003 * defect_scale:
                    spec.reversal_periods.add(date(2023 + (k + 6) // 12, (k + 6) % 12 + 1, 1))
            if rng.random() < 0.01 * defect_scale:
                ps = date(2025, rng.randint(1, 12), 1)
                spec.manual_adj[ps] = rng.choice([-1, 1]) * rng.randint(100, 50000)
        simulate(spec, book, rng, as_of)
    for b, vf, applies, conv in LMS_CONFIG:
        book.add("lms_config", dict(branch_id=b, valid_from=vf, valid_to=None, applies_to=applies, convention_id=conv))

    book.close()
    counts = dict(book.counts)
    manifest = dict(dataset_id=dataset_id, seed=seed, loans=loans + 3, bulk_loans=loans, as_of=as_of.isoformat(),
                    defect_scale=defect_scale, generator_version=GENERATOR_VERSION, row_counts=counts,
                    generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return out


COLUMNS = {
    "branches": ["branch_id", "branch_name", "state_name", "region"],
    "borrowers": ["borrower_id", "display_name", "preferred_language", "state_name"],
    "loans": ["loan_id", "borrower_id", "branch_id", "product", "sanction_date", "agreement_date",
              "sanctioned_paise", "tenure_months", "emi_start_date", "status", "closed_date"],
    "kfs": ["loan_id", "issued_date", "annual_rate_pct", "day_count_basis", "commitment_fee_rate_pct",
            "broken_period_disclosed", "disclosed_emi_paise", "disclosed_apr_pct"],
    "kfs_disbursal_schedule": ["loan_id", "tranche_no", "expected_date", "expected_paise"],
    "rate_history": ["loan_id", "effective_date", "annual_rate_pct"],
    "tranches": ["loan_id", "tranche_no", "amount_paise", "payment_mode", "payee_type"],
    "disbursement_evidence": ["evidence_id", "loan_id", "tranche_no", "evidence_source", "event_date", "reference", "recorded_in"],
    "demands": ["loan_id", "due_date", "instalment_no", "kind", "demand_paise"],
    "receipts": ["receipt_id", "loan_id", "value_date", "kind", "amount_paise", "principal_paise", "due_date"],
    "interest_postings": ["posting_id", "loan_id", "period_start", "period_end", "posted_paise", "posted_on",
                          "reverses_posting_id", "is_manual"],
    "lms_config": ["branch_id", "valid_from", "valid_to", "applies_to", "convention_id"],
    "planted_defects": ["defect_id", "loan_id", "tranche_no", "kind", "detail"],
    "expected": ["loan_id", "period_start", "true_convention_id", "true_fair_paise", "true_posted_paise"],
}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--loans", type=int, default=10000)
    p.add_argument("--as-of", default="2026-10-01", help="first day after the last billing period")
    p.add_argument("--defects", type=float, default=1.0, help="defect level: 0 none, 1 default, 3 heavy")
    p.add_argument("--out", default=str(ROOT / "data"))
    a = p.parse_args()
    out = generate(a.seed, a.loans, date.fromisoformat(a.as_of), a.defects, Path(a.out))
    print(json.loads((out / "manifest.json").read_text()))


if __name__ == "__main__":
    main()
