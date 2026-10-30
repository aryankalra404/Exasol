import { useMemo } from "react";
import { day, describeConvention, go, inr, inrExact, month, n, PRACTICE, SOURCE_WORDS, STATUS_WORDS, useApi } from "../lib";

const DAY_MS = 86400000;
const toT = (d: string) => Date.parse(d.slice(0, 10) + "T00:00:00Z");

export default function Loan({ runId, loanId, period }: { runId: string; loanId?: string; period: string | null }) {
  const { data, error } = useApi<any>(loanId ? `/runs/${runId}/loans/${loanId}` : null, [runId, loanId]);
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
            <span>Day count <b>{L.day_count_basis}</b></span>
            {L.commitment_fee_rate_pct && <span>Commitment fee disclosed <b>{L.commitment_fee_rate_pct}% p.a.</b></span>}
            <span>Status <b>{L.status}</b></span>
          </div>
        </div>
        <div className="card pad" style={{ minWidth: 260 }}>
          <div className="upper">Refund owed on this loan</div>
          <div className="num" style={{ fontSize: 28, fontWeight: 600, color: Number(total.excess_paise) > 0 ? "var(--accent)" : "var(--ink)" }}>{inr(total.excess_paise)}</div>
          <div className="small muted">{data.ledger.length ? data.ledger.map((r: any) => `${r.practice_code} ${inr(r.excess_paise)}`).join(" · ") : "Nothing refundable"}</div>
          {data.ledger.length > 0 && <a className="btn" style={{ marginTop: 12 }} href={`#/letter/${loanId}`}>Borrower letter</a>}
        </div>
      </div>

      <section className="section">
        <header>
          <div>
            <h2>When did the money actually reach them?</h2>
            <p>Every date source for each tranche, side by side. The resolved date follows the precedence rules in Policy; conflicts are flagged, not hidden.</p>
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
            <p>{n(periods.length)} months audited, {flagged.length} differ from fair interest. Click a month to see the working.</p>
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

      {selected && <Proof sel={selected} proof={proof.data} findings={data.findings.filter((f: any) => f.period_start === selected.period_start)} />}

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
                    <td className="small">{p.matched_convention_id ? describeConvention(p.matched_convention_id) : <span className="faint">{p.match_status === "UNEXPLAINED" ? `none (closest ${p.closest_convention_id})` : "-"}</span>}</td>
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
  evidence.forEach((e) => marks.push({ label: SOURCE_WORDS[e.evidence_source] ?? e.evidence_source, date: e.event_date, kind: "ev", note: e.recorded_in }));
  const all = marks.map((m) => toT(m.date)).concat(t.resolved_date ? [toT(t.resolved_date)] : []);
  const bands = extra.filter((x) => x.extra_balance_paise && toT(x.interval_end) > Math.min(...all) - 40 * DAY_MS && toT(x.interval_start) < Math.max(...all) + 40 * DAY_MS);
  bands.forEach((b) => { all.push(toT(b.interval_start)); all.push(toT(b.interval_end)); });
  let lo = Math.min(...all), hi = Math.max(...all);
  const span = Math.max(hi - lo, 10 * DAY_MS);
  lo -= span * 0.06; hi = lo + span * 1.12;
  const W = 1000, x = (d: string) => 30 + ((toT(d) - lo) / (hi - lo)) * (W - 60);
  const rows = [...marks].sort((a, b) => toT(a.date) - toT(b.date));

  return (
    <div className="card pad">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 16 }}>
        <h3>Tranche {t.tranche_no} · {inr(t.amount_paise, { paise: false })} · {t.payment_mode} to {String(t.payee_type).toLowerCase()}</h3>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className={`tag ${t.confidence}`}>{t.confidence}</span>
          {t.conflict_flag && <span className="tag AMBIGUOUS">sources disagree by {t.max_spread_days} days</span>}
        </div>
      </div>
      <svg className="tl" viewBox={`0 0 ${W} 122`} preserveAspectRatio="none" style={{ height: 122, marginTop: 10 }}>
        <line x1={20} x2={W - 20} y1={70} y2={70} stroke="var(--rule)" strokeWidth={1.5} />
        {bands.map((b, i) => (
          <g key={i}>
            <rect x={x(b.interval_start)} y={60} width={Math.max(2, x(b.interval_end) - x(b.interval_start))} height={20} fill="var(--accent)" opacity={0.18} />
            <text x={x(b.interval_start) + 4} y={96} style={{ fill: "var(--accent-ink)" }}>charged before money in hand: {b.days} days</text>
          </g>
        ))}
        {rows.map((m, i) => {
          const up = i % 2 === 0;
          return (
            <g key={m.label + m.date}>
              <line x1={x(m.date)} x2={x(m.date)} y1={up ? 30 : 70} y2={up ? 70 : 108} stroke={m.kind === "ref" ? "var(--ink-3)" : "var(--ink-2)"} strokeDasharray={m.kind === "ref" ? "3 3" : ""} />
              <circle cx={x(m.date)} cy={70} r={4} fill={m.kind === "ref" ? "var(--paper)" : "var(--ink)"} stroke="var(--ink)" />
              <text className="lbl" x={x(m.date) + 5} y={up ? 22 : 118}>{m.label}</text>
              <text x={x(m.date) + 5} y={up ? 34 : 106}>{day(m.date)}</text>
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
          <span>No defensible money-in-hand date. Missing: <b>{t.missing_sources}</b>. Periods between {day(t.gap_window_start)} and {day(t.gap_window_end)} are held out of the refund total.</span>
        ) : (
          <span>Money in hand <b>{day(t.resolved_date)}</b> (green ring), from <b>{SOURCE_WORDS[t.resolved_source] ?? t.resolved_source}</b>{t.confidence === "FALLBACK" ? ", using the LMS date because no rail credit record exists" : ""}.</span>
        )}
        <span className="faint"> Evidence ids: <span className="mono">{t.evidence_ids}</span></span>
      </div>
    </div>
  );
}

