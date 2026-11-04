import { useMemo, useState } from "react";
import { CONFIDENCE_WORDS, DAYCOUNT_WORDS, day, describeConvention, go, inr, inrExact, LETTER_WORDS, LOAN_STATUS_WORDS, MODE_WORDS, month, plural, post, PRACTICE, REVIEW_WORDS, SOURCE_WORDS, sources, STATUS_WORDS, useApi, useReviewer } from "../lib";
import { ActorFields, missingActor } from "./Review";
import SourceRecords from "./SourceRecords";

const DAY_MS = 86400000;
const toT = (d: string) => Date.parse(d.slice(0, 10) + "T00:00:00Z");

export default function Loan({ runId, loanId, period }: { runId: string; loanId?: string; period: string | null }) {
  const [ver, setVer] = useState(0);
  const { data, error } = useApi<any>(loanId ? `/runs/${runId}/loans/${loanId}` : null, [runId, loanId, ver]);
  const periods: any[] = data?.periods ?? [];
  const selected = useMemo(() => {
    if (!periods.length) return null;
    if (period) return periods.find((p) => p.period_start === period) ?? null;
    const flagged = periods.filter((p) => p.match_status !== "FAIR");
    return flagged[0] ?? periods[0];
  }, [periods, period]);
  const proof = useApi<any>(selected ? `/runs/${runId}/loans/${loanId}/proof/${selected.period_start}` : null, [runId, loanId, selected?.period_start]);

  if (!loanId) return <div className="empty">Pick a loan from the ledger or search.</div>;
  if (error) return <div className="empty">{error}</div>;
  if (!data) return <div className="loading">Loading loan {loanId} from Exasol…</div>;
  const L = data.loan;
  const total = data.ledger_total;
  const pickPeriod = (p: string) => go(`/loan/${loanId}?period=${p}`);
  const flagged = periods.filter((p) => p.match_status !== "FAIR");

  return (
    <>
      <div className="loan-head">
        <div>
          <div className="upper">{L.product === "HOME" ? "Home loan" : L.product === "PERSONAL" ? "Personal loan" : L.product} · {L.branch_name}</div>
          <h1 style={{ marginTop: 4 }}>{L.display_name} <span className="faint mono" style={{ fontSize: 18 }}>{L.loan_id}</span></h1>
          <div className="kv">
            <span>Sanctioned <b>{inr(L.sanctioned_paise, { paise: false })}</b></span>
            <span>Sanction <b>{day(L.sanction_date)}</b></span>
            <span>Rate (KFS) <b>{L.annual_rate_pct}%</b></span>
            <span>Day count <b>{DAYCOUNT_WORDS[L.day_count_basis] ?? L.day_count_basis}</b></span>
            {L.commitment_fee_rate_pct && <span>Commitment fee disclosed <b>{L.commitment_fee_rate_pct}% p.a.</b></span>}
            <span>Status <b>{LOAN_STATUS_WORDS[L.status] ?? L.status}</b></span>
          </div>
        </div>
        <div className="card pad" style={{ minWidth: 260 }}>
          <div className="upper">Refund owed on this loan</div>
          <div className="num" style={{ fontSize: 28, fontWeight: 600, color: Number(total.excess_paise) > 0 ? "var(--accent)" : "var(--ink)" }}>{inr(total.excess_paise)}</div>
          <div className="small muted">{data.ledger.length ? data.ledger.map((r: any) => `${r.practice_code} ${inr(r.excess_paise)}`).join(" · ") : flaggedNote(periods)}</div>
          {data.ledger.length > 0 && <a className="btn" style={{ marginTop: 12 }} href={`#/letter/${loanId}`}>Borrower letter</a>}
        </div>
      </div>

      {(data.review.length > 0 || data.review_history.length > 0) && <ReviewPanel data={data} onChange={() => setVer((v) => v + 1)} />}

      <section className="section">
        <header>
          <div>
            <h2>When did the money actually reach them?</h2>
            <p>All recorded dates for each tranche. The money-in-hand date follows the precedence rules in Policy, and disagreeing dates are flagged.</p>
          </div>
        </header>
        <div className="grid">
          {data.tranches.map((t: any) => (
            <Tranche key={t.tranche_no} t={t} loan={L}
              evidence={data.evidence.filter((e: any) => e.tranche_no === t.tranche_no)}
              extra={(proof.data?.extra_intervals ?? []) as any[]} />
          ))}
        </div>
      </section>

      <section className="section">
        <header>
          <div>
            <h2>Every billing month, posted vs recomputed</h2>
            <p>{plural(periods.length, "month")} audited, {flagged.length} {flagged.length === 1 ? "differs" : "differ"} from fair interest. Select a month to see the working.</p>
          </div>
          <Legend />
        </header>
        <div className="card pad">
          <div className="strip">
            {periods.map((p) => (
              <button key={p.period_start} title={`${month(p.period_start)} · ${STATUS_WORDS[p.match_status]} · ${inr(p.excess_paise)}`}
                className={`${p.match_status} ${selected?.period_start === p.period_start ? "sel" : ""}`}
                onClick={() => pickPeriod(p.period_start)} />
            ))}
          </div>
          <div className="strip-axis">
            {periods.map((p, i) => <span key={p.period_start}>{i === 0 || p.period_start.slice(5, 7) === "01" ? p.period_start.slice(0, 7) : ""}</span>)}
          </div>
        </div>
      </section>

      {selected && <Proof key={selected.period_start} runId={runId} loanId={loanId} sel={selected} proof={proof.data} findings={data.findings.filter((f: any) => f.period_start === selected.period_start)} />}

      {flagged.length > 0 && (
        <section className="section">
          <header><h2>All months with a finding</h2></header>
          <div className="card">
            <table className="t">
              <thead><tr><th>Month</th><th>Status</th><th>Convention that reproduces the posting</th><th className="r">Posted</th><th className="r">Fair</th><th className="r">Excess</th></tr></thead>
              <tbody>
                {flagged.map((p) => (
                  <tr key={p.period_start} className={`click ${selected?.period_start === p.period_start ? "sel" : ""}`} onClick={() => pickPeriod(p.period_start)}>
                    <td>{month(p.period_start)}</td>
                    <td><span className={`tag ${p.match_status}`}>{STATUS_WORDS[p.match_status]}</span></td>
                    <td className="small">{p.matched_convention_id ? describeConvention(p.matched_convention_id) : <span className="faint">{p.match_status === "UNEXPLAINED" ? `None (closest: ${describeConvention(p.closest_convention_id).toLowerCase()})` : "-"}</span>}</td>
                    <td className="r">{inr(p.posted_paise)}</td>
                    <td className="r">{inr(p.fair_paise)}</td>
                    <td className="r">{inr(p.excess_paise)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}

function ReviewPanel({ data, onChange }: { data: any; onChange: () => void }) {
  const [name, setName] = useReviewer();
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const decide = async (r: any, decision: string) => {
    const missing = missingActor(name, reason);
    if (missing) { setErr(missing); return; }
    setErr(null);
    try {
      await post(`/runs/${data.run_id}/review/decisions`, { loan_id: r.loan_id, practice_code: r.practice_code, decision, reviewer: name, reason });
      setReason("");
      onChange();
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <section className="section">
      <header>
        <div>
          <h2>Review</h2>
          <p>A person decides whether this refund goes ahead. The decision records the figure they saw; it cannot change it.</p>
        </div>
        {data.letter && <span className={`tag ${data.letter.letter_state}`}>Letter: {LETTER_WORDS[data.letter.letter_state]}</span>}
      </header>
      {err && <div className="verdict warn" style={{ marginBottom: 12 }}>{err}</div>}
      {data.review.length > 0 && <ActorFields name={name} setName={setName} reason={reason} setReason={setReason} />}
      <div className="card">
        <table className="t">
          <thead><tr><th>Practice</th><th className="r">Refund</th><th>Review</th><th>Latest decision</th><th className="r">Action</th></tr></thead>
          <tbody>
            {data.review.map((r: any) => (
              <tr key={r.practice_code}>
                <td><span className="tag code">{r.practice_code}</span> <span className="small muted">{PRACTICE[r.practice_code]}</span></td>
                <td className="r">{inr(r.excess_paise)}</td>
                <td><span className={`tag ${r.review_state}`}>{REVIEW_WORDS[r.review_state]}</span></td>
                <td className="small muted">{r.decided_by ? `${r.decided_by}: ${r.review_reason}` : "-"}{r.review_state === "STALE" && <div className="tiny">Decided at {inr(r.reviewed_paise)}; the figure has changed since.</div>}</td>
                <td className="r nowrap">
                  <button className="btn mini" onClick={() => decide(r, "APPROVED")}>Approve</button>{" "}
                  <button className="btn ghost mini" onClick={() => decide(r, "HOLD")}>Hold</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.review_history.length > 0 && (
        <details style={{ marginTop: 10 }}>
          <summary className="small muted">All decisions on this loan ({data.review_history.length})</summary>
          <div className="card" style={{ marginTop: 8 }}>
            <table className="t">
              <thead><tr><th>When (UTC)</th><th>Item</th><th>Decision</th><th className="r">Figure seen</th><th>By</th><th>Reason</th></tr></thead>
              <tbody>
                {data.review_history.map((h: any, i: number) => (
                  <tr key={i}>
                    <td className="small">{day(h.decided_at)} {String(h.decided_at).slice(11, 16)}</td>
                    <td className="small">{h.practice_code ?? month(h.period_start)}</td>
                    <td><span className={`tag ${h.review_decision}`}>{REVIEW_WORDS[h.review_decision]}</span></td>
                    <td className="r">{inr(h.figure_paise)}</td>
                    <td className="small">{h.decided_by}</td>
                    <td className="small muted">{h.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </section>
  );
}

function flaggedNote(periods: any[]): string {
  if (periods.some((p) => p.match_status === "EVIDENCE_GAP")) return "Nothing refundable yet: evidence pending from the branch";
  if (periods.some((p) => p.match_status === "PERMITTED")) return "Nothing refundable: charges match disclosed terms";
  return "Nothing refundable";
}

function Legend() {
  const items: [string, string][] = [["FAIR", "Fair"], ["REFUND", "Refund"], ["PERMITTED", "Permitted"], ["EVIDENCE_GAP", "Gap"], ["UNEXPLAINED", "Unexplained"], ["AMBIGUOUS", "Ambiguous"]];
  return (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }} className="tiny muted">
      {items.map(([k, label]) => (
        <span key={k} style={{ display: "inline-flex", gap: 5, alignItems: "center" }}>
          <span className={`strip-key ${k}`} style={{ width: 10, height: 10, borderRadius: 2, display: "inline-block",
            background: { FAIR: "var(--ok-soft)", REFUND: "var(--accent)", PERMITTED: "var(--slate)", EVIDENCE_GAP: "var(--warn)", UNEXPLAINED: "#6b5a8e", AMBIGUOUS: "#b07a45" }[k] }} />
          {label}
        </span>
      ))}
    </div>
  );
}

function Tranche({ t, loan, evidence, extra }: { t: any; loan: any; evidence: any[]; extra: any[] }) {
  const marks: { label: string; date: string; kind: string; note?: string }[] = [];
  if (t.tranche_no === 1) {
    marks.push({ label: "Sanction", date: loan.sanction_date, kind: "ref" });
    marks.push({ label: "Agreement", date: loan.agreement_date, kind: "ref" });
  }
  evidence.forEach((e) => marks.push({ label: `${SOURCE_WORDS[e.evidence_source] ?? e.evidence_source}${e.recorded_in === "REVIEWER" ? " (branch reply)" : ""}`, date: e.event_date, kind: "ev", note: e.recorded_in }));
  const all = marks.map((m) => toT(m.date)).concat(t.resolved_date ? [toT(t.resolved_date)] : []);
  const bands = extra.filter((x) => x.extra_balance_paise && toT(x.interval_end) > Math.min(...all) - 40 * DAY_MS && toT(x.interval_start) < Math.max(...all) + 40 * DAY_MS);
  bands.forEach((b) => { all.push(toT(b.interval_start)); all.push(toT(b.interval_end)); });
  let lo = Math.min(...all), hi = Math.max(...all);
  const span = Math.max(hi - lo, 10 * DAY_MS);
  lo -= span * 0.06; hi = lo + span * 1.12;
  const W = 1000, x = (d: string) => 30 + ((toT(d) - lo) / (hi - lo)) * (W - 60);
  // records on the same day share one mark, so their labels never draw over each other
  const rows = [...marks].sort((a, b) => toT(a.date) - toT(b.date)).reduce<typeof marks>((out, m) => {
    const last = out[out.length - 1];
    if (last && last.date === m.date) out[out.length - 1] = { ...last, label: `${last.label}, ${m.label}`, kind: last.kind === "ev" ? "ev" : m.kind };
    else out.push(m);
    return out;
  }, []);

  return (
    <div className="card pad">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 16 }}>
        <h3>Tranche {t.tranche_no} · {inr(t.amount_paise, { paise: false })} · {MODE_WORDS[t.payment_mode] ?? t.payment_mode} to {String(t.payee_type).toLowerCase()}</h3>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className={`tag ${t.confidence}`}>{CONFIDENCE_WORDS[t.confidence] ?? t.confidence}</span>
          {t.conflict_flag && <span className="tag AMBIGUOUS">Sources disagree by {plural(t.max_spread_days, "day")}</span>}
        </div>
      </div>
      <svg className="tl" viewBox={`0 0 ${W} 122`} preserveAspectRatio="none" style={{ height: 122, marginTop: 10 }}>
        <line x1={20} x2={W - 20} y1={70} y2={70} stroke="var(--rule)" strokeWidth={1.5} />
        {bands.map((b, i) => (
          <g key={i}>
            <rect x={x(b.interval_start)} y={60} width={Math.max(2, x(b.interval_end) - x(b.interval_start))} height={20} fill="var(--accent)" opacity={0.18} />
          </g>
        ))}
        {rows.map((m, i) => {
          const up = i % 2 === 0;
          // a label near the right edge reads leftwards from its mark, so a merged label stays inside the card
          const flip = x(m.date) > W * 0.7;
          const tx = x(m.date) + (flip ? -5 : 5);
          const anchor = flip ? "end" : "start";
          return (
            <g key={m.label + m.date}>
              <line x1={x(m.date)} x2={x(m.date)} y1={up ? 30 : 70} y2={up ? 70 : 108} stroke={m.kind === "ref" ? "var(--ink-3)" : "var(--ink-2)"} strokeDasharray={m.kind === "ref" ? "3 3" : ""} />
              <circle cx={x(m.date)} cy={70} r={4} fill={m.kind === "ref" ? "var(--paper)" : "var(--ink)"} stroke="var(--ink)" />
              <text className="lbl" x={tx} y={up ? 22 : 118} textAnchor={anchor}>{m.label}</text>
              <text x={tx} y={up ? 34 : 106} textAnchor={anchor}>{day(m.date)}</text>
            </g>
          );
        })}
        {t.resolved_date && (
          <g>
            <circle cx={x(t.resolved_date)} cy={70} r={8} fill="none" stroke="var(--ok)" strokeWidth={2.5} />
          </g>
        )}
      </svg>
      <div className="small" style={{ marginTop: 6 }}>
        {t.confidence === "GAP" ? (
          <span>Money-in-hand date cannot be confirmed. Missing: <b>{sources(t.missing_sources)}</b>. Months between {day(t.gap_window_start)} and {day(t.gap_window_end)} are held out of the refund total.</span>
        ) : (
          <span>Money in hand <b>{day(t.resolved_date)}</b> (green ring), from the <b>{sources(t.resolved_source)}</b>{t.confidence === "FALLBACK" ? ", using the LMS date because no rail credit record exists" : ""}.
            {bands.length > 0 && <span style={{ color: "var(--accent-ink)" }}> Shaded: interest charged before the money was in hand, {plural(bands.reduce((a, b) => a + Number(b.days), 0), "day")}.</span>}</span>
        )}
        <span className="faint"> Evidence IDs: <span className="mono">{t.evidence_ids}</span></span>
      </div>
    </div>
  );
}

function Proof({ runId, loanId, sel, proof, findings }: { runId: string; loanId: string; sel: any; proof: any; findings: any[] }) {
  const [showSource, setShowSource] = useState(false);
  const status = sel.match_status;
  const tone = { FAIR: "ok", MATCHED: "", PERMITTED: "slate", EVIDENCE_GAP: "warn", UNEXPLAINED: "purple", AMBIGUOUS: "", UNDERCHARGE: "ok" }[status as string] ?? "";
  const codes = findings.map((f) => f.practice_code).filter(Boolean);
  return (
    <section className="section">
      <header>
        <div>
          <h2>Why this figure: {month(sel.period_start)}</h2>
          <p>How Exasol arrived at this month's figure, interval by interval. Interest is kept exact until the monthly total, which is rounded half up once.</p>
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <button className="btn" onClick={() => setShowSource((v) => !v)} aria-expanded={showSource}>{showSource ? "Hide source records" : "Show source records"}</button>
          <a className="btn ghost" href="#/method/S70_FINGERPRINT">{status === "MATCHED" || status === "PERMITTED" ? "SQL that matched it" : "View the SQL"}</a>
        </div>
      </header>
      <div className="proof">
        <div><div className="upper">Posted by the loan system</div><div className="v">{inr(sel.posted_paise)}</div><div className="tiny faint mono">{sel.posting_ids}</div></div>
        <div><div className="upper">Fair, recomputed</div><div className="v">{inr(sel.fair_paise)}</div><div className="tiny faint">from the money-in-hand date, KFS rate and day count</div></div>
        <div className="excess"><div className="upper">{status === "EVIDENCE_GAP" ? "Provisional difference" : "Excess"}</div><div className="v">{inr(sel.excess_paise)}</div><div className="tiny faint">{status === "EVIDENCE_GAP" ? "posted minus provisional fair, not refunded" : "posted minus fair"}</div></div>
      </div>
      <div className={`verdict ${tone}`} style={{ marginTop: 14 }}>
        {status === "MATCHED" && <>The posting is reproduced <b>exactly, to the paisa</b>, by one convention: <b>{describeConvention(sel.matched_convention_id)}</b>. {codes.map((c) => <span key={c} className="tag code" style={{ marginRight: 4 }}>{c}</span>)} {codes.map((c) => PRACTICE[c]).join("; ")}.</>}
        {status === "FAIR" && <>The posted amount equals fair interest. Nothing to refund.</>}
        {status === "PERMITTED" && <>{findings[0]?.reason}</>}
        {status === "EVIDENCE_GAP" && <>{findings[0]?.reason} The provisional figures below are shown for context only.</>}
        {status === "UNEXPLAINED" && <>{findings[0]?.reason} This goes to the unexplained queue for a human, rather than being forced into a practice.</>}
        {status === "AMBIGUOUS" && <>{findings[0]?.reason}</>}
        {status === "UNDERCHARGE" && <>{findings[0]?.reason}</>}
      </div>

      {showSource && <SourceRecords runId={runId} loanId={loanId} sel={sel} />}

      {findings.length > 1 && (
        <div className="card" style={{ marginTop: 14 }}>
          <table className="t">
            <thead><tr><th>Practice</th><th>Attributed excess</th><th className="r">Days</th></tr></thead>
            <tbody>{findings.map((f) => <tr key={f.finding_id}><td><span className="tag code">{f.practice_code}</span> {PRACTICE[f.practice_code]}</td><td className="num">{inr(f.excess_paise)}</td><td className="r">{f.days_affected}</td></tr>)}</tbody>
          </table>
        </div>
      )}

      {!proof ? <div className="loading">Loading working…</div> : (
        <div className="grid g2" style={{ marginTop: 14, alignItems: "start" }}>
          <div className="card">
            <div className="pad" style={{ paddingBottom: 6 }}><h3>Fair interest, interval by interval</h3>
              <div className="math">balance × rate × days ÷ (100 × {proof.divisor})</div></div>
            <table className="t">
              <thead><tr><th>From</th><th>To</th><th className="r">Balance</th><th className="r">Rate</th><th className="r">Days</th><th className="r">Interest</th></tr></thead>
              <tbody>
                {proof.fair_intervals.map((r: any) => (
                  <tr key={r.interval_start}>
                    <td className="small">{day(r.interval_start)}</td><td className="small">{day(r.interval_end)}</td>
                    <td className="r">{inr(r.balance_paise, { paise: false })}</td><td className="r">{r.annual_rate_pct}%</td>
                    <td className="r">{r.days}</td><td className="r" dangerouslySetInnerHTML={{ __html: inrExact(r.interest_paise_exact) }} />
                  </tr>
                ))}
                {proof.fair_intervals.length === 0 && <tr><td colSpan={6} className="small muted">No principal outstanding in this month under the fair convention.</td></tr>}
                <tr><td colSpan={5} className="small"><b>Month total, rounded half up once</b></td><td className="r"><b>{inr(sel.fair_paise)}</b></td></tr>
              </tbody>
            </table>
          </div>
          <div className="card">
            <div className="pad" style={{ paddingBottom: 6 }}><h3>What was charged on top</h3>
              <div className="math">{sel.matched_convention_id && sel.matched_convention_id !== "MIH|DIS|NET|EXACT" ? describeConvention(sel.matched_convention_id) : "No extra balance under a recognised convention"}</div></div>
            {proof.extra_intervals.length > 0 ? (
              <table className="t">
                <thead><tr><th>From</th><th>To</th><th className="r">Extra balance</th><th className="r">Rate</th><th className="r">Days</th><th className="r">Interest</th></tr></thead>
                <tbody>
                  {proof.extra_intervals.map((r: any) => (
                    <tr key={r.interval_start + r.convention_id}>
                      <td className="small">{day(r.interval_start)}</td><td className="small">{day(r.interval_end)}</td>
                      <td className="r">{Number(r.fee_balance_paise) ? <>fee on {inr(r.fee_balance_paise, { paise: false })}</> : inr(r.extra_balance_paise, { paise: false })}</td>
                      <td className="r">{Number(r.fee_balance_paise) ? r.fee_rate_pct : r.annual_rate_pct}%</td>
                      <td className="r">{r.days}</td><td className="r" dangerouslySetInnerHTML={{ __html: inrExact(r.interest_paise_exact) }} />
                    </tr>
                  ))}
                  <tr><td colSpan={5} className="small"><b>Excess for the month (posted − fair)</b></td><td className="r"><b>{inr(sel.excess_paise)}</b></td></tr>
                </tbody>
              </table>
            ) : <div className="pad small muted">{status === "UNEXPLAINED" ? `Closest candidate (${describeConvention(sel.closest_convention_id).toLowerCase()}) is off by ${inr(sel.closest_diff_paise)}.` : "Nothing charged on top."}</div>}
            <div className="pad small" style={{ borderTop: "1px solid var(--rule-2)" }}>
              <div className="upper" style={{ marginBottom: 6 }}>Postings in the loan system</div>
              {proof.postings.map((p: any) => (
                <div key={p.posting_id} className="mono tiny" style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>{p.posting_id}{p.reverses_posting_id ? ` reverses ${p.reverses_posting_id}` : ""}{p.is_manual ? " · manual journal" : ""}</span>
                  <span>{inr(p.posted_paise)} on {day(p.posted_on)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
