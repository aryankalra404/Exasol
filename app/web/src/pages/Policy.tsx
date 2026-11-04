import { useState } from "react";
import type { Run } from "../App";
import { api, day, inr, MODE_WORDS, n, PRACTICE, seconds, SOURCE_WORDS, useApi, useReviewer } from "../lib";
import { LivePanel } from "./Live";
import { ActorFields } from "./Review";

const HELP: Record<string, string> = {
  commitment_fee_permitted_if_disclosed: "If on, a fee from the sanction date that the Key Facts Statement disclosed is listed as permitted, not refunded.",
  include_ambiguous_in_refund_total: "The excess is certain but more than one practice explains it. If on, it is counted in the refund total.",
  allow_lms_fallback_electronic: "For NEFT, RTGS and IMPS with no payment-rail record, use the loan system's date instead of holding the tranche as a gap.",
  conflict_tolerance_days: "Evidence dates further apart than this from the resolved date are flagged as a conflict.",
  match_tolerance_paise: "A convention counts as reproducing a posting if it is within this many paise. 0 means exact.",
};

const SHORT_OFF: Record<string, string> = {
  commitment_fee_permitted_if_disclosed: "commitment fee not permitted",
  include_ambiguous_in_refund_total: "ambiguous excluded",
  allow_lms_fallback_electronic: "no LMS fallback",
};

const NICE: Record<string, string> = {
  commitment_fee_permitted_if_disclosed: "Commitment fee from sanction is permitted when the KFS discloses it",
  include_ambiguous_in_refund_total: "Count ambiguous findings in the refund total",
  allow_lms_fallback_electronic: "Accept the LMS date for electronic transfers with no rail credit record",
  conflict_tolerance_days: "Conflict tolerance (days)",
  match_tolerance_paise: "Match tolerance (paise)",
};

