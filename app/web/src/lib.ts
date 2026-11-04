import { useEffect, useState } from "react";

// ---------- data ----------
export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api${path}`, init);
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail ?? msg; } catch { /* keep status text */ }
    throw new Error(msg);
  }
  return r.json();
}

export function useApi<T = any>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!path) return;
    let live = true;
    setLoading(true);
    setError(null);
    api<T>(path)
      .then((d) => live && setData(d))
      .catch((e) => live && setError(String(e.message ?? e)))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  return { data, error, loading, setData };
}

export const post = <T = any>(path: string, body: unknown) =>
  api<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

/** The reviewer's self-declared name, remembered in this browser. */
export function useReviewer(): [string, (v: string) => void] {
  const [name, setName] = useState(() => {
    try { return localStorage.getItem("reviewer") ?? ""; } catch { return ""; }
  });
  return [name, (v: string) => {
    setName(v);
    try { localStorage.setItem("reviewer", v); } catch { /* private mode */ }
  }];
}

// ---------- routing (hash based, so the static build works from any path) ----------
export function useRoute() {
  const [hash, setHash] = useState(window.location.hash || "#/book");
  useEffect(() => {
    const on = () => { setHash(window.location.hash || "#/book"); };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const [path, query = ""] = hash.slice(1).split("?");
  const parts = path.split("/").filter(Boolean);
  return { parts, params: new URLSearchParams(query) };
}

export function go(to: string) {
  window.location.hash = to;
}

// ---------- formatting (display only: no figures are computed here) ----------
/** Indian digit grouping for integer paise, using string operations only. */
export function inr(paise: number | string | null | undefined, opts: { paise?: boolean } = {}): string {
  if (paise === null || paise === undefined || paise === "") return "-";
  let s = String(paise);
  const neg = s.startsWith("-");
  if (neg) s = s.slice(1);
  s = s.padStart(3, "0");
  const rupees = s.slice(0, -2).replace(/^0+(?=\d)/, "");
  const p = s.slice(-2);
  let head = rupees.slice(0, -3);
  const tail = rupees.slice(-3);
  const groups: string[] = [];
  while (head.length > 2) { groups.unshift(head.slice(-2)); head = head.slice(0, -2); }
  if (head) groups.unshift(head);
  const whole = groups.length ? `${groups.join(",")},${tail}` : tail;
  return `${neg ? "-" : ""}₹${whole}${opts.paise === false ? "" : "." + p}`;
}

/** Exact decimal paise string (e.g. "230136.9863") shown as rupees with 4 decimals of a paisa kept. */
export function inrExact(v: string | number): string {
  const s = String(v);
  const [i, f = ""] = s.split(".");
  return `${inr(i)}${f ? `<span class="faint">${f.replace(/0+$/, "")}</span>` : ""}`;
}

export function n(v: number | string | null | undefined): string {
  if (v === null || v === undefined) return "-";
  const s = String(v);
  return s.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function month(d: string | null | undefined): string {
  if (!d) return "-";
  const [y, m] = d.split("-");
  return `${MONTHS[Number(m) - 1]} ${y}`;
}
export function day(d: string | null | undefined): string {
  if (!d) return "-";
  const [y, m, dd] = d.slice(0, 10).split("-");
  return `${Number(dd)} ${MONTHS[Number(m) - 1]} ${y}`;
}
export function seconds(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "-";
  const s = String(Math.round(Number(ms)));
  return s.length > 3 ? `${s.slice(0, -3)}.${s.slice(-3, -2)} s` : `${s} ms`;
}

// ---------- domain words ----------
export const PRACTICE: Record<string, string> = {
  P1: "Interest from sanction or agreement date",
  P2: "Interest from the cheque date, cheque handed over later",
  P3: "Full-month interest on a mid-month disbursal or repayment",
  P4: "Interest on the full amount despite an advance instalment",
  P5: "Interest on the sanctioned instead of the disbursed amount",
  P6: "Amortisation change not communicated",
  AMB: "Practice not uniquely identifiable",
};

export function describeConvention(id: string | null | undefined): string {
  if (!id) return "-";
  if (id === "CFEE") return "Fair interest plus the disclosed commitment fee on the undisbursed amount";
  const [s, p, a, m] = id.split("|");
  if (s === "MIH" && p === "DIS" && a === "NET" && m === "EXACT") return "Fair: from the day money reached the borrower, on the disbursed balance";
  const bits: string[] = [];
  bits.push({ MIH: "from the money-in-hand date", CHQ: "from the cheque date", SNC: "from the sanction date", AGR: "from the agreement date" }[s] ?? s);
  if (p === "SAN") bits.push("on the full sanctioned amount");
  if (a === "IGN") bits.push("advance EMI not netted until its due date");
  if (m === "FULL") bits.push("rounded out to whole months");
  const t = bits.join(", ");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export const STATUS_WORDS: Record<string, string> = {
  FAIR: "Fair",
  REFUND: "Refund",
  MATCHED: "Refund",
  AMBIGUOUS: "Ambiguous",
  PERMITTED: "Permitted",
  EVIDENCE_GAP: "Evidence gap",
  UNEXPLAINED: "Unexplained",
  UNDERCHARGE: "Undercharge",
};

export const REVIEW_WORDS: Record<string, string> = {
  UNREVIEWED: "Not reviewed",
  APPROVED: "Approved",
  HOLD: "On hold",
  STALE: "Needs re-review",
  CLEARED: "Cleared, no refund",
};

export const LETTER_WORDS: Record<string, string> = { DRAFT: "Draft", APPROVED: "Approved", RELEASED: "Released" };

export const SOURCE_WORDS: Record<string, string> = {
  SANCTION: "Sanction",
  AGREEMENT: "Agreement",
  LMS_DISB: "LMS disbursal",
  CHEQUE_DATE: "Cheque date",
  HANDOVER_ACK: "Handover receipt",
  RAIL_CREDIT: "Rail credit",
};

/** Long form for sentences: "handover acknowledgement", "payment-rail credit". */
export const SOURCE_LONG: Record<string, string> = {
  LMS_DISB: "loan-system disbursal date",
  CHEQUE_DATE: "cheque date",
  HANDOVER_ACK: "handover acknowledgement",
  RAIL_CREDIT: "payment-rail credit",
};
export const sources = (codes: string | null | undefined) =>
  String(codes ?? "").split(",").filter(Boolean).map((c) => SOURCE_LONG[c.trim()] ?? c.trim().toLowerCase().replace(/_/g, " ")).join(", ");

export const MODE_WORDS: Record<string, string> = { CHEQUE: "Cheque", DD: "Demand draft", NEFT: "NEFT", RTGS: "RTGS", IMPS: "IMPS" };
export const CONFIDENCE_WORDS: Record<string, string> = { CONFIRMED: "Confirmed", FALLBACK: "Fallback date", GAP: "Cannot decide" };
export const DAYCOUNT_WORDS: Record<string, string> = { ACT_365: "Actual/365", "30E_360": "30E/360" };
export const LOAN_STATUS_WORDS: Record<string, string> = { ACTIVE: "Active", CLOSED: "Closed" };

/** "1 month" / "2 months". */
export function plural(count: number | string, one: string, many = `${one}s`): string {
  return `${n(count)} ${Number(count) === 1 ? one : many}`;
}

/** Capitalise the first letter of a sentence stored in lower case (step descriptions). */
export const sentence = (s: string | null | undefined) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");
