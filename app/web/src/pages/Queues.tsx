import { useEffect, useState } from "react";
import { day, describeConvention, go, inr, MODE_WORDS, month, n, plural, post, REVIEW_WORDS, sources, useApi, useReviewer } from "../lib";
import { ActorFields, missingActor, Toast } from "./Review";

const TABS: [string, string, string][] = [
  ["gaps", "Evidence gaps", "The money-in-hand date cannot be decided. A query to the branch is drafted for each."],
  ["unexplained", "Unexplained", "No known calculation method reproduces the posted amount. Needs manual review."],
  ["ambiguous", "Ambiguous", "The overcharge is certain, but more than one practice explains it equally well. When counted in the total, approve these in Review and release, as practice AMB."],
  ["permitted", "Permitted", "The posting matches a term the KFS disclosed, and policy allows it. No refund."],
  ["undercharge", "Undercharge", "The lender posted less than the fair amount. Nothing to refund; listed for completeness."],
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
          <p>Items the audit could not resolve automatically. Each one says what is missing and why it is not in the refund total.</p>
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

const GAPS_PER_PAGE = 20;
const ROWS_PER_PAGE = 50;

function Pager({ page, size, total, onPage, noun }: { page: number; size: number; total: number; onPage: (p: number) => void; noun: string }) {
  const last = Math.max(1, Math.ceil(total / size));
  const from = total ? (page - 1) * size + 1 : 0;
  const to = Math.min(page * size, total);
  return (
    <div className="pager">
      <span className="small muted">Showing {n(from)}–{n(to)} of {plural(total, noun)}</span>
      <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button className="btn ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
        <span className="small muted">Page {page} of {last}</span>
        <button className="btn ghost" disabled={page >= last} onClick={() => onPage(page + 1)}>Next</button>
      </span>
    </div>
  );
}

function Gaps({ runId }: { runId: string }) {
  const { data } = useApi<any[]>(`/runs/${runId}/gaps`, [runId]);
  const [copied, setCopied] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [branch, setBranch] = useState("");
  useEffect(() => setPage(1), [runId, branch]);
  if (!data) return <div className="loading">Loading…</div>;
  if (!data.length) return <div className="empty">No evidence gaps in this run.</div>;
  const branches = [...new Map(data.map((g) => [g.branch_id, g.branch_name])).entries()].sort((a, b) => a[1].localeCompare(b[1]));
  const shown = branch ? data.filter((g) => g.branch_id === branch) : data;
  const pageRows = shown.slice((page - 1) * GAPS_PER_PAGE, page * GAPS_PER_PAGE);
  const toPage = (p: number) => { setPage(p); window.scrollTo({ top: 0 }); };
  return (
    <>
    <div className="filters" style={{ marginBottom: 12 }}>
      <select value={branch} onChange={(e) => setBranch(e.target.value)}>
        <option value="">All branches</option>
        {branches.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select>
    </div>
    <Pager page={page} size={GAPS_PER_PAGE} total={shown.length} onPage={toPage} noun="tranche" />
    <div className="grid g2">
      {pageRows.map((g) => (
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
    <Pager page={page} size={GAPS_PER_PAGE} total={shown.length} onPage={toPage} noun="tranche" />
    </>
  );
}

function FindingQueue({ runId, status }: { runId: string; status: string }) {
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [runId, status]);
  const [ver, setVer] = useState(0);
  const [name, setName] = useReviewer();
  const [why, setWhy] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const { data } = useApi<any[]>(`/runs/${runId}/queue/${status}?page=${page}&size=${ROWS_PER_PAGE}`, [runId, status, page, ver]);
  const unexplained = status === "UNEXPLAINED";
  const decide = async (r: any, decision: string) => {
    const missing = missingActor(name, why);
    if (missing) { setErr(missing); return; }
    setErr(null);
    try {
      await post(`/runs/${r.run_id}/review/unexplained`, { loan_id: r.loan_id, period_start: r.period_start, decision, reviewer: name, reason: why });
      setVer((v) => v + 1);
    } catch (e: any) { setErr(e.message); }
  };
  if (!data) return <div className="loading">Loading…</div>;
  if (!data.length) return <div className="empty">Nothing in this queue for this run.</div>;
  const total = Number(data[0].total_rows ?? data.length);
  const onPage = (p: number) => { setPage(p); window.scrollTo({ top: 0 }); };
  return (
    <>
    {unexplained && (
      <>
        <p className="small muted" style={{ marginTop: 0 }}>Record the outcome of a manual look. This moves no money: to change a refund, correct the evidence or the policy and re-run.</p>
        <ActorFields name={name} setName={setName} reason={why} setReason={setWhy} why="What did you find?" sticky />
        <Toast err={err} onClose={() => setErr(null)} />
      </>
    )}
    <div className="card">
      <div className="pad" style={{ borderBottom: "1px solid var(--rule-2)", paddingTop: 10, paddingBottom: 10 }}>
        <Pager page={page} size={ROWS_PER_PAGE} total={total} onPage={onPage} noun="billing month" />
      </div>
      <table className="t">
        <thead><tr><th>Borrower</th><th>Loan</th><th>Month</th><th className="r">Posted</th><th className="r">Fair</th><th className="r">Difference</th><th>Why it is here</th>{unexplained && <th>Review</th>}</tr></thead>
        <tbody>
          {data.map((r) => (
            <tr key={r.loan_id + r.period_start + (r.practice_code ?? "")} className="click" onClick={() => go(`/loan/${r.loan_id}?period=${r.period_start}`)}>
              <td>{r.display_name}</td>
              <td className="mono small">{r.loan_id}</td>
              <td className="small">{month(r.period_start)}</td>
              <td className="r">{inr(r.posted_paise)}</td>
              <td className="r">{inr(r.fair_paise)}</td>
              <td className="r">{inr(r.excess_paise)}</td>
              <td className="small muted" style={{ maxWidth: 420 }}>{reason(r)}</td>
              {unexplained && (
                <td className="small" onClick={(e) => e.stopPropagation()}>
                  <span className={`tag ${r.review_state}`}>{REVIEW_WORDS[r.review_state]}</span>
                  {r.decided_by && <div className="tiny faint" title={r.review_reason}>{r.decided_by}: {r.review_reason}</div>}
                  <div className="nowrap" style={{ marginTop: 4 }}>
                    <button className="btn mini" onClick={() => decide(r, "CLEARED")}>Clear</button>{" "}
                    <button className="btn ghost mini" onClick={() => decide(r, "HOLD")}>Hold</button>
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="pad" style={{ borderTop: "1px solid var(--rule-2)", paddingTop: 10, paddingBottom: 10 }}>
        <Pager page={page} size={ROWS_PER_PAGE} total={total} onPage={onPage} noun="billing month" />
      </div>
    </div>
    </>
  );
}

/** The SQL reason, with the closest method and gap shown in words and rupees for the unexplained queue. */
function reason(r: any): string {
  if (r.closest_convention_id && r.closest_diff_paise !== null && r.closest_diff_paise !== undefined && String(r.reason).startsWith("No known")) {
    const off = inr(String(r.closest_diff_paise).replace("-", ""));
    return `No known calculation method reproduces the posted amount. Closest: ${describeConvention(r.closest_convention_id).toLowerCase()}, off by ${off}.${r.has_manual ? " A manual journal entry was posted for this month." : ""}`;
  }
  return r.reason;
}
