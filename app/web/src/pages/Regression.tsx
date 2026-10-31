import { describeConvention, go, inr, month, plural, useApi } from "../lib";

export default function Regression({ runId, branch }: { runId: string; branch?: string }) {
  const meta = useApi<any>(`/runs/${runId}/summary`, [runId]).data;
  const br = branch ?? defaultBranch(meta?.root_causes ?? []);
  const { data } = useApi<any[]>(br ? `/runs/${runId}/cohorts?branch=${br}` : null, [runId, br]);
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
          <p>Shows whether a loan-system fix reached loans already on the book, or only loans sanctioned after it.</p>
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
              <b>{plural(c.loans, "loan")}</b> sanctioned {month(c.earliest_sanction) === month(c.latest_sanction) ? `in ${month(c.earliest_sanction)}` : `${month(c.earliest_sanction)} to ${month(c.latest_sanction)}`}
              {" "}charged interest {describeConvention(c.convention_id).toLowerCase()}, last in <b>{month(c.last_period)}</b>.
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
        <div className="legend-row small muted">
          <span><b>Rows</b> quarter the loans were sanctioned</span>
          <span><b>Columns</b> quarter interest was charged</span>
          <span><i className="sw" style={{ background: "rgba(180, 56, 31, 0.75)" }} /> loans overcharged (number shown, hover for amount)</span>
          <span><i className="sw" style={{ background: "var(--ok-soft)" }} /> charged correctly</span>
        </div>
        <div className="small" style={{ marginTop: 6 }}>If older rows stay red after newer rows turn green, the fix covered only new loans.</div>
      </div>
    </>
  );
}

/** Open on the branch where overcharging went on longest after the last affected loan was sanctioned:
 *  the clearest sign of a fix that reached new loans but not old ones. Picks a branch, computes no figure. */
function defaultBranch(causes: any[]): string {
  const gap = (c: any) => Date.parse(c.last_period) - Date.parse(c.latest_sanction);
  const best = [...causes].sort((a, b) => gap(b) - gap(a))[0];
  return best?.branch_id ?? "";
}
