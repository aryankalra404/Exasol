import { useState } from "react";
import { go, inr, month, n, PRACTICE, REVIEW_WORDS, useApi } from "../lib";

export default function Ledger({ runId, params }: { runId: string; params: URLSearchParams }) {
  const practice = params.get("practice") ?? "";
  const branch = params.get("branch") ?? "";
  const product = params.get("product") ?? "";
  const [q, setQ] = useState(params.get("q") ?? "");
  const [sort, setSort] = useState("excess");
  const [page, setPage] = useState(1);
  const qs = new URLSearchParams({ practice, branch, product, q, sort, page: String(page), size: "50" }).toString();
  const { data, error } = useApi<any>(`/runs/${runId}/ledger?${qs}`, [runId, qs]);
  const meta = useApi<any>(`/runs/${runId}/summary`, [runId]);
  const set = (k: string, v: string) => {
    const p = new URLSearchParams({ practice, branch, product, q });
    if (v) p.set(k, v); else p.delete(k);
    [...p.keys()].forEach((key) => { if (!p.get(key)) p.delete(key); });
    setPage(1);
    go(`/ledger?${p.toString()}`);
  };
  const csv = `/api/runs/${runId}/ledger.csv?${new URLSearchParams({ practice, branch, product, q }).toString()}`;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Refund ledger</h1>
          <p>One row per loan and practice, refundable findings only. Gaps, unexplained and permitted postings are in Work queues.</p>
        </div>
        <div className="filters" style={{ margin: 0 }}>
          <a className="btn ghost" href="#/review">Review and release</a>
          <a className="btn" href={csv}>Export CSV</a>
        </div>
      </div>
      <div className="filters">
        <select value={practice} onChange={(e) => set("practice", e.target.value)}>
          <option value="">All practices</option>
          {["P1", "P2", "P3", "P4", "P5", "AMB"].map((p) => <option key={p} value={p}>{p} · {PRACTICE[p]}</option>)}
        </select>
        <select value={branch} onChange={(e) => set("branch", e.target.value)}>
          <option value="">All branches</option>
          {(meta.data?.branches ?? []).map((b: any) => <option key={b.branch_id} value={b.branch_id}>{b.branch_name}</option>)}
        </select>
        <select value={product} onChange={(e) => set("product", e.target.value)}>
          <option value="">All products</option>
          <option value="HOME">Home</option>
          <option value="PERSONAL">Personal</option>
        </select>
        <input placeholder="Loan ID or borrower name" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && set("q", q)} />
        <select value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="excess">Largest excess first</option>
          <option value="days">Most days first</option>
          <option value="period">Earliest first</option>
          <option value="loan">Loan id</option>
        </select>
        {data && <span className="muted small" style={{ marginLeft: "auto" }}>
          <b className="num" style={{ color: "var(--ink)" }}>{inr(data.total.excess_paise)}</b> across {n(data.total.loans)} loans, {n(data.total.n)} rows
        </span>}
      </div>
      {error && <div className="empty">{error}</div>}
      <div className="card">
        <table className="t">
          <thead><tr><th>Borrower</th><th>Loan</th><th>Branch</th><th>Practice</th><th>Months</th><th className="r">Periods</th><th className="r">Days</th><th className="r">Excess</th><th>Review</th></tr></thead>
          <tbody>
            {(data?.rows ?? []).map((r: any) => (
              <tr key={r.loan_id + r.practice_code} className="click" onClick={() => go(`/loan/${r.loan_id}`)}>
                <td>{r.display_name}</td>
                <td className="mono small">{r.loan_id}</td>
                <td className="small">{r.branch_name}</td>
                <td><span className="tag code">{r.practice_code}</span> <span className="small muted">{PRACTICE[r.practice_code]}</span></td>
                <td className="small">{month(r.first_period)}{r.first_period !== r.last_period ? ` to ${month(r.last_period)}` : ""}</td>
                <td className="r">{r.periods}</td>
                <td className="r">{n(r.days_affected)}</td>
                <td className="r">{inr(r.excess_paise)}</td>
                <td><span className={`tag ${r.review_state}`} title={r.decided_by ? `${r.decided_by}: ${r.review_reason}` : ""}>{REVIEW_WORDS[r.review_state]}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.rows.length === 0 && <div className="empty">No refundable rows for these filters.</div>}
      </div>
      {data && Number(data.total.n) > 50 && (
        <div className="filters" style={{ marginTop: 14, justifyContent: "flex-end" }}>
          <button className="btn ghost" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button>
          <span className="small muted">Page {page} of {Math.ceil(Number(data.total.n) / 50)}</span>
          <button className="btn ghost" disabled={data.rows.length < 50} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      )}
    </>
  );
}