export default function Policy({ runs, onRun }: { runs: Run[]; onRun: (id: string) => void }) {
  const { data, setData } = useApi<any>(`/policy/settings`, []);
  const [busy, setBusy] = useState(false);
  const [showLive, setShowLive] = useState(false);
  const [name, setName] = useReviewer();
  const [why, setWhy] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [last, setLast] = useState<any>(null);
  const [a, setA] = useState<string>("");
  const [b, setB] = useState<string>("");
  const ra = a || runs[1]?.run_id || "";
  const rb = b || runs[0]?.run_id || "";
  const cmp = useApi<any>(ra && rb && ra !== rb ? `/compare/${ra}/${rb}` : null, [ra, rb]);

  const save = async (key: string, value: string) => {
    setErr(null);
    try {
      setData(await api("/policy/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ setting_key: key, setting_value: value, changed_by: name, reason: why }) }));
    } catch (e: any) { setErr(e.message); }
  };
  const rerun = async () => {
    setBusy(true); setErr(null); setShowLive(true);
    try {
      const off = (data?.settings ?? []).filter((s: any) => s.setting_value === "false").map((s: any) => SHORT_OFF[s.setting_key] ?? s.setting_key);
      const label = off.length ? `Re-run: ${off.join(", ")}` : "Re-run: default policy";
      const r = await api<any>("/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ label: label.slice(0, 190) }) });
      setLast(r); setA(""); setB(""); onRun(r.run_id);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Policy and re-runs</h1>
          <p>Each interpretation is a setting. Change one, re-run the whole book in Exasol, and see which loans and amounts change.</p>
        </div>
        <button className="btn" onClick={rerun} disabled={busy}>{busy ? "Running in Exasol…" : "Re-run audit with this policy"}</button>
      </div>
      {err && <div className="verdict warn" style={{ marginBottom: 16 }}>{err}</div>}
      {showLive && <LivePanel running={busy} onClose={() => setShowLive(false)} />}
      {last &&<div className="verdict ok" style={{ marginBottom: 16 }}>New run <span className="mono">{last.run_id.slice(0, 8)}</span> finished in {seconds(last.duration_ms)}. It is now selected; the comparison below shows what changed.</div>}

      <div className="grid g2" style={{ alignItems: "start" }}>
        <div className="card pad">
          <h2>Settings</h2>
          <p className="small muted">Every change records who made it and why, and goes in the inspection pack.</p>
          <ActorFields name={name} setName={setName} reason={why} setReason={setWhy} why="Reason for this change" />
          {(data?.settings ?? []).map((s: any) => {
            const bool = s.setting_value === "true" || s.setting_value === "false";
            return (
              <div key={s.setting_key} className="toggle">
                <div>
                  <div style={{ fontWeight: 500 }}>{NICE[s.setting_key] ?? s.setting_key}</div>
                  <div className="small muted">{HELP[s.setting_key] ?? s.description}</div>
                </div>
                {bool ? (
                  <button className={`switch ${s.setting_value === "true" ? "on" : ""}`} aria-label={s.setting_key}
                    onClick={() => save(s.setting_key, s.setting_value === "true" ? "false" : "true")} />
                ) : (
                  <input defaultValue={s.setting_value} style={{ width: 70, font: "inherit", padding: "4px 8px", border: "1px solid var(--rule)", borderRadius: 6 }}
                    onBlur={(e) => e.target.value !== s.setting_value && save(s.setting_key, e.target.value)} />
                )}
              </div>
            );
          })}
        </div>
        <div className="card pad">
          <h2>Money-in-hand precedence</h2>
          <p className="small muted">Which record decides the day money reached the borrower, by payment mode. Stored as data in Exasol, so compliance can change it without code.</p>
          <table className="t">
            <thead><tr><th>Mode</th><th>Rank</th><th>Evidence</th><th>Rule</th></tr></thead>
            <tbody>
              {(data?.date_precedence ?? []).map((r: any) => (
                <tr key={r.payment_mode + r.rank}><td className="small">{MODE_WORDS[r.payment_mode] ?? r.payment_mode}</td><td>{r.rank}</td><td className="small">{SOURCE_WORDS[r.evidence_source] ?? r.evidence_source}</td>
                  <td className="small">{r.rule === "MAX_WITH_CHEQUE_DATE" ? "Later of this and the cheque date" : r.rule === "FALLBACK" ? "Only if the setting allows it" : "Use as is"}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <section className="section">
        <header>
          <div><h2>Compare two runs</h2><p>Differences are computed by Exasol from the two runs' findings.</p></div>
          <div className="filters" style={{ margin: 0 }}>
            <select value={ra} onChange={(e) => setA(e.target.value)}>{runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.run_id.slice(0, 8)} · {r.label}</option>)}</select>
            <span className="muted">to</span>
            <select value={rb} onChange={(e) => setB(e.target.value)}>{runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.run_id.slice(0, 8)} · {r.label}</option>)}</select>
          </div>
        </header>
        {cmp.data && (
          <>
            <div className="grid g3">
              <div className="tile"><div className="upper">Refund total</div><div className="v">{inr(cmp.data.totals.b_refund)}</div>
                <div className={`d num ${Number(cmp.data.totals.delta_refund) > 0 ? "delta-up" : Number(cmp.data.totals.delta_refund) < 0 ? "delta-down" : ""}`}>{String(cmp.data.totals.delta_refund).startsWith("-") ? "" : "+"}{inr(cmp.data.totals.delta_refund)} vs {inr(cmp.data.totals.a_refund)}</div></div>
              <div className="tile"><div className="upper">Borrowers owed</div><div className="v">{n(cmp.data.totals.b_loans)}</div>
                <div className="d num">{String(cmp.data.totals.delta_loans).startsWith("-") ? "" : "+"}{n(cmp.data.totals.delta_loans)} vs {n(cmp.data.totals.a_loans)}</div></div>
              <div className="tile slate"><div className="upper">Permitted (not refunded)</div><div className="v">{inr(cmp.data.totals.b_permitted)}</div>
                <div className="d num">was {inr(cmp.data.totals.a_permitted)}</div></div>
            </div>
            <div className="grid g2" style={{ marginTop: 16, alignItems: "start" }}>
              <div className="card">
                <table className="t">
                  <thead><tr><th>Status</th><th>Practice</th><th className="r">Before</th><th className="r">After</th><th className="r">Change</th></tr></thead>
                  <tbody>{(cmp.data.by_status_practice as any[]).filter((r) => r.delta_paise !== 0).map((r) => (
                    <tr key={r.status + r.practice_code}><td><span className={`tag ${r.status}`}>{r.status}</span></td><td className="small">{r.practice_code ? `${r.practice_code} ${PRACTICE[r.practice_code] ?? ""}` : "-"}</td>
                      <td className="r">{inr(r.a_paise, { paise: false })}</td><td className="r">{inr(r.b_paise, { paise: false })}</td><td className="r">{inr(r.delta_paise, { paise: false })}</td></tr>
                  ))}</tbody>
                </table>
                {(cmp.data.by_status_practice as any[]).every((r) => r.delta_paise === 0) && <div className="empty">No change between these runs.</div>}
              </div>
              <div className="card">
                <table className="t">
                  <thead><tr><th>Loan</th><th>Status before → after</th><th className="r">Refund change</th></tr></thead>
                  <tbody>{(cmp.data.loans as any[]).slice(0, 25).map((r) => (
                    <tr key={r.loan_id} className="click" onClick={() => (window.location.hash = `#/loan/${r.loan_id}`)}>
                      <td className="mono small">{r.loan_id}</td><td className="small">{r.a_status ?? "none"} → {r.b_status ?? "none"}</td><td className="r">{inr(r.delta_paise)}</td></tr>
                  ))}</tbody>
                </table>
                {cmp.data.loans.length === 0 && <div className="empty">No loan changed.</div>}
              </div>
            </div>
          </>
        )}
        {!cmp.data && <div className="empty">Re-run with a different policy to compare.</div>}
      </section>

      <section className="section">
        <header><h2>Policy change log</h2></header>
        <div className="card">
          <table className="t">
            <thead><tr><th>When (UTC)</th><th>Setting</th><th>Change</th><th>By</th><th>Reason</th></tr></thead>
            <tbody>{(data?.changes ?? []).map((c: any, i: number) => (
              <tr key={i}><td className="small">{day(c.changed_at)} {String(c.changed_at).slice(11, 16)}</td><td className="small">{NICE[c.setting_key] ?? c.setting_key}</td>
                <td className="small mono">{c.old_value} → {c.new_value}</td><td className="small">{c.changed_by}</td><td className="small muted">{c.reason}</td></tr>
            ))}</tbody>
          </table>
          {data && !data.changes?.length && <div className="empty">No changes recorded yet.</div>}
        </div>
      </section>

      <section className="section">
        <header><h2>Run history</h2></header>
        <div className="card">
          <table className="t">
            <thead><tr><th>Run</th><th>When</th><th>Label</th><th className="r">Time in Exasol</th><th className="r">Refund</th></tr></thead>
            <tbody>{runs.map((r) => (
              <tr key={r.run_id}><td className="mono small">{r.run_id.slice(0, 8)}</td><td className="small">{day(r.started_at)} {r.started_at.slice(11, 16)} UTC</td>
                <td className="small muted">{r.label}</td><td className="r">{seconds(r.duration_ms)}</td><td className="r">{inr(r.refund_paise, { paise: false })}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </section>
    </>
  );
}
