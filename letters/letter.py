"""Borrower refund letters and the number checker.

Every figure in a letter comes from {OUT}.letter_figures (computed by SQL in Exasol). The template marks each
figure as {{figure:<key>}}; rendering substitutes the formatted ledger value. The checker then reads the
rendered text back, finds every rupee amount and every count it contains, re-reads the ledger independently,
and fails the letter if any figure differs or if any amount appears that the ledger does not hold.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

PRACTICE_TEXT = {
    "en": {
        "P1": "interest charged from the sanction or agreement date, before the money reached you",
        "P2": "interest charged from the date printed on a cheque that was handed over later",
        "P3": "interest charged for a full month when the money moved mid-month",
        "P4": "interest charged on the full amount although an advance instalment had been paid",
        "P5": "interest charged on the sanctioned amount instead of the amount actually disbursed",
        "AMB": "interest charged before the money reached you (the exact method could not be told apart)",
    },
    "hi": {
        "P1": "राशि मिलने से पहले, स्वीकृति या अनुबंध की तारीख से ब्याज",
        "P2": "चेक पर छपी तारीख से ब्याज, जबकि चेक बाद में सौंपा गया",
        "P3": "महीने के बीच में राशि मिलने पर पूरे महीने का ब्याज",
        "P4": "अग्रिम किस्त जमा होने के बावजूद पूरी राशि पर ब्याज",
        "P5": "वितरित राशि के बजाय स्वीकृत राशि पर ब्याज",
        "AMB": "राशि मिलने से पहले का ब्याज (सटीक तरीका अलग से पहचाना नहीं जा सका)",
    },
}

TEMPLATES = {
    "en": """Dear {name},

Loan {loan_id} ({product} loan), {branch} branch

We have reviewed the interest charged on your loan. For some billing periods we charged interest for days
before the money actually reached you, or on an amount you did not yet have. This is not how interest should
be charged, and we are refunding the difference.

Amount we will refund: {{{{figure:TOTAL.excess}}}}
Billing periods affected: {{{{figure:TOTAL.periods}}}}, from {first} to {last}

What happened:
{lines}

The refund will be credited to your loan account. You do not need to do anything. If you have questions,
please contact the {branch} branch and quote reference {loan_id}.

This letter was prepared from our interest audit. Every amount in it is taken from the audit ledger and was
checked against it before sending.

Yours sincerely,
Grievance Redressal Officer
(Synthetic example. Not a real lender, borrower or loan.)
""",
    "hi": """प्रिय {name},

ऋण {loan_id} ({product} ऋण), {branch} शाखा

हमने आपके ऋण पर लगाए गए ब्याज की समीक्षा की है। कुछ बिलिंग अवधियों में हमने उन दिनों का ब्याज लिया जब राशि
आप तक पहुँची ही नहीं थी, या ऐसी राशि पर ब्याज लिया जो आपको अभी मिली नहीं थी। यह अंतर हम लौटा रहे हैं।

वापसी की राशि: {{{{figure:TOTAL.excess}}}}
प्रभावित बिलिंग अवधियाँ: {{{{figure:TOTAL.periods}}}}, {first} से {last} तक

क्या हुआ:
{lines}

राशि आपके ऋण खाते में जमा की जाएगी। आपको कुछ करने की आवश्यकता नहीं है। प्रश्न हों तो {branch} शाखा से
संपर्क करें और संदर्भ {loan_id} बताएं।

इस पत्र की हर राशि ऑडिट लेजर से ली गई है और भेजने से पहले उससे मिलाई गई है।

भवदीय,
शिकायत निवारण अधिकारी
(कृत्रिम उदाहरण। कोई वास्तविक ऋणदाता, उधारकर्ता या ऋण नहीं।)
""",
}

LINE = {
    "en": "  - {text}: {{{{figure:{key}.excess}}}} over {{{{figure:{key}.days}}}} days",
    "hi": "  - {text}: {{{{figure:{key}.excess}}}}, {{{{figure:{key}.days}}}} दिन",
}

PRODUCT = {"en": {"HOME": "home", "PERSONAL": "personal", "LAP": "loan against property"},
           "hi": {"HOME": "गृह", "PERSONAL": "व्यक्तिगत", "LAP": "संपत्ति के बदले"}}


def inr(paise: int) -> str:
    """Indian grouping: 1230137 paise -> Rs 12,301.37."""
    neg = paise < 0
    rupees, p = divmod(abs(int(paise)), 100)
    s = str(rupees)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return f"{'-' if neg else ''}₹{s}.{p:02d}"


def month_name(d: date) -> str:
    return d.strftime("%b %Y")


@dataclass
class Letter:
    loan_id: str
    lang: str
    text: str
    figures: dict[str, str] = field(default_factory=dict)  # key -> rendered string


def render(rows: list[dict], lang: str = "en") -> Letter:
    """rows: letter_figures rows for one loan (one per practice plus TOTAL)."""
    lang = lang if lang in TEMPLATES else "en"
    by_key = {r["line_key"]: r for r in rows}
    total = by_key["TOTAL"]
    values: dict[str, str] = {}
    for key, r in by_key.items():
        values[f"{key}.excess"] = inr(int(r["excess_paise"]))
        values[f"{key}.days"] = str(int(r["days_affected"]))
        values[f"{key}.periods"] = str(int(r["periods"]))
    lines = "\n".join(LINE[lang].format(text=PRACTICE_TEXT[lang].get(k, k), key=k)
                      for k in sorted(by_key) if k != "TOTAL")
    body = TEMPLATES[lang].format(name=total["display_name"], loan_id=total["loan_id"],
                                  product=PRODUCT[lang].get(total["product"], total["product"]),
                                  branch=total["branch_name"], first=month_name(total["first_period"]),
                                  last=month_name(total["last_period"]), lines=lines)
    used: dict[str, str] = {}

    def sub(m: re.Match) -> str:
        key = m.group(1)
        used[key] = values[key]
        return values[key]

    text = re.sub(r"\{\{figure:([A-Z0-9]+\.[a-z]+)\}\}", sub, body)
    return Letter(total["loan_id"], lang, text, used)


AMOUNT_RE = re.compile(r"-?₹[0-9,]+\.[0-9]{2}")


def check(letter: Letter, ledger_rows: list[dict]) -> dict:
    """Re-read the rendered letter against ledger rows fetched independently of rendering."""
    ledger = {r["line_key"]: r for r in ledger_rows}
    results = []
    ok = True
    for key, shown in letter.figures.items():
        line, kind = key.split(".")
        row = ledger.get(line)
        if row is None:
            results.append({"figure": key, "shown": shown, "ledger": None, "ok": False})
            ok = False
            continue
        col = {"excess": "excess_paise", "days": "days_affected", "periods": "periods"}[kind]
        expected = inr(int(row[col])) if kind == "excess" else str(int(row[col]))
        good = shown == expected and shown in letter.text
        ok &= good
        results.append({"figure": key, "shown": shown, "ledger": expected, "ok": good})
    allowed = {v for k, v in letter.figures.items() if k.endswith(".excess")}
    stray = [a for a in AMOUNT_RE.findall(letter.text) if a not in allowed]
    if stray:
        ok = False
    # the practice lines must add up to the total, to the paisa, as the ledger says
    parts = sum(int(r["excess_paise"]) for k, r in ledger.items() if k != "TOTAL")
    sums = parts == int(ledger["TOTAL"]["excess_paise"])
    ok &= sums
    return {"ok": ok, "figures": results, "stray_amounts": stray, "lines_sum_to_total": sums}
