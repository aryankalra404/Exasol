import { describeConvention, go, inr, month, n, useApi } from "../lib";

export default function Regression({ runId, branch }: { runId: string; branch?: string }) {
  const meta = useApi<any>(`/runs/${runId}/summary`, [runId]).data;
  const br = branch ?? "BR001";
  const { data } = useApi<any[]>(`/runs/${runId}/cohorts?branch=${br}`, [runId, br]);
  const causes = (meta?.root_causes ?? []).filter((r: any) => r.branch_id === br);
  const sq = [...new Set((data ?? []).map((r) => r.sanction_quarter))].sort();
  const pq = [...new Set((data ?? []).map((r) => r.period_quarter))].sort();
  const cell = new Map((data ?? []).map((r) => [`${r.sanction_quarter}|${r.period_quarter}`, r]));
  const maxCount = Math.max(1, ...(data ?? []).map((r) => Number(r.loans_overcharged)));
  const name = meta?.branches?.find((b: any) => b.branch_id === br)?.branch_name ?? br;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Was it fixed for everyone, or only for new loans?</h1>
          <p>
            Rows are loans grouped by the quarter they were sanctioned; columns are the quarter interest was charged. A dark cell
            means loans in that cohort were still being overcharged then. A fix applied only to new loans shows as old cohorts
            that stay dark after newer ones turn clear.
          </p>
        </div>
        <select value={br} onChange={(e) => go(`/regression/${e.target.value}`)}
          style={{ font: "inherit", padding: "7px 10px", border: "1px solid var(--rule)", borderRadius: 6, background: "var(--card)", minWidth: 260 }}>
          {(meta?.branches ?? []).map((b: any) => <option key={b.branch_id} value={b.branch_id}>{b.branch_name} ({b.branch_id})</option>)}
        </select>
      </div>

      {!meta && <div className="loading">Reading root causes…</div>}
      {meta && causes.length === 0 && <div className="verdict ok" style={{ marginBottom: 20 }}>No refundable behaviour found at {name} in this run.</div>}
      {causes.length > 0 && (
        <div className="grid" style={{ marginBottom: 20 }}>
          {causes.map((c: any) => (
            <div key={c.convention_id} className="verdict">
              <b>{name}</b>: {describeConvention(c.convention_id).toLowerCase()} on <b>{n(c.loans)} loans</b> sanctioned
              {" "}{month(c.earliest_sanction)} to {month(c.latest_sanction)}, still charged up to <b>{month(c.last_period)}</b>.
              {" "}Excess {inr(c.excess_paise)}.
            </div>
          ))}
        </div>
      )}

      <div className="card pad" style={{ overflowX: "auto" }}>
        {!data ? <div className="loading">Loading…</div> : (
          <table className="heat">
            <thead>
              <tr><th>Sanctioned ↓ · charged →</th>{pq.map((q) => <th key={q}>{q.replace("-", " ")}</th>)}</tr>
            </thead>
            <tbody>
              {sq.map((s) => (
                <tr key={s}>
                  <th>{s.replace("-", " ")}</th>
                  {pq.map((p) => {
                    const r: any = cell.get(`${s}|${p}`);
                    if (!r) return <td key={p} />;
                    const w = Number(r.loans_overcharged) / maxCount;
                    const bg = r.loans_overcharged > 0 ? `rgba(180, 56, 31, ${0.25 + 0.75 * w})` : "var(--ok-soft)";
                    return (
                      <td key={p} style={{ background: bg, color: w > 0.5 ? "#fff" : "var(--ink)" }}
                        title={`${r.loans_overcharged} of ${r.loans_in_cohort} loans overcharged · ${inr(r.excess_paise)}`}>
                        {r.loans_overcharged > 0 ? r.loans_overcharged : ""}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="tiny muted" style={{ marginTop: 12 }}>Cell number: loans overcharged in that quarter. Green: billed, nothing overcharged. Hover for amounts.</div>
      </div>
    </>
  );
}
