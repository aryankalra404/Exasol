import { useState } from "react";
import { CERTAINTY_WORDS, day, describeConvention, inr, month, n, plural, post, PRACTICE, REVIEW_WORDS, useApi, useReviewer } from "../lib";

/** Who and why. Both are required by the API on every review action; the name is remembered, the reason is not. */
export function ActorFields({ name, setName, reason, setReason, why = "Reason for this action", sticky = false }: {
  name: string; setName: (v: string) => void; reason: string; setReason: (v: string) => void; why?: string; sticky?: boolean;
}) {
  return (
    <div className={`filters actor ${sticky ? "sticky" : ""}`}>
      <input data-actor="name" aria-label="Your name" placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} />
      <input data-actor="reason" aria-label={why} className="grow" placeholder={why} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
    </div>
  );
}

/** Says what is missing before a request is sent, and puts the cursor there. Null when both are filled in. */
export function missingActor(name: string, reason: string): string | null {
  const missing = !name.trim() ? "name" : !reason.trim() ? "reason" : null;
  if (!missing) return null;
  document.querySelector<HTMLInputElement>(`input[data-actor="${missing}"]`)?.focus();
  return missing === "name" ? "Enter your name first. Every review action records who took it." : "Enter a reason first. Every review action records why it was taken.";
}

/** Feedback fixed to the window, so it shows wherever the reviewer has scrolled to. */
export function Toast({ err, msg, onClose }: { err: string | null; msg?: string | null; onClose: () => void }) {
  if (!err && !msg) return null;
  return (
    <div className={`toast ${err ? "warn" : "ok"}`} role={err ? "alert" : "status"}>
      <span>{err ?? msg}</span>
      <button className="toast-x" aria-label="Dismiss" onClick={onClose}>×</button>
    </div>
  );
}

const sumOf = (rows: any[] | undefined, state: string, key: string) => rows?.find((r) => (r.review_state ?? r.letter_state) === state)?.[key] ?? 0;

function OlderRun({ onLatest }: { onLatest: () => void }) {
  return (
    <div className="verdict warn older-run">
      <span>You are viewing an older audit run, so it is read-only and the buttons are off.</span>
      <button className="btn" onClick={onLatest}>Switch to the latest run</button>
    </div>
  );
}

