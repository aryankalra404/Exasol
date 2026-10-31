"""The letter checker must pass a faithful letter and reject any tampered figure."""

from dataclasses import replace
from datetime import date

from letters.letter import check, inr, render

ROWS = [
    {"loan_id": "LDM0001", "borrower_id": "BDM0001", "display_name": "Meena Iyer", "preferred_language": "en",
     "product": "HOME", "branch_name": "Pune Kothrud", "line_key": "P2", "periods": 1, "days_affected": 8,
     "excess_paise": 230137, "first_period": date(2025, 3, 1), "last_period": date(2025, 3, 1)},
    {"loan_id": "LDM0001", "borrower_id": "BDM0001", "display_name": "Meena Iyer", "preferred_language": "en",
     "product": "HOME", "branch_name": "Pune Kothrud", "line_key": "TOTAL", "periods": 1, "days_affected": 8,
     "excess_paise": 230137, "first_period": date(2025, 3, 1), "last_period": date(2025, 3, 1)},
]


def test_inr_indian_grouping():
    assert inr(230137) == "₹2,301.37"
    assert inr(120000000) == "₹12,00,000.00"
    assert inr(5) == "₹0.05"
    assert inr(-1712206217) == "-₹1,71,22,062.17"


def test_faithful_letter_passes():
    for lang in ("en", "hi", "ta"):
        letter = render(ROWS, lang)
        assert "₹2,301.37" in letter.text
        assert check(letter, ROWS)["ok"]


def test_tamil_letter_is_tamil_and_checked():
    letter = render(ROWS, "ta")
    assert letter.lang == "ta" and "அன்புள்ள Meena Iyer" in letter.text and "8 நாட்கள்" in letter.text
    bad = replace(letter, text=letter.text.replace("₹2,301.37", "₹2,301.73", 1))
    assert check(letter, ROWS)["ok"] and not check(bad, ROWS)["ok"]


def test_tampered_amount_is_rejected():
    letter = render(ROWS, "en")
    bad = replace(letter, text=letter.text.replace("₹2,301.37", "₹2,310.37", 1))
    result = check(bad, ROWS)
    assert not result["ok"]


def test_stray_amount_is_rejected():
    letter = render(ROWS, "en")
    bad = replace(letter, text=letter.text + "\nGoodwill credit: ₹500.00\n")
    result = check(bad, ROWS)
    assert not result["ok"] and result["stray_amounts"] == ["₹500.00"]


def test_ledger_changed_after_render_is_rejected():
    letter = render(ROWS, "en")
    changed = [dict(r, excess_paise=230136) for r in ROWS]
    assert not check(letter, changed)["ok"]
