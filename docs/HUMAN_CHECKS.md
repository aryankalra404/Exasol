# Human checks

Checks software cannot do for us. Fill in each result here and only claim what is recorded. All names and figures below are synthetic.

Priority for the finale: 1 and 2 first, then a person for the blind red team (`RED_TEAM.md`). The machine-written round does not replace them. If one is not done, say so if asked; `LIMITS.md` already does.

## 1. Letter wording (native speakers of Hindi and Tamil)

About 15 minutes per language. Figures are checked by software, so read for meaning and tone.

Ask the reader:

- Is any sentence wrong, unclear or awkward for a borrower with no finance background?
- Does it sound like a formal letter from a lender?
- Does "refund", "billing period" and "credited to your loan account" read correctly?
- Would you know what happened and what to do next?

| Language | Reader | Date | Result | Changes to make |
|---|---|---|---|---|
| Hindi | | | | |
| Tamil | | | | |

Edit wording in `letters/letter.py`, then run `make test`. If nobody checks a language, keep the `LIMITS.md` line and consider showing only the checked languages live.

### Hindi sample

```text
प्रिय Meena Iyer,

ऋण LDM0001 (गृह ऋण), Pune Kothrud शाखा

हमने आपके ऋण पर लगाए गए ब्याज की समीक्षा की है। कुछ बिलिंग अवधियों में हमने उन दिनों का ब्याज लिया जब राशि आप तक पहुँची ही नहीं थी, या ऐसी राशि पर ब्याज लिया जो आपको अभी मिली नहीं थी। यह अंतर हम लौटा रहे हैं।

वापसी की राशि: ₹2,301.37
प्रभावित बिलिंग अवधियाँ: 1, Mar 2025 में

क्या हुआ:
  - चेक पर छपी तारीख से ब्याज, जबकि चेक बाद में सौंपा गया: ₹2,301.37, 8 दिन

राशि आपके ऋण खाते में जमा की जाएगी। आपको कुछ करने की आवश्यकता नहीं है। प्रश्न हों तो Pune Kothrud शाखा से संपर्क करें और संदर्भ LDM0001 बताएं।

इस पत्र की हर राशि ऑडिट लेजर से ली गई है और भेजने से पहले उससे मिलाई गई है।

भवदीय,
शिकायत निवारण अधिकारी
(कृत्रिम उदाहरण। कोई वास्तविक ऋणदाता, उधारकर्ता या ऋण नहीं।)
```

### Tamil sample

```text
அன்புள்ள Meena Iyer,

கடன் LDM0001 (வீட்டுக் கடன்), Pune Kothrud கிளை

உங்கள் கடனுக்கு வசூலிக்கப்பட்ட வட்டியை நாங்கள் மறுஆய்வு செய்தோம். சில பில்லிங் காலங்களில், பணம் உங்களைச் சென்றடைவதற்கு முந்தைய நாட்களுக்கும், உங்களுக்கு இன்னும் கிடைக்காத தொகைக்கும் வட்டி வசூலித்தோம். அந்த வேறுபாட்டை நாங்கள் திருப்பித் தருகிறோம்.

திருப்பித் தரப்படும் தொகை: ₹2,301.37
பாதிக்கப்பட்ட பில்லிங் காலங்கள்: 1, Mar 2025 இல்

என்ன நடந்தது:
  - காசோலை பின்னர் ஒப்படைக்கப்பட்டிருந்தும், காசோலையில் அச்சிடப்பட்ட தேதியிலிருந்து வசூலிக்கப்பட்ட வட்டி: ₹2,301.37, 8 நாட்கள்

இந்தத் தொகை உங்கள் கடன் கணக்கில் வரவு வைக்கப்படும். நீங்கள் எதுவும் செய்ய வேண்டியதில்லை. கேள்விகள் இருந்தால், Pune Kothrud கிளையைத் தொடர்புகொண்டு LDM0001 என்ற குறிப்பைக் குறிப்பிடவும்.

இந்தக் கடிதத்தில் உள்ள ஒவ்வொரு தொகையும் தணிக்கை லெட்ஜரிலிருந்து எடுக்கப்பட்டு, அனுப்பும் முன் அதனுடன் சரிபார்க்கப்பட்டது.

தங்கள் உண்மையுள்ள,
குறை தீர்க்கும் அலுவலர்
(செயற்கை உதாரணம். உண்மையான கடன் வழங்குநர், கடன் பெற்றவர் அல்லது கடன் அல்ல.)
```

### Reason lines (only one appears in the sample above)

