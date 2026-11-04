import { day, describeConvention, inr, MODE_WORDS, month, plural, sources, SOURCE_LONG, useApi } from "../lib";

const ABOUT: Record<string, { title: string; why: string }> = {
  evidence: { title: "Dates on record", why: "Every date any system holds for each tranche, and where it is stored." },
  entered_evidence: { title: "Dates entered from branch replies", why: "Entered by a person with a reference and a reason. The re-run decided the result." },
  postings: { title: "Interest the loan system posted", why: "What the borrower was actually charged for this month. In paise." },
  tranches: { title: "Tranches", why: "How much was paid out, how, and to whom. In paise." },
  rates: { title: "Rate history", why: "The rates in force up to the end of this month." },
  kfs: { title: "Key Facts Statement", why: "What was disclosed to the borrower. A disclosed term is not treated as unfair." },
  loan: { title: "Loan", why: "Sanction and agreement dates, the starting points the rules are tested against." },
  receipts: { title: "Repayments", why: "Received in this month, plus any advance instalment. In paise." },
};
const FIRST = ["evidence", "entered_evidence", "postings"];

function ruleWords(t: any): string {
  const steps = (t.precedence ?? []).map((p: any) => {
    const name = SOURCE_LONG[p.evidence_source] ?? p.evidence_source;
    if (p.rule === "MAX_WITH_CHEQUE_DATE") return `${name}, never before the cheque date`;
    if (p.rule === "FALLBACK") return `the ${name} if the policy allows it`;
    return name;
  });
  return steps.join(", otherwise ");
}

