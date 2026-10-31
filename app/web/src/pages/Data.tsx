import { useRef, useState } from "react";
import { api, day, go, n, seconds, useApi } from "../lib";

const TABLE_WORDS: Record<string, string> = {
  loans: "Loans",
  kfs: "Key Facts Statements",
  tranches: "Tranches",
  disbursement_evidence: "Disbursement evidence",
  interest_postings: "Interest postings",
  receipts: "Receipts",
  rate_history: "Rate history",
  branches: "Branches",
  borrowers: "Borrowers",
  demands: "Demands",
  kfs_disbursal_schedule: "KFS disbursal schedule",
};

const ORDER = Object.keys(TABLE_WORDS);

const FILES: [string, string][] = [
  ["loans.csv", "One row per loan: branch, product, sanction and agreement dates, sanctioned amount"],
  ["kfs.csv", "What the Key Facts Statement disclosed: rate, day count, commitment fee"],
  ["tranches.csv", "Each disbursement: amount and payment mode"],
  ["disbursement_evidence.csv", "Every date recorded for a tranche: loan system, cheque, handover, payment rail"],
  ["interest_postings.csv", "The interest the loan system posted, month by month, with reversals"],
  ["receipts.csv", "Repayments, advance instalments and closures"],
  ["rate_history.csv", "Rate in force from each date"],
  ["branches.csv, borrowers.csv", "Names for the screens and letters"],
  ["demands.csv, kfs_disbursal_schedule.csv", "Optional"],
];

export default function Data({ onChanged }: { onChanged: () => void }) {
  const [ver, setVer] = useState(0);
  const { data } = useApi<any>("/data/status", [ver]);
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const file = useRef<HTMLInputElement>(null);

  const done = (r: any) => { setResult(r); setVer((v) => v + 1); onChanged(); };
  const upload = async (f: File) => {
    setBusy(`Checking and loading ${f.name}…`); setErrors([]); setResult(null);
    try {
      const r = await api<any>("/data/upload", { method: "POST", headers: { "Content-Type": "application/zip" }, body: f });
      if (r.ok) done(r); else setErrors(r.errors);
    } catch (e: any) { setErrors([e.message]); } finally { setBusy(null); if (file.current) file.current.value = ""; }
  };
  const sample = async () => {
    setBusy("Loading the synthetic sample book and running the audit…"); setErrors([]); setResult(null);
    try { done(await api<any>("/data/sample", { method: "POST" })); }
    catch (e: any) { setErrors([e.message]); } finally { setBusy(null); }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Data</h1>
          <p>The audit runs on whichever loan book is loaded in Exasol. Load your own extract to see your own figures on every screen.</p>
        </div>
      </div>

      {busy && <div className="verdict" style={{ marginBottom: 16 }}>{busy} This takes under a minute for a 10,000-loan book.</div>}
      {result && (
        <div className="verdict ok" style={{ marginBottom: 16 }}>
          Loaded <b>{result.dataset_id}</b> and audited it in {seconds(result.run.duration_ms)} inside Exasol.{" "}
          <a href="#/book" onClick={() => go("/book")}>Open the overview</a>
        </div>
      )}
      {errors.length > 0 && (
        <div className="verdict" style={{ marginBottom: 16, borderLeftColor: "var(--accent)" }}>
          <b>The extract was not loaded.</b> Nothing in Exasol was changed. Fix these and upload again:
          <ul className="small" style={{ margin: "8px 0 0", paddingLeft: 18 }}>{errors.map((e) => <li key={e}>{e}</li>)}</ul>
        </div>
      )}

      <div className="grid g2" style={{ alignItems: "start" }}>
        <div className="card pad">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
            <h2>Loaded book</h2>
            {data?.loaded && <span className={`tag ${data.synthetic ? "PERMITTED" : "FAIR"}`}>{data.synthetic ? "Synthetic sample" : "Uploaded extract"}</span>}
          </div>
          {!data ? <div className="loading">Reading from Exasol…</div> : !data.loaded ? (
            <p className="muted">No loan book is loaded yet.</p>
          ) : (
            <>
              <div className="kv" style={{ margin: "10px 0 14px" }}>
                <span>Name <b className="mono">{data.dataset.dataset_id}</b></span>
                <span>Data up to <b>{day(data.dataset.as_of)}</b></span>
                <span>Last audit <b>{data.latest_run ? `${day(data.latest_run.started_at)}, ${seconds(data.latest_run.duration_ms)}` : "not run yet"}</b></span>
              </div>
              <table className="t">
                <thead><tr><th>Table</th><th className="r">Rows</th></tr></thead>
                <tbody>
                  {[...(data.tables as any[])].sort((a, b) => ORDER.indexOf(a.table_name) - ORDER.indexOf(b.table_name)).map((t) => (
                    <tr key={t.table_name}><td>{TABLE_WORDS[t.table_name] ?? t.table_name}</td><td className="r">{n(t.n)}</td></tr>
                  ))}
                </tbody>
              </table>
              {data.synthetic && <p className="small muted" style={{ marginBottom: 0 }}>Generated with a fixed seed. Names, loans and figures are fictional.</p>}
            </>
          )}
        </div>

        <div className="card pad">
          <h2>Load your own book</h2>
          <p className="small muted">Export these files from your loan system, one CSV per table, and upload them together as a ZIP. Each file is checked before anything in Exasol changes.</p>
          <table className="t" style={{ marginBottom: 14 }}>
            <tbody>
              {FILES.map(([f, d]) => <tr key={f}><td className="mono small" style={{ whiteSpace: "nowrap" }}>{f}</td><td className="small muted">{d}</td></tr>)}
            </tbody>
          </table>
          <p className="small muted">Amounts in whole paise, dates as YYYY-MM-DD. The template shows every column with three example loans, and can itself be uploaded as a test.</p>
          <div className="filters" style={{ margin: 0 }}>
            <a className="btn ghost" href="/api/data/templates.zip">Download template</a>
            <button className="btn" disabled={!!busy} onClick={() => file.current?.click()}>Upload ZIP</button>
            <input ref={file} type="file" accept=".zip,application/zip" hidden onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          </div>
          <div style={{ borderTop: "1px solid var(--rule-2)", marginTop: 18, paddingTop: 14 }}>
            <div className="small" style={{ fontWeight: 500 }}>Sample book</div>
            <p className="small muted" style={{ margin: "4px 0 10px" }}>10,000 synthetic loans with known defects, including the three walkthrough loans.</p>
            <button className="btn ghost" disabled={!!busy} onClick={sample}>
              {data?.loaded && data.synthetic ? "Reload the sample book" : "Load the sample book"}
            </button>
          </div>
          <p className="tiny faint" style={{ marginBottom: 0, marginTop: 14 }}>Loading replaces the current book. Earlier audit runs stay in the run history. Large books load faster from the command line: <span className="mono">make load</span>.</p>
        </div>
      </div>
    </>
  );
}

export function FirstRun() {
  return (
    <div className="card pad" style={{ maxWidth: 640, margin: "60px auto", textAlign: "center" }}>
      <h1 style={{ marginTop: 0 }}>No audit yet</h1>
      <p className="muted">Sahi Byaaj audits the loan book loaded in Exasol. Load the synthetic sample to look around, or upload your own extract.</p>
      <div style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 18 }}>
        <a className="btn" href="#/data">Go to Data</a>
      </div>
    </div>
  );
}
