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
    "ta": {
        "P1": "பணம் உங்களுக்குக் கிடைப்பதற்கு முன்பே, அனுமதி அல்லது ஒப்பந்தத் தேதியிலிருந்து வசூலிக்கப்பட்ட வட்டி",
        "P2": "காசோலை பின்னர் ஒப்படைக்கப்பட்டிருந்தும், காசோலையில் அச்சிடப்பட்ட தேதியிலிருந்து வசூலிக்கப்பட்ட வட்டி",
        "P3": "மாதத்தின் நடுவில் பணம் வழங்கப்பட்டபோதும் முழு மாதத்திற்கும் வசூலிக்கப்பட்ட வட்டி",
        "P4": "முன்கூட்டிய தவணை செலுத்தப்பட்டிருந்தும் முழுத் தொகைக்கும் வசூலிக்கப்பட்ட வட்டி",
        "P5": "உண்மையில் வழங்கப்பட்ட தொகைக்குப் பதிலாக அனுமதிக்கப்பட்ட தொகைக்கு வசூலிக்கப்பட்ட வட்டி",
        "AMB": "பணம் உங்களுக்குக் கிடைப்பதற்கு முன் வசூலிக்கப்பட்ட வட்டி (சரியான முறையைத் தனியாகக் கண்டறிய முடியவில்லை)",
    },
}

TEMPLATES = {
    "en": """Dear {name},

Loan {loan_id} ({product} loan), {branch} branch

We have reviewed the interest charged on your loan. For some billing periods we charged interest for days
before the money actually reached you, or on an amount you did not yet have. This is not how interest should
be charged, and we are refunding the difference.

Amount we will refund: {{{{figure:TOTAL.excess}}}}
Billing periods affected: {{{{figure:TOTAL.periods}}}}, {span}

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
प्रभावित बिलिंग अवधियाँ: {{{{figure:TOTAL.periods}}}}, {span}

क्या हुआ:
{lines}

राशि आपके ऋण खाते में जमा की जाएगी। आपको कुछ करने की आवश्यकता नहीं है। प्रश्न हों तो {branch} शाखा से
संपर्क करें और संदर्भ {loan_id} बताएं।

इस पत्र की हर राशि ऑडिट लेजर से ली गई है और भेजने से पहले उससे मिलाई गई है।

भवदीय,
शिकायत निवारण अधिकारी
(कृत्रिम उदाहरण। कोई वास्तविक ऋणदाता, उधारकर्ता या ऋण नहीं।)
""",
    "ta": """அன்புள்ள {name},

கடன் {loan_id} ({product} கடன்), {branch} கிளை

உங்கள் கடனுக்கு வசூலிக்கப்பட்ட வட்டியை நாங்கள் மறுஆய்வு செய்தோம். சில பில்லிங் காலங்களில், பணம் உங்களைச்
சென்றடைவதற்கு முந்தைய நாட்களுக்கும், உங்களுக்கு இன்னும் கிடைக்காத தொகைக்கும் வட்டி வசூலித்தோம். அந்த
வேறுபாட்டை நாங்கள் திருப்பித் தருகிறோம்.

திருப்பித் தரப்படும் தொகை: {{{{figure:TOTAL.excess}}}}
பாதிக்கப்பட்ட பில்லிங் காலங்கள்: {{{{figure:TOTAL.periods}}}}, {span}

என்ன நடந்தது:
{lines}

இந்தத் தொகை உங்கள் கடன் கணக்கில் வரவு வைக்கப்படும். நீங்கள் எதுவும் செய்ய வேண்டியதில்லை. கேள்விகள் இருந்தால்,
{branch} கிளையைத் தொடர்புகொண்டு {loan_id} என்ற குறிப்பைக் குறிப்பிடவும்.

இந்தக் கடிதத்தில் உள்ள ஒவ்வொரு தொகையும் தணிக்கை லெட்ஜரிலிருந்து எடுக்கப்பட்டு, அனுப்பும் முன் அதனுடன்
சரிபார்க்கப்பட்டது.

தங்கள் உண்மையுள்ள,
குறை தீர்க்கும் அலுவலர்
(செயற்கை உதாரணம். உண்மையான கடன் வழங்குநர், கடன் பெற்றவர் அல்லது கடன் அல்ல.)
""",
}

def _reflow(text: str) -> str:
    """Join lines wrapped mid-sentence in the source so each paragraph is one line; keep labels, list items
    and the signature block on their own lines."""
    out: list[str] = []
    for line in text.split("\n"):
        prev = out[-1] if out else ""
        joinable = (prev and line and not line.startswith(("  -", "(")) and "{{{{figure" not in prev
                    and not prev.rstrip().endswith((".", ":", "।", ")"))
                    and not (prev.rstrip().endswith(",") and len(prev) < 30))  # salutation, sign-off
        if joinable:
            out[-1] = prev.rstrip() + " " + line.lstrip()
        else:
            out.append(line)
    return "\n".join(out)


TEMPLATES = {k: _reflow(v) for k, v in TEMPLATES.items()}

# (one month, a range of months)
SPAN = {"en": ("in {first}", "from {first} to {last}"), "hi": ("{first} में", "{first} से {last} तक"),
        "ta": ("{first} இல்", "{first} முதல் {last} வரை")}

LINE = {
    "en": "  - {text}: {{{{figure:{key}.excess}}}} over {{{{figure:{key}.days}}}} days",
    "hi": "  - {text}: {{{{figure:{key}.excess}}}}, {{{{figure:{key}.days}}}} दिन",
    "ta": "  - {text}: {{{{figure:{key}.excess}}}}, {{{{figure:{key}.days}}}} நாட்கள்",
}

PRODUCT = {"en": {"HOME": "home", "PERSONAL": "personal", "LAP": "loan against property"},
           "hi": {"HOME": "गृह", "PERSONAL": "व्यक्तिगत", "LAP": "संपत्ति के बदले"},
           "ta": {"HOME": "வீட்டுக்", "PERSONAL": "தனிநபர்", "LAP": "சொத்து அடமானக்"}}


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


def _cap(t: str) -> str:
    return t[:1].upper() + t[1:]


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
    lines = "\n".join(LINE[lang].format(text=_cap(PRACTICE_TEXT[lang].get(k, k)), key=k)
                      for k in sorted(by_key) if k != "TOTAL")
    first, last = month_name(total["first_period"]), month_name(total["last_period"])
    span = SPAN[lang][0 if first == last else 1].format(first=first, last=last)
    body = TEMPLATES[lang].format(name=total["display_name"], loan_id=total["loan_id"],
                                  product=PRODUCT[lang].get(total["product"], total["product"]),
                                  branch=total["branch_name"], span=span, lines=lines)
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
