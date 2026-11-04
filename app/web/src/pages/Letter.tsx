import { useState } from "react";
import { day, go, inr, LETTER_WORDS, post, PRACTICE, useApi, useReviewer } from "../lib";
import { ActorFields } from "./Review";

const KIND: Record<string, string> = { excess: "amount", days: "days", periods: "billing periods" };
const figureLabel = (key: string) => {
  const [line, kind] = key.split(".");
  return line === "TOTAL" ? `Total ${KIND[kind] ?? kind}` : `${line} ${KIND[kind] ?? kind}`;
};

export default function Letter({ runId, loanId, lang }: { runId: string; loanId?: string; lang: string }) {
  const [ver, setVer] = useState(0);
  const [name, setName] = useReviewer();
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [batch, setBatch] = useState<any>(null);
  const { data, error } = useApi<any>(loanId ? `/runs/${runId}/letters/${loanId}?lang=${lang}` : null, [runId, loanId, lang, ver]);
  if (error) return <div className="empty">{error}</div>;
  if (!data) return <div className="loading">Rendering letter from the ledger…</div>;
  const state = data.state ?? {};
  const release = async () => {
    setErr(null);
    try {
      setBatch(await post(`/runs/${data.run_id}/releases`, { reviewer: name, reason, loan_ids: [loanId], lang: data.lang }));
      setVer((v) => v + 1);
    } catch (e: any) { setErr(e.message); }
  };
  const figures = new Set((data.check.figures as any[]).filter((f) => f.figure.endsWith(".excess")).map((f) => f.shown));
  const html = escape(data.text).replace(/-?₹[0-9,]+\.[0-9]{2}/g, (m) => (figures.has(m) ? `<mark>${m}</mark>` : m));
  return (
    <>
      <div className="page-head">
        <div>
          <a href={`#/loan/${loanId}`} className="small muted">← Back to loan {loanId}</a>
          <h1 style={{ marginTop: 6 }}>Refund letter</h1>
          <p>The wording is a fixed template. Every amount comes from the refund ledger, and a checker compares each one with the ledger, and a person must approve the refund before the letter can be released.</p>
        </div>
        <div className="filters" style={{ margin: 0 }}>
          <button className={`btn ${data.lang === "en" ? "" : "ghost"}`} onClick={() => go(`/letter/${loanId}?lang=en`)}>English</button>
          <button className={`btn ${data.lang === "hi" ? "" : "ghost"}`} onClick={() => go(`/letter/${loanId}?lang=hi`)}>हिन्दी</button>
          <button className={`btn ${data.lang === "ta" ? "" : "ghost"}`} onClick={() => go(`/letter/${loanId}?lang=ta`)}>தமிழ்</button>
        </div>
      </div>
      {state.letter_state !== "RELEASED" && state.letter_state !== "APPROVED" && <div className="verdict warn" style={{ marginBottom: 16 }}><b>Draft.</b> Not approved by a reviewer, so it cannot be released yet. <a href={`#/loan/${loanId}`}>Review this refund</a>.</div>}
      {err && <div className="verdict warn" style={{ marginBottom: 16 }}>{err}</div>}
      {batch && <div className="verdict ok" style={{ marginBottom: 16 }}>Released. <a href={`/api/releases/${batch.batch_id}/letters.zip`}>Download the batch</a> and send it through your own channels.</div>}
      <div className="grid" style={{ gridTemplateColumns: "1fr 320px", alignItems: "start" }}>
        <div className="letter" dangerouslySetInnerHTML={{ __html: html }} />
        <div className="grid" style={{ alignItems: "start" }}>
        <div className="card pad">
          <div className="upper">Status</div>
          <div style={{ margin: "6px 0 10px" }}><span className={`tag ${state.letter_state}`}>{LETTER_WORDS[state.letter_state] ?? state.letter_state}</span></div>
          {state.letter_state === "RELEASED" ? (
            <>
              <p className="small muted" style={{ marginTop: 0 }}>Released by {state.released_by} on {day(state.released_at)} at {inr(state.released_paise)}. This tool does not send letters, so this does not confirm delivery.</p>
              <a className="btn ghost" href={`/api/releases/${state.batch_id}/letters.zip`}>Download batch</a>
            </>
          ) : (
            <>
              {state.released_paise != null && <p className="small muted" style={{ marginTop: 0 }}>An earlier letter was released at {inr(state.released_paise)}. The figure has changed since.</p>}
              <ActorFields name={name} setName={setName} reason={reason} setReason={setReason} why="Note for this release" />
              <button className="btn" onClick={release}>Release this letter</button>
              <p className="tiny faint" style={{ marginBottom: 0 }}>Releases the {data.lang === "en" ? "English" : data.lang === "hi" ? "Hindi" : "Tamil"} version for dispatch through the lender's own channels.</p>
            </>
          )}
        </div>
        <div className="card pad">
          <div className="upper">Checker</div>
          <div style={{ fontFamily: "var(--serif)", fontSize: 22, fontWeight: 600, margin: "4px 0 12px", color: data.check.ok ? "var(--ok)" : "var(--accent)" }}>
            {data.check.ok ? "Every figure matches the ledger" : "Letter rejected"}
          </div>
          <div className="checklist">
            {(data.check.figures as any[]).map((f) => (
              <div key={f.figure}>
                <span className={f.ok ? "tick" : "cross"}>{f.ok ? "OK" : "NO"}</span>
                <span className="small" title={PRACTICE[f.figure.split(".")[0]] ?? ""}>{figureLabel(f.figure)}</span>
                <span className="mono small" style={{ marginLeft: "auto" }}>{f.shown}</span>
              </div>
            ))}
            <div><span className={data.check.lines_sum_to_total ? "tick" : "cross"}>{data.check.lines_sum_to_total ? "OK" : "NO"}</span><span className="small">Practice lines add up to the total, per the ledger</span></div>
            <div><span className={data.check.stray_amounts.length ? "cross" : "tick"}>{data.check.stray_amounts.length ? "NO" : "OK"}</span><span className="small">No amount in the letter that the ledger does not hold</span></div>
          </div>
          {data.requested_lang && data.requested_lang !== data.lang && <p className="tiny muted">Preferred language {data.requested_lang} is not available yet; shown in English.</p>}
        </div>
        </div>
      </div>
    </>
  );
}

function escape(s: string) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
