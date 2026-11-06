import { useEffect, useState } from "react";
import { describeConvention, go, inr, month, n, plural, useApi } from "../lib";

const VERDICT: Record<string, { label: string; tag: string; box: string }> = {
  NEW_LOANS_ONLY: { label: "Fixed for new loans only", tag: "REFUND", box: "" },
  NOT_FIXED: { label: "No fix seen", tag: "REFUND", box: "" },
  MIXED: { label: "Mixed, needs a person", tag: "AMBIGUOUS", box: "warn" },
  NOT_ENOUGH_EVIDENCE: { label: "Not enough evidence", tag: "EVIDENCE_GAP", box: "warn" },
  ALL_LOANS: { label: "Fixed for all loans", tag: "FAIR", box: "ok" },
};

const quarterOf = (d: string | null | undefined) =>
  d ? `${d.slice(0, 4)}-Q${Math.ceil(Number(d.slice(5, 7)) / 3)}` : null;

function sentence(r: any) {
  const first = r.first_fair_period ? month(r.first_fair_period) : "";
  switch (r.verdict) {
    case "NEW_LOANS_ONLY":
      return <>Fair charging first appears in <b>{first}</b>, but loans sanctioned before it never passed a test after that. Their last month on the old rule is <b>{month(r.last_old_rule_period)}</b>.</>;
    case "NOT_FIXED":
      return <>No test month was ever charged fairly. The old rule was last seen in <b>{month(r.last_old_rule_period)}</b>.</>;
    case "ALL_LOANS":
      return <>Fair charging first appears in <b>{first}</b>. From then on, older and newer loans both pass, and none is on the old rule.</>;
    case "NOT_ENOUGH_EVIDENCE":
      return <>Fair charging first appears in <b>{first}</b>, but no older loan has had a test month since, so the fix is unproven for them.</>;
    default:
      return <>From <b>{first}</b>, some test months pass and others still follow the old rule. A person needs to look at these loans.</>;
  }
}

