import { useEffect, useState } from "react";
import { go, inr, n, OUTCOME_WORDS, useApi } from "../lib";

const ORDER = ["FAIR", "REFUND", "PERMITTED", "EVIDENCE_GAP", "UNEXPLAINED", "UNDERCHARGE"];
const SIZE = 50;

const HELP: Record<string, string> = {
  FAIR: "Every month the loan system posted matches the interest recomputed from the day the money reached the borrower. Checked, nothing to do.",
  REFUND: "At least one month was overcharged. Approve these in Review and release.",
  PERMITTED: "The loan system charged a term the KFS disclosed, and policy allows it. No refund.",
  EVIDENCE_GAP: "No refund is owed so far, but a date cannot be decided yet. Work queues holds the query to each branch.",
  UNEXPLAINED: "No refund is owed so far, but no known method reproduces at least one posting. Needs investigation in Work queues.",
  UNDERCHARGE: "The lender posted less than the fair amount in at least one month. Nothing to refund.",
};

export default function Loans({ runId, outcome }: { runId: string; outcome: string }) {
  const [page, setPage] = useState(1);
  const [branch, setBranch] = useState("");
  useEffect(() => setPage(1), [runId, outcome, branch]);
  const counts = useApi<any>(`/runs/${runId}/outcomes`, [runId]).data?.outcomes as any[] | undefined;
  const meta = useApi<any>(`/runs/${runId}/summary`, [runId]).data;
  const qs = new URLSearchParams({ branch, page: String(page), size: String(SIZE) }).toString();
  const { data, error } = useApi<any[]>(`/runs/${runId}/outcomes/${outcome}?${qs}`, [runId, outcome, qs]);
  const total = Number(data?.[0]?.total_rows ?? 0);
  const last = Math.max(1, Math.ceil(total / SIZE));
  return (
    <>
      <div className="page-head">
        <div>
          <h1>All loans</h1>
          <p>Every audited loan has one outcome. A loan owed money counts as a refund, even if another of its months is still open.</p>
        </div>
      </div>
      <div className="tabs">
        {ORDER.map((k) => (
          <a key={k} href={`#/loans/${k}`} className={outcome === k ? "on" : ""}>
            {OUTCOME_WORDS[k]}<span className="count">{n(counts?.find((c) => c.outcome === k)?.loans ?? 0)}</span>
          </a>
        ))}
      </div>
      <p className="muted" style={{ marginTop: 0 }}>{HELP[outcome]}</p>
      <div className="filters">
        <select aria-label="Branch" value={branch} onChange={(e) => setBranch(e.target.value)}>
          <option value="">All branches</option>
          {(meta?.branches ?? []).map((b: any) => <option key={b.branch_id} value={b.branch_id}>{b.branch_name}</option>)}
        </select>
        <span className="muted small" style={{ marginLeft: "auto" }}>{n(total)} loans</span>
      </div>
      {error && <div className="empty">{error}</div>}
      <div className="card">
        <table className="t">
          <thead><tr><th>Borrower</th><th>Loan</th><th>Branch</th><th className="r">Months audited</th><th className="r">Posted</th><th className="r">Fair</th><th className="r">Refund</th></tr></thead>
          <tbody>
            {(data ?? []).map((r) => (
              <tr key={r.loan_id} className="click" onClick={() => go(`/loan/${r.loan_id}`)}>
                <td>{r.display_name}</td>
                <td className="mono small">{r.loan_id}</td>
                <td className="small">{r.branch_name}</td>
                <td className="r">{n(r.months)}</td>
                <td className="r">{inr(r.posted_paise)}</td>
                <td className="r">{inr(r.fair_paise)}</td>
                <td className="r">{inr(r.refund_paise)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.length === 0 && <div className="empty">No loans here.</div>}
      </div>
      {total > SIZE && (
        <div className="filters" style={{ marginTop: 14, justifyContent: "flex-end" }}>
          <button className="btn ghost" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button>
          <span className="small muted">Page {page} of {last}</span>
          <button className="btn ghost" disabled={page >= last} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      )}
    </>
  );
}