function RecordTable({ record, deciding, changed }: { record: any; deciding: Set<string>; changed: boolean }) {
  const about = ABOUT[record.key] ?? { title: record.table, why: "" };
  const idAt = record.columns.findIndex((c: string) => c === "evidence_id");
  const stale = changed && record.key === "postings";
  return (
    <div className="card" style={{ marginTop: 10 }}>
      <div className="pad" style={{ paddingBottom: 6 }}>
        <h3>{about.title} <span className="faint mono tiny">{record.table}</span></h3>
        <div className="small muted">{about.why}</div>
      </div>
      <div style={{ overflowX: "auto" }}>
        {record.rows.length === 0 ? <div className="pad small muted">No rows.</div> : (
          <table className="t">
            <thead><tr>{record.columns.map((c: string) => <th key={c} className="mono tiny">{c}</th>)}{idAt >= 0 && <th />}</tr></thead>
            <tbody>
              {record.rows.map((row: any[], i: number) => {
                const decides = idAt >= 0 && deciding.has(row[idAt]);
                return (
                  <tr key={i} style={stale ? { background: "var(--warn-soft)" } : decides ? { background: "var(--ok-soft)" } : undefined}>
                    {row.map((v, j) => (
                      <td key={j} className="mono tiny nowrap">{v === null ? <span className="faint">NULL</span> : String(v)}</td>
                    ))}
                    {idAt >= 0 && <td className="nowrap">{decides && <span className="tag FAIR">Sets the date</span>}</td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <details className="pad" style={{ paddingTop: 8, paddingBottom: 10 }}>
        <summary className="tiny muted">The statement that read these rows</summary>
        <pre className="sql" style={{ marginTop: 8 }}>{record.sql}</pre>
      </details>
    </div>
  );
}

function TrancheStep({ t, evidence, deciding }: { t: any; evidence: any[]; deciding: Set<string> }) {
  const head = `Tranche ${t.tranche_no}, ${MODE_WORDS[t.payment_mode] ?? t.payment_mode}`;
  if (t.confidence === "GAP") {
    return <li>{head}: no date can be confirmed. Missing: <b>{sources(t.missing_sources)}</b>. The rule asks for the {ruleWords(t)}.</li>;
  }
  const row = evidence.find((e) => e.tranche_no === t.tranche_no && deciding.has(e.evidence_id));
  return (
    <li>
      {head}: the rule asks for the {ruleWords(t)}. Money in hand <b>{day(t.resolved_date)}</b>{row && <>, from <span className="mono">{row.evidence_id}</span></>}.
      {t.confidence === "FALLBACK" && " No rail credit record, so this is the loan system's own date."}
      {t.conflict_flag && row && row.recorded_in !== "LMS" && <> The records disagree, and the date that decides this is held in <b className="mono">{row.recorded_in}</b>, outside the loan system.</>}
    </li>
  );
}

function outcome(status: string, d: any, sel: any) {
  const reason = d.findings[0]?.reason;
  switch (status) {
    case "MATCHED": return <>The posting is reproduced <b>exactly, to the paisa</b>, by one rule: <b>{describeConvention(sel.matched_convention_id)}</b>. Refund for this month: <b>{inr(d.refund_paise)}</b>.</>;
    case "FAIR": return <>The posting equals fair interest. <b>Nothing to refund.</b></>;
    case "PERMITTED": return <>{reason}</>;
    case "AMBIGUOUS": return <>{reason}</>;
    case "EVIDENCE_GAP": return <>{reason}</>;
    case "UNEXPLAINED": return <>{reason} <b>Sent to a person, and not refunded.</b></>;
    case "UNDERCHARGE": return <>{reason} <b>Listed, never refunded.</b></>;
    default: return <>{reason}</>;
  }
}

export default function SourceRecords({ runId, loanId, sel }: { runId: string; loanId: string; sel: any }) {
  const { data, error } = useApi<any>(`/runs/${runId}/loans/${loanId}/source/${sel.period_start}`, []);
  if (error) return <div className="verdict warn" style={{ marginTop: 14 }}>{error}</div>;
  if (!data) return <div className="loading">Reading the source rows from Exasol…</div>;

  const deciding = new Set<string>(data.deciding_evidence_ids);
  const d = data.decision;
  const fp = d.fingerprint;
  const records: any[] = data.records;
  const evidence = records.filter((r) => r.key === "evidence" || r.key === "entered_evidence").flatMap((r) =>
    r.rows.map((row: any[]) => Object.fromEntries(r.columns.map((c: string, i: number) => [c, row[i]]))));
  const count = records.reduce((a, r) => a + r.rows.length, 0);
  const postingIds = String(fp.posting_ids ?? "").split(",").filter(Boolean).join(", ");
  const later = records.filter((r) => !FIRST.includes(r.key));
  const f = data.freshness;

  return (
    <div style={{ marginTop: 14 }}>
      {!f.same_extract && <div className="verdict warn" style={{ marginBottom: 10 }}>A different book is loaded now. These rows are from that book, not the one run on {day(data.run.started_at)} audited.</div>}
      {f.same_extract && !f.posted_matches && <div className="verdict warn" style={{ marginBottom: 10 }}>The stored posting has changed since this run. The run audited <b>{inr(f.posted_in_run)}</b>, and the table now holds <b>{inr(f.posted_now)}</b>. Re-run the audit to decide on the current records.</div>}

      <div className="card pad">
        <h3>How these records became this decision: {month(sel.period_start)}</h3>
        <ol className="small" style={{ margin: "10px 0 0", paddingLeft: 20, lineHeight: 1.7 }}>
          {d.tranches.map((t: any) => <TrancheStep key={t.tranche_no} t={t} evidence={evidence} deciding={deciding} />)}
          <li>The loan system posted <b>{inr(fp.posted_paise)}</b>{postingIds && <> (<span className="mono">{postingIds}</span>)</>}. {fp.match_status === "EVIDENCE_GAP" ? "Provisional fair interest" : "Fair interest from those dates"} is <b>{inr(fp.fair_paise)}</b>, a difference of <b>{inr(fp.excess_paise)}</b>.</li>
          <li>{outcome(fp.match_status, d, fp)}</li>
        </ol>
        <div className="tiny faint" style={{ marginTop: 10 }}>
          {plural(count, "row")} read from Exasol just now, shown as stored. Raw tables hold the loaded extract, not a copy per run{f.same_extract && f.posted_matches ? "; the posted total matches what this run audited" : ""}.
        </div>
      </div>

      {records.filter((r) => FIRST.includes(r.key)).map((r) => <RecordTable key={r.key} record={r} deciding={deciding} changed={!f.posted_matches} />)}

      <details style={{ marginTop: 10 }}>
        <summary className="small muted">Other records the calculation used: tranches, rates, Key Facts Statement, loan, repayments</summary>
        {later.map((r) => <RecordTable key={r.key} record={r} deciding={deciding} changed={!f.posted_matches} />)}
        <div className="small muted" style={{ marginTop: 10 }}>Before this month: {plural(data.earlier_receipts.receipts, "receipt")}, with {inr(data.earlier_receipts.principal_paise)} of principal.</div>
      </details>
    </div>
  );
}