| Code | English | Hindi |
|---|---|---|
| P1 | interest charged from the sanction or agreement date, before the money reached you | राशि मिलने से पहले, स्वीकृति या अनुबंध की तारीख से ब्याज |
| P2 | interest charged from the date printed on a cheque that was handed over later | चेक पर छपी तारीख से ब्याज, जबकि चेक बाद में सौंपा गया |
| P3 | interest charged for a full month when the money moved mid-month | महीने के बीच में राशि मिलने पर पूरे महीने का ब्याज |
| P4 | interest charged on the full amount although an advance instalment had been paid | अग्रिम किस्त जमा होने के बावजूद पूरी राशि पर ब्याज |
| P5 | interest charged on the sanctioned amount instead of the amount actually disbursed | वितरित राशि के बजाय स्वीकृत राशि पर ब्याज |
| AMB | interest charged before the money reached you (the exact method could not be told apart) | राशि मिलने से पहले का ब्याज (सटीक तरीका अलग से पहचाना नहीं जा सका) |

| Code | English | Tamil |
|---|---|---|
| P1 | interest charged from the sanction or agreement date, before the money reached you | பணம் உங்களுக்குக் கிடைப்பதற்கு முன்பே, அனுமதி அல்லது ஒப்பந்தத் தேதியிலிருந்து வசூலிக்கப்பட்ட வட்டி |
| P2 | interest charged from the date printed on a cheque that was handed over later | காசோலை பின்னர் ஒப்படைக்கப்பட்டிருந்தும், காசோலையில் அச்சிடப்பட்ட தேதியிலிருந்து வசூலிக்கப்பட்ட வட்டி |
| P3 | interest charged for a full month when the money moved mid-month | மாதத்தின் நடுவில் பணம் வழங்கப்பட்டபோதும் முழு மாதத்திற்கும் வசூலிக்கப்பட்ட வட்டி |
| P4 | interest charged on the full amount although an advance instalment had been paid | முன்கூட்டிய தவணை செலுத்தப்பட்டிருந்தும் முழுத் தொகைக்கும் வசூலிக்கப்பட்ட வட்டி |
| P5 | interest charged on the sanctioned amount instead of the amount actually disbursed | உண்மையில் வழங்கப்பட்ட தொகைக்குப் பதிலாக அனுமதிக்கப்பட்ட தொகைக்கு வசூலிக்கப்பட்ட வட்டி |
| AMB | interest charged before the money reached you (the exact method could not be told apart) | பணம் உங்களுக்குக் கிடைப்பதற்கு முன் வசூலிக்கப்பட்ட வட்டி (சரியான முறையைத் தனியாகக் கண்டறிய முடியவில்லை) |

## 2. Oracle independence (a teammate who did not write the SQL)

Why: `STATUS.md` lists one owner for both the SQL and the oracle. A juror may ask how independent it really is.

- [ ] Read `DOMAIN.md`, then `oracle/oracle.py`, without reading `sql/`
- [ ] Confirm `oracle/` imports nothing from `sql/` and shares no logic
- [ ] Hand-calculate Meena: 12,00,000 x 8.75% x 8 / 365, half up to the paisa
- [ ] Hand-calculate one more month from another loan, and compare with the oracle
- [ ] Try to find a rule in `DOMAIN.md` the oracle gets wrong
- [ ] Run `make oracle LOANS=10000` and read the result yourself

| Reviewer | Date | Result | Problems found |
|---|---|---|---|
| | | | |

Record the outcome in `STATUS.md`. Say honestly how far it goes: a review after the fact is not the same as being written separately.

## 3. Auditor conversation (15 minutes, a practising internal or statutory auditor)

Why: "they sample" is an unvalidated assumption in `LIMITS.md`. Do not name the person or firm without permission.

1. How do you test interest charging on a loan book today? Sample, full recompute, or the system's own reports?
2. Where do disbursement dates come from, and how often do they disagree?
3. Who signs off before a refund goes out? Does approve and hold match that?
4. What would you need to see before trusting a tool's refund figure?
5. What would stop you using this?

| Who (role only) | Date | What we assumed that was wrong | What to change or say |
|---|---|---|---|
| | | | |

Quote only what was said, and as one person's view, not as how auditors work in general.

## 4. RBI primary text (someone on the team)

Why: we verified the 31 Jul 2026 directions for the RRB text and read the NBFC, co-op and commercial bank versions through summaries (`LIMITS.md`). The pitch is about housing finance lenders.

- [ ] Read the primary text that applies to NBFCs and HFCs on rbi.org.in
- [ ] Confirm the P5 and P6 wording in `DOMAIN.md` and `sql/05_policy_and_out_schema.sql`
- [ ] Note the exact title and date, and correct `LIMITS.md`

| Reader | Date | Document | Result |
|---|---|---|---|
| | | | |
