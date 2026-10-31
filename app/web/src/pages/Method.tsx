import { go, sentence, useApi } from "../lib";

export default function Method({ runId, step }: { runId: string; step?: string }) {
  const sum = useApi<any>(`/runs/${runId}/summary`, [runId]).data;
  const sel = step ?? "S70_FINGERPRINT";
  const { data } = useApi<any>(`/lineage/${sel}`, [sel]);
  const steps: any[] = sum?.steps ?? [];
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Method</h1>
          <p>
            The audit is nine SQL files run in order inside Exasol. Each finding records the step that produced it, and each step
            records the SHA-256 of its SQL, so any number on screen can be traced to the exact statement that computed it.
          </p>
        </div>
      </div>
      <div className="grid" style={{ gridTemplateColumns: "300px minmax(0, 1fr)", alignItems: "start" }}>
        <div className="card">
          <table className="t">
            <tbody>
              {steps.map((s) => (
                <tr key={s.sql_step_id} className={`click ${s.sql_step_id === sel ? "sel" : ""}`} onClick={() => go(`/method/${s.sql_step_id}`)}>
                  <td><div className="mono small">{s.sql_step_id}</div><div className="tiny faint">{s.file_path}</div></td>
                  <td className="r small">{s.duration_ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          {data && (
            <>
              <div className="card pad" style={{ marginBottom: 12 }}>
                <h3 className="mono">{data.sql_step_id} · {data.file_path}</h3>
                <p className="small muted" style={{ margin: "6px 0" }}>{sentence(data.description)}</p>
                <div className="tiny faint mono">sha256 {data.statement_sha}</div>
              </div>
              <pre className="sql">{data.sql}</pre>
            </>
          )}
        </div>
      </div>
      <section className="section card pad">
        <h2>Rules the SQL implements</h2>
        <ul className="small" style={{ lineHeight: 1.7, color: "var(--ink-2)" }}>
          <li>Money is integer paise. Each interval's interest is an exact integer numerator, balance × rate × days. Each month is divided and rounded half up once. No floating-point arithmetic.</li>
          <li>Interest accrues from the money-in-hand date: for cheques, the later of handover and cheque date; for NEFT, RTGS and IMPS, the rail credit date. Without that evidence the period becomes an evidence gap.</li>
          <li>33 candidate conventions: 4 start dates × 2 principal bases × 2 advance-EMI treatments × 2 month roundings, plus a disclosed commitment fee. Each differs from fair only on the days its balance differs, so all of them are computed side by side in one pass.</li>
          <li>The convention that reproduces the lender's posting to the paisa names the practice. Ties are broken by the loan's own posting history, then by the fewest unfair dimensions. A posting nothing reproduces is unexplained.</li>
          <li>Excess is always posted minus fair. Attribution only labels it, splitting it across practices in a fixed order so the parts sum to the excess exactly.</li>
          <li>An independent Python oracle, sharing no code with the SQL, recomputes every loan day by day and must agree to the paisa.</li>
        </ul>
      </section>
    </>
  );
}