export default function Review({ runId, params, onLatest }: { runId: string; params: URLSearchParams; onLatest: () => void }) {
  const [ver, setVer] = useState(0);
  const [name, setName] = useReviewer();
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [practice, setPractice] = useState(params.get("practice") ?? "");
  const [branch, setBranch] = useState(params.get("branch") ?? "");
  const [review, setReview] = useState(params.get("review") ?? "UNREVIEWED");
  const [certainty, setCertainty] = useState(params.get("certainty") ?? "");
  const [convention, setConvention] = useState(params.get("convention") ?? "");
  const [page, setPage] = useState(1);
  const size = 25;
  const qs = new URLSearchParams({ practice, branch, review, certainty, convention, page: String(page), size: String(size) }).toString();
  const sum = useApi<any>(`/runs/${runId}/review/summary`, [runId, ver]).data;
  const led = useApi<any>(`/runs/${runId}/ledger?${qs}`, [runId, qs, ver]).data;
  const meta = useApi<any>(`/runs/${runId}/summary`, [runId]).data;
  const rid = sum?.run_id;
  const readOnly = sum && !sum.is_latest;

  const act = async (fn: () => Promise<any>, done: (r: any) => string) => {
    setBusy(true); setErr(null); setMsg(null);
    try {
      const r = await fn();
      setMsg(done(r));
      setVer((v) => v + 1);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const needActor = (why: string) => {
    const missing = missingActor(name, why);
    if (missing) { setMsg(null); setErr(missing); }
    return missing;
  };
  const decide = (r: any, decision: string) => needActor(reason) ?? act(
    () => post(`/runs/${rid}/review/decisions`, { loan_id: r.loan_id, practice_code: r.practice_code, decision, reviewer: name, reason }),
    () => `${REVIEW_WORDS[decision]}: ${r.loan_id} ${r.practice_code}, ${inr(r.excess_paise)}.`,
  );
  const approveAll = () => needActor(reason) ?? act(
    () => post(`/runs/${rid}/review/approve-filtered`, { practice, branch, certainty, convention, reviewer: name, reason }),
    (r) => `Approved ${plural(r.row_count, "row")}, ${inr(r.excess_paise)}. Rows on hold or with a changed figure were left alone.`,
  );
  const release = () => act(
    () => post(`/runs/${rid}/releases`, { reviewer: name, reason: note }),
    (r) => `Released ${plural(r.letter_count, "letter")}, ${inr(r.total_paise)}. Download the batch below and send it through your own channels.`,
  );

  const approved = sumOf(sum?.by_state, "APPROVED", "excess_paise");
  const ready = Number(sumOf(sum?.letters, "APPROVED", "loans"));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Review and release</h1>
          <p>A person approves each refund before its letter can leave. Decisions never change a figure: every amount here comes from the audit run in Exasol.</p>
        </div>
      </div>
      {readOnly && <OlderRun onLatest={onLatest} />}
      <Toast err={err} msg={msg} onClose={() => { setErr(null); setMsg(null); }} />

      {sum && (
        <div className="grid g4">
          <div className="tile ok"><div className="upper">Approved</div><div className="v">{inr(approved, { paise: false })}</div><div className="d">of {inr(sum.ledger_total, { paise: false })} owed, {plural(sumOf(sum.by_state, "APPROVED", "row_count"), "row")}</div></div>
          <div className="tile"><div className="upper">Not reviewed</div><div className="v">{inr(sumOf(sum.by_state, "UNREVIEWED", "excess_paise"), { paise: false })}</div><div className="d">{plural(sumOf(sum.by_state, "UNREVIEWED", "row_count"), "row")}</div></div>
          <div className="tile warn"><div className="upper">Needs re-review</div><div className="v">{inr(sumOf(sum.by_state, "STALE", "excess_paise"), { paise: false })}</div><div className="d">{plural(sumOf(sum.by_state, "STALE", "row_count"), "row")} whose figure changed after the decision</div></div>
          <div className="tile slate"><div className="upper">On hold</div><div className="v">{inr(sumOf(sum.by_state, "HOLD", "excess_paise"), { paise: false })}</div><div className="d">{plural(sumOf(sum.by_state, "HOLD", "row_count"), "row")}, still counted as owed until resolved</div></div>
        </div>
      )}

      <section className="section">
        <header><div><h2>Refunds to review</h2><p>Approve or hold one row, or filter to one root cause or evidence level and approve what is left under one reason. Loans with no refund are listed in <a href="#/loans/FAIR">All loans</a>.</p></div></header>
        {readOnly ? <OlderRun onLatest={onLatest} /> : <ActorFields name={name} setName={setName} reason={reason} setReason={setReason} sticky />}
        <div className="filters">
          <select aria-label="Review state" value={review} onChange={(e) => { setReview(e.target.value); setPage(1); }}>
            <option value="">All review states</option>
            {["UNREVIEWED", "STALE", "HOLD", "APPROVED"].map((s) => <option key={s} value={s}>{REVIEW_WORDS[s]}</option>)}
          </select>
          <select aria-label="Evidence" value={certainty} onChange={(e) => { setCertainty(e.target.value); setPage(1); }}>
            <option value="">All evidence levels</option>
            {Object.entries(CERTAINTY_WORDS).map(([k, label]) => {
              const c = sum?.by_certainty?.find((x: any) => x.certainty === k);
              return <option key={k} value={k}>{label} ({n(c?.row_count ?? 0)})</option>;
            })}
          </select>
          <select aria-label="Practice" value={practice} onChange={(e) => { setPractice(e.target.value); setPage(1); }}>
            <option value="">All practices</option>
            {["P1", "P2", "P3", "P4", "P5", "AMB"].map((p) => <option key={p} value={p}>{p} · {PRACTICE[p]}</option>)}
          </select>
          <select aria-label="Branch" value={branch} onChange={(e) => { setBranch(e.target.value); setPage(1); }}>
            <option value="">All branches</option>
            {(meta?.branches ?? []).map((b: any) => <option key={b.branch_id} value={b.branch_id}>{b.branch_name}</option>)}
          </select>
          {convention && <button className="btn ghost mini" title="Clear this filter" onClick={() => { setConvention(""); setPage(1); }}>Root cause: {describeConvention(convention).toLowerCase()} ×</button>}
          {(practice || branch || certainty || convention) && <button className="btn ghost" disabled={busy || readOnly} onClick={approveAll}>Approve all not reviewed in this filter</button>}
          {led && <span className="muted small" style={{ marginLeft: "auto" }}>{plural(led.total.n, "row")}, <b className="num">{inr(led.total.excess_paise)}</b></span>}
        </div>
        <div className="card">
          <table className="t">
            <thead><tr><th>Borrower</th><th>Loan</th><th>Practice</th><th>Why</th><th>Months</th><th className="r">Excess</th><th>Review</th><th className="r">Action</th></tr></thead>
            <tbody>
              {(led?.rows ?? []).map((r: any) => (
                <tr key={r.loan_id + r.practice_code}>
                  <td>{r.display_name}</td>
                  <td className="mono small"><a href={`#/loan/${r.loan_id}`}>{r.loan_id}</a></td>
                  <td><span className="tag code">{r.practice_code}</span></td>
                  <td className="small" style={{ maxWidth: 300 }}>
                    {r.practice_code === "AMB" ? PRACTICE.AMB : describeConvention(String(r.conventions ?? "").split(",")[0])}, {plural(r.days_affected, "day")} affected
                    <div className="tiny faint">{CERTAINTY_WORDS[r.certainty]}</div>
                  </td>
                  <td className="small">{month(r.first_period)}{r.first_period !== r.last_period ? ` to ${month(r.last_period)}` : ""}</td>
                  <td className="r">{inr(r.excess_paise)}</td>
                  <td className="small"><span className={`tag ${r.review_state}`}>{REVIEW_WORDS[r.review_state]}</span>{r.held_days != null && <div className="tiny">On hold for {plural(r.held_days, "day")}</div>}{r.decided_by && <div className="tiny faint" title={r.review_reason}>{r.decided_by}: {r.review_reason}</div>}</td>
                  <td className="r nowrap">
                    <button className="btn mini" disabled={busy || readOnly} onClick={() => decide(r, "APPROVED")}>Approve</button>{" "}
                    <button className="btn ghost mini" disabled={busy || readOnly} onClick={() => decide(r, "HOLD")}>Hold</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {led && led.rows.length === 0 && <div className="empty">Nothing here for these filters.</div>}
        </div>
        {led && Number(led.total.n) > size && (
          <div className="filters" style={{ marginTop: 14, justifyContent: "flex-end" }}>
            <button className="btn ghost" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button>
            <span className="small muted">Page {page} of {Math.ceil(Number(led.total.n) / size)}</span>
            <button className="btn ghost" disabled={led.rows.length < size} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        )}
      </section>

      <section className="section">
        <header><div><h2>Release letters</h2><p>This tool does not send anything. Releasing checks every approved letter against the ledger again and packages it for the lender's own email, SMS or post.</p></div></header>
        {sum && (
          <div className="grid g3" style={{ marginBottom: 14 }}>
            <div className="tile"><div className="upper">Draft</div><div className="v">{plural(sumOf(sum.letters, "DRAFT", "loans"), "letter")}</div><div className="d">Waiting for every refund on the loan to be approved</div></div>
            <div className="tile ok"><div className="upper">Approved, ready</div><div className="v">{plural(ready, "letter")}</div><div className="d">{inr(sumOf(sum.letters, "APPROVED", "total_paise"))}</div></div>
            <div className="tile slate"><div className="upper">Released</div><div className="v">{plural(sumOf(sum.letters, "RELEASED", "loans"), "letter")}</div><div className="d">{inr(sumOf(sum.letters, "RELEASED", "total_paise"))}</div></div>
          </div>
        )}
        {(sum?.changed_releases ?? []).length > 0 && (
          <div className="verdict warn" style={{ marginBottom: 14 }}>
            <b>{plural(sum.changed_releases.length, "released letter")} no longer match{sum.changed_releases.length === 1 ? "es" : ""} this run.</b> Review the new figure and tell the borrower through your own process.
            <div className="small" style={{ marginTop: 6 }}>{sum.changed_releases.slice(0, 5).map((c: any) => (
              <div key={c.loan_id}><a href={`#/loan/${c.loan_id}`} className="mono">{c.loan_id}</a>: released at {inr(c.released_paise)}, now {inr(c.current_paise)}</div>
            ))}</div>
          </div>
        )}
        <div className="filters actor">
          <input className="grow" aria-label="Note for this batch" placeholder="Note for this batch" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
          <button className="btn" disabled={busy || readOnly || ready === 0} onClick={() => {
            if (!name.trim()) { needActor(note); return; }
            if (!note.trim()) { setMsg(null); setErr("Enter a note for this batch first."); document.querySelector<HTMLInputElement>('input[aria-label="Note for this batch"]')?.focus(); return; }
            release();
          }}>Release {plural(ready, "approved letter")}</button>
        </div>
        <div className="card">
          <table className="t">
            <thead><tr><th>Released</th><th>By</th><th>Note</th><th className="r">Letters</th><th className="r">Total</th><th /></tr></thead>
            <tbody>
              {(sum?.batches ?? []).map((b: any) => (
                <tr key={b.batch_id}>
                  <td className="small">{day(b.released_at)} {String(b.released_at).slice(11, 16)} UTC</td>
                  <td className="small">{b.released_by}</td>
                  <td className="small muted">{b.batch_note}</td>
                  <td className="r">{n(b.letter_count)}</td>
                  <td className="r">{inr(b.total_paise)}</td>
                  <td className="r"><a className="btn ghost mini" href={`/api/releases/${b.batch_id}/letters.zip`}>Download</a></td>
                </tr>
              ))}
            </tbody>
          </table>
          {sum && sum.batches.length === 0 && <div className="empty">No letters released yet.</div>}
        </div>
      </section>
    </>
  );
}