export default function Regression({ runId, branch }: { runId: string; branch?: string }) {
  const all = useApi<any[]>(`/runs/${runId}/fix-coverage`, [runId]);
  const rows = all.data ?? [];
  const main = rows.filter((r) => r.is_main);
  const br = branch ?? main[0]?.branch_id ?? "";
  const rules = rows.filter((r) => r.branch_id === br).sort((a, b) => Number(b.excess_paise) - Number(a.excess_paise));
  const [conv, setConv] = useState("");
  useEffect(() => setConv(""), [br, runId]);
  const rule = rules.find((r) => r.convention_id === conv) ?? rules[0];
  const qs = rule ? `?convention=${encodeURIComponent(rule.convention_id)}` : "";
  const detail = useApi<any>(rule ? `/runs/${runId}/fix-coverage/${br}${qs}` : null, [runId, br, rule?.convention_id]).data;
  const cohorts = useApi<any[]>(br ? `/runs/${runId}/cohorts?branch=${br}` : null, [runId, br]).data;
  const v = rule ? VERDICT[rule.verdict] : null;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Did the fix reach every loan?</h1>
          <p>A month only counts as a test when the rule found in the postings and fair interest give different figures. Every other month matches both, so it proves nothing.</p>
        </div>
      </div>

      {all.error && <div className="empty">{all.error}</div>}
      {!all.data && !all.error && <div className="loading">Reading test months from Exasol…</div>}
      {all.data && main.length === 0 && (
        <div className="verdict warn">No fix coverage in this run. Either nothing was refundable, or the run is older than this check: re-run the audit on Policy & re-runs.</div>
      )}

      {main.length > 0 && (
        <section className="section" style={{ marginTop: 0 }}>
          <header><div><h2>All branches with a refundable rule</h2><p>The main rule at each branch, by refund. Select a row for its test months.</p></div></header>
          <div className="card">
            <table className="t">
              <thead><tr><th>Branch</th><th>Rule found</th><th>Verdict</th><th>First fair test</th><th>Last on old rule</th><th className="r">Loans to correct</th></tr></thead>
              <tbody>
                {main.map((r) => (
                  <tr key={r.branch_id} className={`click ${r.branch_id === br ? "sel" : ""}`} onClick={() => go(`/regression/${r.branch_id}`)}>
                    <td>{r.branch_name}<div className="faint mono tiny">{r.branch_id}</div></td>
                    <td className="small">{describeConvention(r.convention_id)}</td>
                    <td><span className={`tag ${VERDICT[r.verdict]?.tag ?? ""}`}>{VERDICT[r.verdict]?.label ?? r.verdict}</span></td>
                    <td className="small">{r.first_fair_period ? month(r.first_fair_period) : "None"}</td>
                    <td className="small">{r.last_old_rule_period ? month(r.last_old_rule_period) : "None"}</td>
                    <td className="r num">{n(r.loans_to_correct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {br && !rule && all.data && main.length > 0 && <div className="verdict ok">No refundable rule at this branch in this run.</div>}

      {rule && v && (
        <section className="section">
          <header>
            <div>
              <h2>{rule.branch_name} <span className="faint mono tiny">{br}</span></h2>
              <p>{describeConvention(rule.convention_id)}</p>
            </div>
            {rules.length > 1 && (
              <select value={rule.convention_id} onChange={(e) => setConv(e.target.value)}
                style={{ font: "inherit", padding: "7px 10px", border: "1px solid var(--rule)", borderRadius: 6, background: "var(--card)", maxWidth: 340 }}>
                {rules.map((r) => <option key={r.convention_id} value={r.convention_id}>{r.is_main ? "Main rule: " : "Also matched: "}{describeConvention(r.convention_id)}</option>)}
              </select>
            )}
          </header>

          <div className={`verdict ${v.box}`} style={{ marginBottom: 16 }}>
            <span className={`tag ${v.tag}`} style={{ marginRight: 8 }}>{v.label}</span>{sentence(rule)}
            {!rule.is_main && <div className="small muted" style={{ marginTop: 6 }}>This is not the branch's main rule. In some months it gives the same figure as the main rule, so read it with care.</div>}
          </div>

          {rule.first_fair_period && (
            <div className="card" style={{ marginBottom: 16 }}>
              <table className="t">
                <thead><tr><th>Test months from {month(rule.first_fair_period)}</th><th className="r">Still on old rule</th><th className="r">Charged fairly</th></tr></thead>
                <tbody>
                  <tr><td>Loans sanctioned before {month(rule.first_fair_period)}</td><td className="r num">{n(rule.older_old_rule_months)}</td><td className="r num">{n(rule.older_fair_months)}</td></tr>
                  <tr><td>Loans sanctioned from {month(rule.first_fair_period)}</td><td className="r num">{n(rule.newer_old_rule_months)}</td><td className="r num">{n(rule.newer_fair_months)}</td></tr>
                </tbody>
              </table>
            </div>
          )}

          <Heat rule={rule} grid={detail?.grid} cohorts={cohorts ?? undefined} />
          <Actions runId={runId} br={br} rule={rule} loans={detail?.loans} qs={qs} />
        </section>
      )}
    </>
  );
}

function Heat({ rule, grid, cohorts }: { rule: any; grid?: any[]; cohorts?: any[] }) {
  if (!grid || !cohorts) return <div className="card pad"><div className="loading">Loading…</div></div>;
  const sq = [...new Set(cohorts.map((r) => r.sanction_quarter))].sort();
  const pq = [...new Set(cohorts.map((r) => r.period_quarter))].sort();
  const exists = new Set(cohorts.map((r) => `${r.sanction_quarter}|${r.period_quarter}`));
  const cell = new Map(grid.map((r) => [`${r.sanction_quarter}|${r.period_quarter}`, r]));
  const maxOld = Math.max(1, ...grid.map((r) => Number(r.old_rule_months)));
  const maxFair = Math.max(1, ...grid.map((r) => Number(r.fair_months)));
  const fix = quarterOf(rule.first_fair_period);

  const paint = (r: any) => {
    const old = Number(r?.old_rule_months ?? 0);
    const fair = Number(r?.fair_months ?? 0);
    const und = Number(r?.undecided_months ?? 0);
    if (old > 0 && fair > 0) return { background: "#e3c67e", color: "var(--ink)", text: `${old}/${fair}` };
    if (old > 0) { const w = old / maxOld; return { background: `rgba(180, 56, 31, ${0.3 + 0.7 * w})`, color: w > 0.45 ? "#fff" : "var(--ink)", text: String(old) }; }
    if (fair > 0) { const w = fair / maxFair; return { background: `rgba(47, 107, 79, ${0.25 + 0.75 * w})`, color: w > 0.45 ? "#fff" : "var(--ink)", text: String(fair) }; }
    if (und > 0) return { background: "var(--paper-2)", color: "var(--ink-2)", text: "?" };
    return { background: "var(--paper-2)", color: "var(--ink-3)", text: "" };
  };

  return (
    <div className="card pad" style={{ overflowX: "auto" }}>
      <table className="heat">
        <thead>
          <tr><th>Sanctioned ↓ · charged →</th>{pq.map((q) => <th key={q}>{q.replace("-", " ")}</th>)}</tr>
        </thead>
        <tbody>
          {sq.map((s) => (
            <tr key={s}>
              <th>{s.replace("-", " ")}</th>
              {pq.map((p) => {
                const key = `${s}|${p}`;
                if (!exists.has(key)) return <td key={p} />;
                const r: any = cell.get(key);
                const c = paint(r);
                const lines = [p === fix ? "inset 2px 0 0 var(--ink)" : "", s === fix ? "inset 0 2px 0 var(--ink)" : ""].filter(Boolean).join(", ");
                return (
                  <td key={p} style={{ background: c.background, color: c.color, boxShadow: lines || undefined }}
                    title={r ? `${n(r.old_rule_months)} on old rule, ${n(r.fair_months)} charged fairly, ${n(r.undecided_months)} undecided` : "No test month: the old rule and fair interest give the same figure"}>
                    {c.text}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="legend-row small muted">
        <span><i className="sw" style={{ background: "rgba(180, 56, 31, 0.75)" }} /> test failed: months on the old rule</span>
        <span><i className="sw" style={{ background: "rgba(47, 107, 79, 0.75)" }} /> test passed: months charged fairly</span>
        <span><i className="sw" style={{ background: "#e3c67e" }} /> both (old rule / fair)</span>
        <span><i className="sw" style={{ background: "var(--paper-2)" }} /> no test, so no evidence. ? means undecided</span>
        {fix && <span><b>Black lines</b> first fair test month, {fix.replace("-", " ")}</span>}
      </div>
      <div className="small" style={{ marginTop: 6 }}>Rows are the quarter loans were sanctioned, columns the quarter interest was charged, both calendar quarters. The first fair test month is the earliest sign of a fix, not its date: the lender confirms that.</div>
    </div>
  );
}

function Actions({ runId, br, rule, loans, qs }: { runId: string; br: string; rule: any; loans?: any[]; qs: string }) {
  const count = Number(rule.loans_to_correct);
  return (
    <div className="card pad" style={{ marginTop: 16 }}>
      <header style={{ marginBottom: 12 }}>
        <h2>What to do</h2>
        <p className="muted small" style={{ margin: "4px 0 0" }}>
          {count > 0
            ? <>{plural(count, "loan")} on this rule to correct in the loan system: {n(rule.open_loans_to_correct)} still open, {n(rule.loans_with_undisbursed)} of them with money still to be paid out. Correcting the system stops future overcharges only. Past overcharges still need refunds, and this page does not track refunds paid.</>
            : <>No loan has been on this rule since the first fair test month. Any earlier overcharges still need refunds, and this page does not track refunds paid.</>}
        </p>
      </header>
      <div className="filters" style={{ margin: 0 }}>
        {count > 0 && <a className="btn" href={`/api/runs/${runId}/fix-coverage/${br}/loans.csv${qs}`}>Export loans to correct</a>}
        <a className="btn ghost" href={`#/review?branch=${br}&convention=${encodeURIComponent(rule.convention_id)}`}>Review these refunds</a>
      </div>
      {count > 0 && loans && (
        <table className="t" style={{ marginTop: 14 }}>
          <thead><tr><th>Loan</th><th className="r">Months on old rule</th><th>Last on old rule</th><th>Status</th><th className="r">Refund owed on loan</th></tr></thead>
          <tbody>
            {loans.map((l) => (
              <tr key={l.loan_id} className="click" onClick={() => go(`/loan/${l.loan_id}`)}>
                <td className="mono small">{l.loan_id}</td>
                <td className="r num">{n(l.old_rule_months)}</td>
                <td className="small">{month(l.last_old_rule_period)}</td>
                <td className="small">{l.loan_status === "ACTIVE" ? "Open" : "Closed"}</td>
                <td className="r">{inr(l.refund_paise)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {count > 25 && <p className="tiny faint" style={{ marginTop: 8 }}>Largest 25 by refund. The export has all {n(count)}.</p>}
    </div>
  );
}
