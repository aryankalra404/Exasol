"""Simulated loan management system (LMS).

This is the system under audit. It posts monthly interest under whichever
convention its hidden configuration says. It is test-fixture code: the audit
pipeline never imports it and never reads its configuration.

Convention semantics follow docs/DOMAIN.md, "Conventions" and "Principal path".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

FAIR = "MIH|DIS|NET|EXACT"
CFEE = "CFEE"


def month_start(d: date) -> date:
    return d.replace(day=1)


def next_month(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def snap_forward(d: date) -> date:
    return d if d.day == 1 else next_month(d)


def days_30e(a: date, b: date) -> int:
    def f(x: date) -> int:
        return 360 * x.year + 30 * x.month + min(x.day, 30)

    return f(b) - f(a)


@dataclass
class Tranche:
    no: int
    amount: int
    mode: str
    mih: date  # true money-in-hand date
    cheque_date: date | None


@dataclass
class Receipt:
    value_date: date
    kind: str
    principal: int
    due_date: date | None = None


@dataclass
class LoanState:
    sanction_date: date
    agreement_date: date
    sanctioned: int
    tranches: list[Tranche]
    rates: list[tuple[date, Decimal]]  # sorted by effective date
    basis: str  # ACT_365 or 30E_360 (what the LMS actually uses)
    fee_rate: Decimal | None
    receipts: list[Receipt] = field(default_factory=list)


def _parse(conv: str) -> tuple[str, str, str, str]:
    if conv == CFEE:
        return ("MIH", "DIS", "NET", "EXACT")
    sb, pb, adv, mr = conv.split("|")
    return sb, pb, adv, mr


def events(loan: LoanState, conv: str) -> list[tuple[date, int, int]]:
    """Balance events (date, principal delta, fee-balance delta) for a convention."""
    sb, pb, adv, mr = _parse(conv)
    out: list[tuple[date, int, int]] = []
    starts = []
    for t in loan.tranches:
        if sb == "CHQ" and t.mode in ("CHEQUE", "DD") and t.cheque_date:
            s = t.cheque_date
        elif sb == "SNC" and t.no == 1:
            s = loan.sanction_date
        elif sb == "AGR" and t.no == 1:
            s = loan.agreement_date
        else:
            s = t.mih
        if mr == "FULL":
            s = month_start(s)
        starts.append(s)
    disbursed = sum(t.amount for t in loan.tranches)
    if pb == "SAN":
        out.append((starts[0], loan.sanctioned, 0))
    else:
        for t, s in zip(loan.tranches, starts):
            out.append((s, t.amount, 0))
    closure = None
    for r in loan.receipts:
        if r.principal == 0:
            continue
        d = r.value_date
        if r.kind == "ADVANCE_EMI" and adv == "IGN" and r.due_date:
            d = r.due_date
        if r.kind == "CLOSURE":
            closure = r.value_date
            if mr == "FULL":
                d = snap_forward(d)
        out.append((d, -r.principal, 0))
    if pb == "SAN" and closure is not None:
        d = snap_forward(closure) if mr == "FULL" else closure
        out.append((d, -(loan.sanctioned - disbursed), 0))
    if conv == CFEE and loan.fee_rate is not None:
        out.append((loan.sanction_date, 0, loan.sanctioned))
        for t in loan.tranches:
            out.append((t.mih, 0, -t.amount))
        if closure is not None:
            out.append((closure, 0, -(loan.sanctioned - disbursed)))
    return out


def period_interest(loan: LoanState, conv: str, ps: date) -> int:
    """Interest in paise for billing period [ps, next month), rounded half up once."""
    pe = next_month(ps)
    evs = events(loan, conv)
    cuts = {ps, pe}
    for d, _, _ in evs:
        if ps < d < pe:
            cuts.add(d)
    for d, _ in loan.rates:
        if ps < d < pe:
            cuts.add(d)
    pts = sorted(cuts)
    fee_rate = loan.fee_rate or Decimal(0)
    divisor = 365 if loan.basis == "ACT_365" else 360
    total = Decimal(0)
    for a, b in zip(pts, pts[1:]):
        bal = sum(dp for d, dp, _ in evs if d <= a)
        fee = sum(df for d, _, df in evs if d <= a)
        rate = next(r for d, r in reversed(loan.rates) if d <= a) if loan.rates[0][0] <= a else loan.rates[0][1]
        days = (b - a).days if loan.basis == "ACT_365" else days_30e(a, b)
        total += (Decimal(bal) * rate + Decimal(fee) * fee_rate) / 100 * days / divisor
    return int(total.quantize(Decimal(1), rounding=ROUND_HALF_UP))
