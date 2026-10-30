import { describeConvention, inr, month, n, PRACTICE, seconds, useApi } from "../lib";

export default function Book({ runId }: { runId: string }) {
  const { data, error } = useApi<any>(`/runs/${runId}/summary`, [runId]);
  if (error) return <div className="empty">{error}</div>;
  if (!data) return <div className="loading">Reading the audit run from Exasol…</div>;
  const s = data.summary;
  const run = data.run;
  const practiceRows = (data.rollups as any[])
    .filter((r) => r.dimension === "practice" && (r.status === "REFUND" || r.status === "AMBIGUOUS"));
  const practiceTitles: Record<string, string> = Object.fromEntries((data.practices as any[]).map((p) => [p.practice_code, p.title]));
  const maxPractice = Math.max(1, ...practiceRows.map((r) => Number(r.excess_paise)));
  const branchRows = (data.rollups as any[]).filter((r) => r.dimension === "branch" && r.status === "REFUND");
  const branchName: Record<string, string> = Object.fromEntries((data.branches as any[]).map((b) => [b.branch_id, b.branch_name]));

  return (
    <>
      <section className="hero">
        <div>
          <div className="upper">Owed back to borrowers, defensible line by line</div>
          <div className="big num">{inr(s.refund_paise)}</div>
          <p className="lede">
            <b>{n(s.refund_loans)} borrowers</b> were charged interest for days before their money reached them,
            or on money they did not have yet. Every loan, every tranche and every billing period in the book was
            recomputed inside Exasol and matched to the paisa against what the loan system posted.
          </p>
        </div>
        <div className="facts">
          <div><div className="v">{n(s.loans_audited)}</div><div className="k">loans audited (whole book)</div></div>
          <div><div className="v">{n(s.periods_audited)}</div><div className="k">billing periods recomputed</div></div>
          <div><div className="v">{n(s.tranches)}</div><div className="k">tranches, money-in-hand resolved</div></div>
          <div><div className="v">{seconds(run.duration_ms)}</div><div className="k">end-to-end inside Exasol, measured</div></div>
        </div>
      </section>

      <section className="section">
        <header>
          <div>
            <h2>Kept out of the total, on purpose</h2>
            <p>An auditor has to defend every rupee. Anything the evidence cannot settle is listed separately, not guessed.</p>
          </div>
        </header>
        <div className="grid g4">
          <a className="tile warn" href="#/queues/gaps">
            <div className="upper">Evidence gaps</div>
            <div className="v">{n(s.gap_tranches)} tranches</div>
            <div className="d">{inr(s.gap_posted_paise, { paise: false })} posted interest at stake. Branch queries drafted.</div>
          </a>
          <a className="tile" href="#/queues/unexplained">
            <div className="upper">Unexplained postings</div>
            <div className="v">{n(s.unexplained_periods)} periods</div>
            <div className="d">{n(s.unexplained_loans)} loans where no known convention reproduces the posting.</div>
          </a>
          <a className="tile slate" href="#/queues/permitted">
            <div className="upper">Permitted, not refunded</div>
            <div className="v">{inr(s.permitted_paise, { paise: false })}</div>
            <div className="d">{n(s.permitted_loans)} loans charging a fee the KFS disclosed. Policy allows it.</div>
          </a>
          <a className="tile" href="#/queues/ambiguous">
            <div className="upper">Ambiguous, counted</div>
            <div className="v">{inr(s.ambiguous_paise, { paise: false })}</div>
            <div className="d">Excess is certain, practice is not unique. Toggle in Policy.</div>
          </a>
        </div>
      </section>

      <section className="section grid g2" style={{ alignItems: "start" }}>
        <div className="card pad">
          <header style={{ marginBottom: 16 }}>
            <h2>By RBI practice</h2>
            <p className="muted small" style={{ margin: "4px 0 0" }}>Excess split exactly across practices; the parts add up to the total to the paisa.</p>
          </header>
          <div className="bars">
            {practiceRows.map((r) => (
              <a key={r.dim_value + r.status} className="bar-row" href={`#/ledger?practice=${r.dim_value}`} style={{ textDecoration: "none" }}>
                <span className="code">{r.dim_value}</span>
                <div>
                  <div className="label">{practiceTitles[r.dim_value] ?? PRACTICE[r.dim_value] ?? r.dim_value}</div>
                  <div className="bar-track"><div className="bar-fill" style={{ width: `${(100 * Number(r.excess_paise)) / maxPractice}%` }} /></div>
                </div>
                <div className="amt">
                  {inr(r.excess_paise, { paise: false })}
                  <div className="tiny faint">{n(r.loans)} loans</div>
                </div>
              </a>
            ))}
          </div>
        </div>
        <div className="card pad">
          <header style={{ marginBottom: 12 }}>
            <h2>By branch</h2>
            <p className="muted small" style={{ margin: "4px 0 0" }}>Refundable excess. Click a branch to see its cohorts.</p>
          </header>
          <table className="t">
            <thead><tr><th>Branch</th><th className="r">Loans</th><th className="r">Excess</th></tr></thead>
            <tbody>
              {branchRows.sort((a, b) => Number(b.excess_paise) - Number(a.excess_paise)).map((r) => (
                <tr key={r.dim_value} className="click" onClick={() => (window.location.hash = `#/regression/${r.dim_value}`)}>
                  <td>{branchName[r.dim_value]} <span className="faint mono tiny">{r.dim_value}</span></td>
                  <td className="r">{n(r.loans)}</td>
                  <td className="r">{inr(r.excess_paise, { paise: false })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <header>
          <div>
            <h2>What the loan system was actually doing</h2>
            <p>Each row is one behaviour of the lender's system, identified only from its own postings: the convention that reproduces them to the paisa. One configuration fix closes the whole row.</p>
          </div>
        </header>
        <div className="card">
          <table className="t">
            <thead>
              <tr><th>Branch</th><th>Behaviour found in the postings</th><th>Practice</th><th className="r">Loans</th>
                <th>Periods charged</th><th>Loans sanctioned</th><th className="r">Excess</th></tr>
            </thead>
            <tbody>
              {(data.root_causes as any[]).map((r) => (
                <tr key={r.branch_id + r.convention_id} className="click"
                  onClick={() => (window.location.hash = `#/ledger?branch=${r.branch_id}`)}>
                  <td>{r.branch_name}<div className="faint mono tiny">{r.branch_id}</div></td>
                  <td>{describeConvention(r.convention_id)}<div className="faint mono tiny">{r.convention_id}</div></td>
                  <td>{String(r.practice_codes ?? "").split(",").map((p: string) => <span key={p} className="tag code" style={{ marginRight: 4 }}>{p}</span>)}</td>
                  <td className="r">{n(r.loans)}</td>
                  <td className="small">{month(r.first_period)} to {month(r.last_period)}</td>
                  <td className="small">{month(r.earliest_sanction)} to {month(r.latest_sanction)}</td>
                  <td className="r">{inr(r.excess_paise, { paise: false })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <header>
          <div>
            <h2>How this run was computed</h2>
            <p>Nine SQL steps in Exasol, timed on this machine. Click a step to read the statement that produced its numbers.</p>
          </div>
          <a className="btn ghost" href="#/method">Open method</a>
        </header>
        <div className="card">
          <table className="t">
            <thead><tr><th>Step</th><th>What it does</th><th className="r">Time</th></tr></thead>
            <tbody>
              {(data.steps as any[]).map((st) => (
                <tr key={st.sql_step_id} className="click" onClick={() => (window.location.hash = `#/method/${st.sql_step_id}`)}>
                  <td className="mono small">{st.sql_step_id}</td>
                  <td className="small muted">{String(st.description).split(". ")[0]}</td>
                  <td className="r">{n(st.duration_ms)} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