function Proof({ sel, proof, findings }: { sel: any; proof: any; findings: any[] }) {
  const status = sel.match_status;
  const tone = { FAIR: "ok", MATCHED: "", PERMITTED: "slate", EVIDENCE_GAP: "warn", UNEXPLAINED: "purple", AMBIGUOUS: "", UNDERCHARGE: "ok" }[status as string] ?? "";
  const codes = findings.map((f) => f.practice_code).filter(Boolean);
  return (
    <section className="section">
      <header>
        <div>
          <h2>Why this figure: {month(sel.period_start)}</h2>
          <p>The working behind the number, interval by interval, as computed by Exasol. Each interval's interest is exact; the month is rounded half up once.</p>
        </div>
        <a className="btn ghost" href="#/method/S70_FINGERPRINT">SQL that matched it</a>
      </header>
      <div className="proof">
        <div><div className="upper">Posted by the loan system</div><div className="v">{inr(sel.posted_paise)}</div><div className="tiny faint mono">{sel.posting_ids}</div></div>
        <div><div className="upper">Fair, recomputed</div><div className="v">{inr(sel.fair_paise)}</div><div className="tiny faint">from the money-in-hand date, KFS rate and day count</div></div>
        <div className="excess"><div className="upper">Excess</div><div className="v">{inr(sel.excess_paise)}</div><div className="tiny faint">posted minus fair</div></div>
      </div>
      <div className={`verdict ${tone}`} style={{ marginTop: 14 }}>
        {status === "MATCHED" && <>The posting is reproduced <b>exactly, to the paisa</b>, by one convention: <b>{describeConvention(sel.matched_convention_id)}</b>. {codes.map((c) => <span key={c} className="tag code" style={{ marginRight: 4 }}>{c}</span>)} {codes.map((c) => PRACTICE[c]).join("; ")}.</>}
        {status === "FAIR" && <>The posting equals fair interest to the paisa. Nothing to refund.</>}
        {status === "PERMITTED" && <>{findings[0]?.reason}</>}
        {status === "EVIDENCE_GAP" && <>{findings[0]?.reason} The provisional figures below are shown for context only.</>}
        {status === "UNEXPLAINED" && <>{findings[0]?.reason} This goes to the unexplained queue for a human, rather than being forced into a practice.</>}
        {status === "AMBIGUOUS" && <>{findings[0]?.reason}</>}
        {status === "UNDERCHARGE" && <>{findings[0]?.reason}</>}
      </div>

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
            ) : <div className="pad small muted">{status === "UNEXPLAINED" ? `Closest candidate ${sel.closest_convention_id} is off by ${inr(sel.closest_diff_paise)}.` : "Nothing charged on top."}</div>}
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
