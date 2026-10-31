import { useState } from "react";
import { day, go, inr, MODE_WORDS, month, n, plural, sources, useApi } from "../lib";

const TABS: [string, string, string][] = [
  ["gaps", "Evidence gaps", "The money-in-hand date cannot be decided. A query to the branch is drafted for each."],
  ["unexplained", "Unexplained", "No recognised convention reproduces the posting. Needs a person, not a guess."],
  ["ambiguous", "Ambiguous", "Excess is known; more than one practice explains it equally well."],
  ["permitted", "Permitted", "The posting matches a term the KFS disclosed, and policy allows it. No refund."],
  ["undercharge", "Undercharge", "Posted less than fair. Not refundable; listed so nothing is silently dropped."],
];

export default function Queues({ runId, tab }: { runId: string; tab: string }) {
  const s = useApi<any>(`/runs/${runId}/summary`, [runId]).data?.summary;
  const counts: Record<string, string> = s ? {
    gaps: n(s.gap_tranches), unexplained: n(s.unexplained_periods), undercharge: n(s.undercharge_periods),
  } : {};
  const info = TABS.find((t) => t[0] === tab) ?? TABS[0];
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Work queues</h1>
          <p>What the audit could not settle on its own. Each item says what is missing and why it is held out of the refund total.</p>
        </div>
      </div>
      <div className="tabs">
        {TABS.map(([k, label]) => <a key={k} href={`#/queues/${k}`} className={tab === k ? "on" : ""}>{label}{counts[k] && <span className="count">{counts[k]}</span>}</a>)}
      </div>
      <p className="muted" style={{ marginTop: 0 }}>{info[2]}</p>
      {tab === "gaps" ? <Gaps runId={runId} /> : <FindingQueue runId={runId} status={{ unexplained: "UNEXPLAINED", ambiguous: "AMBIGUOUS", permitted: "PERMITTED", undercharge: "UNDERCHARGE" }[tab] ?? "UNEXPLAINED"} />}
    </>
  );
}

function Gaps({ runId }: { runId: string }) {
  const { data } = useApi<any[]>(`/runs/${runId}/gaps`, [runId]);
  const [copied, setCopied] = useState<string | null>(null);
  if (!data) return <div className="loading">Loading…</div>;
  if (!data.length) return <div className="empty">No evidence gaps in this run.</div>;
  return (
    <div className="grid g2">
      {data.map((g) => (
        <div key={g.loan_id + g.tranche_no} className="card pad">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <div>
              <a href={`#/loan/${g.loan_id}`} style={{ fontWeight: 600 }}>{g.display_name}</a>
              <div className="mono small faint" style={{ marginTop: 2 }}>{g.loan_id} · tranche {g.tranche_no} · {MODE_WORDS[g.payment_mode] ?? g.payment_mode} · {inr(g.amount_paise, { paise: false })}</div>
            </div>
            <span className="tag EVIDENCE_GAP" style={{ whiteSpace: "nowrap", alignSelf: "flex-start" }}>Missing {sources(g.missing_source)}</span>
          </div>
          <div className="small muted" style={{ marginTop: 6 }}>
            {g.branch_name} · uncertainty window {day(g.window_start)} to {day(g.window_end)} · {plural(g.periods_affected, "month")} held, {inr(g.posted_paise_at_stake)} posted interest at stake
          </div>
          <div className="query">{g.suggested_query}</div>
          <div style={{ marginTop: 8, display: "flex", justifyContent: "flex-end" }}>
            <button className="copy" onClick={() => { navigator.clipboard?.writeText(g.suggested_query); setCopied(g.loan_id + g.tranche_no); }}>
              {copied === g.loan_id + g.tranche_no ? "Copied" : "Copy query"}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function FindingQueue({ runId, status }: { runId: string; status: string }) {
  const { data } = useApi<any[]>(`/runs/${runId}/queue/${status}?limit=300`, [runId, status]);
  if (!data) return <div className="loading">Loading…</div>;
  if (!data.length) return <div className="empty">Nothing in this queue for this run.</div>;
  return (
    <div className="card">
      <div className="pad small muted" style={{ borderBottom: "1px solid var(--rule-2)" }}>{plural(data.length, "month")}{data.length >= 300 ? " (first 300 shown)" : ""}. Select a row to see the working.</div>
      <table className="t">
        <thead><tr><th>Borrower</th><th>Loan</th><th>Month</th><th className="r">Posted</th><th className="r">Fair</th><th className="r">Difference</th><th>Why it is here</th></tr></thead>
        <tbody>
          {data.map((r) => (
            <tr key={r.loan_id + r.period_start + (r.practice_code ?? "")} className="click" onClick={() => go(`/loan/${r.loan_id}?period=${r.period_start}`)}>
              <td>{r.display_name}</td>
              <td className="mono small">{r.loan_id}</td>
              <td className="small">{month(r.period_start)}</td>
              <td className="r">{inr(r.posted_paise)}</td>
              <td className="r">{inr(r.fair_paise)}</td>
              <td className="r">{inr(r.excess_paise)}</td>
              <td className="small muted" style={{ maxWidth: 420 }}>{r.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
