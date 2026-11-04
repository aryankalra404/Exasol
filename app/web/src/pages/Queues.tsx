import { useEffect, useState } from "react";
import { api, day, describeConvention, go, inr, MODE_WORDS, month, n, plural, post, REVIEW_WORDS, seconds, sources, STATUS_WORDS, useApi, useReviewer } from "../lib";
import { LiveStrip } from "./Live";
import { ActorFields, missingActor, Toast } from "./Review";

const TABS: [string, string, string][] = [
  ["gaps", "Evidence gaps", "The money-in-hand date cannot be decided. A query to the branch is drafted for each, and the reply can be entered here."],
  ["unexplained", "Unexplained", "No known calculation method reproduces the posted amount. Needs manual review."],
  ["ambiguous", "Ambiguous", "The overcharge is certain, but more than one practice explains it equally well. When counted in the total, approve these in Review and release, as practice AMB."],
  ["permitted", "Permitted", "The posting matches a term the KFS disclosed, and policy allows it. No refund."],
  ["undercharge", "Undercharge", "The lender posted less than the fair amount. Nothing to refund; listed for completeness."],
];

const ACTION: Record<string, string> = {
  gaps: "Waiting on the branch",
  unexplained: "Needs investigation",
  ambiguous: "Review as a refund",
  permitted: "No action unless policy changes",
  undercharge: "For information",
};

export default function Queues({ runId, tab, onRun }: { runId: string; tab: string; onRun: () => void }) {
  const [ran, setRan] = useState(0);
  const s = useApi<any>(`/runs/${runId}/summary`, [runId, ran]).data?.summary;
  const counts: Record<string, string> = s ? {
    gaps: n(s.gap_tranches), unexplained: n(s.unexplained_periods), undercharge: n(s.undercharge_periods),
  } : {};
  const info = TABS.find((t) => t[0] === tab) ?? TABS[0];
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Work queues</h1>
          <p>Items the audit could not resolve automatically. Each one says what is missing and why it is not in the refund total.</p>
        </div>
      </div>
      <div className="tabs">
        {TABS.map(([k, label]) => <a key={k} href={`#/queues/${k}`} className={tab === k ? "on" : ""}>{label}{counts[k] && <span className="count">{counts[k]}</span>}</a>)}
      </div>
      <p className="muted" style={{ marginTop: 0 }}><b style={{ color: "var(--ink)" }}>{ACTION[info[0]]}.</b> {info[2]}</p>
      {tab === "gaps" ? <Gaps runId={runId} onRan={() => { setRan((v) => v + 1); onRun(); }} /> : <FindingQueue runId={runId} status={{ unexplained: "UNEXPLAINED", ambiguous: "AMBIGUOUS", permitted: "PERMITTED", undercharge: "UNDERCHARGE" }[tab] ?? "UNEXPLAINED"} />}
    </>
  );
}

const GAPS_PER_PAGE = 20;
const ROWS_PER_PAGE = 50;

function Pager({ page, size, total, onPage, noun }: { page: number; size: number; total: number; onPage: (p: number) => void; noun: string }) {
  const last = Math.max(1, Math.ceil(total / size));
  const from = total ? (page - 1) * size + 1 : 0;
  const to = Math.min(page * size, total);
  return (
    <div className="pager">
      <span className="small muted">Showing {n(from)}–{n(to)} of {plural(total, noun)}</span>
      <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button className="btn ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
        <span className="small muted">Page {page} of {last}</span>
        <button className="btn ghost" disabled={page >= last} onClick={() => onPage(page + 1)}>Next</button>
      </span>
    </div>
  );
}

const ENTRY_WORDS: Record<string, string> = {
  PENDING: "Waiting for a re-run",
  IN_RUN: "Used in this run",
  WITHDRAWN_PENDING: "Withdrawn, waiting for a re-run",
  WITHDRAWN: "Withdrawn",
  NEVER_USED: "Withdrawn, never used",
};

function Gaps({ runId, onRan }: { runId: string; onRan: () => void }) {
  const [ver, setVer] = useState(0);
  const { data } = useApi<any[]>(`/runs/${runId}/gaps`, [runId, ver]);
  const entries = useApi<any[]>(`/runs/${runId}/evidence`, [runId, ver]);
  const [copied, setCopied] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [branch, setBranch] = useState("");
  const [name, setName] = useReviewer();
  const [why, setWhy] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [when, setWhen] = useState("");
  const [ref, setRef] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => setPage(1), [runId, branch]);
  if (!data) return <div className="loading">Loading…</div>;
  const rid = data[0]?.run_id;
  const list = entries.data ?? [];
  const waiting = list.filter((e) => e.entry_state === "PENDING" || e.entry_state === "WITHDRAWN_PENDING");
  const fail = (e: any) => { setMsg(null); setErr(e.message); };
  const save = async (g: any) => {
    const missing = missingActor(name, why);
    if (missing) { setMsg(null); setErr(missing); return; }
    setErr(null);
    try {
      await post(`/runs/${g.run_id}/evidence`, { loan_id: g.loan_id, tranche_no: g.tranche_no, event_date: when, reference: ref, reviewer: name, reason: why });
      setOpen(null); setWhen(""); setRef("");
      setMsg(`Saved for ${g.loan_id}. Re-run the audit to see what this date means.`);
      setVer((v) => v + 1);
    } catch (e: any) { fail(e); }
  };
  const withdraw = async (e: any) => {
    const missing = missingActor(name, why);
    if (missing) { setMsg(null); setErr(missing); return; }
    setErr(null);
    try {
      await post(`/runs/${e.run_id ?? rid ?? "latest"}/evidence/${e.evidence_id}/withdraw`, { reviewer: name, reason: why });
      setMsg(`Withdrawn for ${e.loan_id}. Re-run the audit to apply this.`);
      setVer((v) => v + 1);
    } catch (x: any) { fail(x); }
  };
  const rerun = async () => {
    setBusy(true); setErr(null); setMsg(null);
    try {
      const before = (await api<any>("/runs/latest/summary")).run.run_id;
      const r = await post<any>("/runs", { label: "Re-run: branch evidence entered" });
      const cmp = await api<any>(`/compare/${before}/${r.run_id}`);
      const delta = String(cmp.totals.delta_refund);
      setMsg(`Re-run finished in ${seconds(r.duration_ms)} in Exasol. Refund total ${delta.startsWith("-") ? "" : "+"}${inr(delta)}. Open the loan below to see the result.`);
      setVer((v) => v + 1);
      onRan();
    } catch (e: any) { fail(e); } finally { setBusy(false); }
  };
  const branches = [...new Map(data.map((g) => [g.branch_id, g.branch_name])).entries()].sort((a, b) => a[1].localeCompare(b[1]));
  const shown = branch ? data.filter((g) => g.branch_id === branch) : data;
  const pageRows = shown.slice((page - 1) * GAPS_PER_PAGE, page * GAPS_PER_PAGE);
  const toPage = (p: number) => { setPage(p); window.scrollTo({ top: 0 }); };
  return (
    <>
    <Toast err={err} msg={msg} onClose={() => { setErr(null); setMsg(null); }} />
    <p className="small muted" style={{ marginTop: 0 }}>When a branch replies, enter the date and document reference. You enter no amount: the re-run applies the same rules as every other tranche and decides whether a refund is due.</p>
    <ActorFields name={name} setName={setName} reason={why} setReason={setWhy} why="Reason for this entry" sticky />
    {busy && <LiveStrip running />}
    {waiting.length > 0 && (
      <div className="verdict warn older-run">
        <span><b>{plural(waiting.length, "change")} to the evidence not in this run yet.</b></span>
        <button className="btn" disabled={busy} onClick={rerun}>{busy ? "Running in Exasol…" : "Re-run the audit"}</button>
      </div>
    )}
    {list.length > 0 && (
      <div className="card" style={{ marginBottom: 16 }}>
        <table className="t">
          <thead><tr><th>Entered evidence</th><th>Date</th><th>Reference</th><th>By and why</th><th>Status</th><th>Loan in this run</th><th /></tr></thead>
          <tbody>
            {list.map((e) => (
              <tr key={e.evidence_id}>
                <td><a href={`#/loan/${e.loan_id}`}>{e.display_name}</a><div className="mono tiny faint">{e.loan_id} · tranche {e.tranche_no} · {sources(e.evidence_source)}</div></td>
                <td className="small nowrap">{day(e.event_date)}</td>
                <td className="small mono">{e.reference}</td>
                <td className="small muted">{e.added_by}: {e.reason}{e.withdrawn_by && <div className="tiny">Withdrawn by {e.withdrawn_by}: {e.withdrawn_reason}</div>}</td>
                <td className="small">{ENTRY_WORDS[e.entry_state]}</td>
                <td className="small nowrap">
                  {Number(e.loan_refund_paise) > 0 ? <b>Refund {inr(e.loan_refund_paise)}</b> : !e.loan_statuses ? "Fair, no refund" : "No refund"}
                  {e.loan_statuses && <div>{String(e.loan_statuses).split(",").map((st: string) => <span key={st} className={`tag ${st}`} style={{ marginRight: 4 }}>{STATUS_WORDS[st] ?? st}</span>)}</div>}
                </td>
                <td className="r">{!e.withdrawn_at && <button className="btn ghost mini" onClick={() => withdraw(e)}>Withdraw</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
    {!data.length ? <div className="empty">No evidence gaps in this run.</div> : (
    <>
    <div className="filters" style={{ marginBottom: 12 }}>
      <select value={branch} onChange={(e) => setBranch(e.target.value)}>
        <option value="">All branches</option>
        {branches.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select>
    </div>
    <Pager page={page} size={GAPS_PER_PAGE} total={shown.length} onPage={toPage} noun="tranche" />
    <div className="grid g2">
      {pageRows.map((g) => {
        const key = g.loan_id + g.tranche_no;
        const entered = list.some((e) => e.loan_id === g.loan_id && e.tranche_no === g.tranche_no && !e.withdrawn_at);
        return (
        <div key={key} className="card pad">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <div>
              <a href={`#/loan/${g.loan_id}`} style={{ fontWeight: 600 }}>{g.display_name}</a>
              <div className="mono small faint" style={{ marginTop: 2 }}>{g.loan_id} · tranche {g.tranche_no} · {MODE_WORDS[g.payment_mode] ?? g.payment_mode} · {inr(g.amount_paise, { paise: false })}</div>
            </div>
            <span className="tag EVIDENCE_GAP" style={{ whiteSpace: "nowrap", alignSelf: "flex-start" }}>Missing {sources(g.missing_source)}</span>
          </div>
          <div className="small muted" style={{ marginTop: 6 }}>
            {g.branch_name} · uncertainty window {day(g.window_start)} to {day(g.window_end)} · {plural(g.periods_affected, "month")} held, {inr(g.posted_paise_at_stake)} posted interest at stake
          </div>
          <div className="query">{g.suggested_query}</div>
          {open === key && (
            <div className="filters reply" style={{ marginTop: 10, marginBottom: 0 }}>
              <input type="date" aria-label={`Date for ${g.loan_id}`} value={when} onChange={(e) => setWhen(e.target.value)} />
              <input aria-label={`Reference for ${g.loan_id}`} placeholder="Document reference" maxLength={50} value={ref} onChange={(e) => setRef(e.target.value)} />
              <button className="btn mini" onClick={() => save(g)}>Save date</button>
              <button className="btn ghost mini" onClick={() => setOpen(null)}>Cancel</button>
            </div>
          )}
          <div style={{ marginTop: 8, display: "flex", justifyContent: "flex-end", gap: 8 }}>
            {entered ? <span className="small muted">Date entered</span> : open !== key && <button className="copy" onClick={() => { setOpen(key); setWhen(""); setRef(""); }}>Enter branch reply</button>}
            <button className="copy" onClick={() => { navigator.clipboard?.writeText(g.suggested_query); setCopied(key); }}>
              {copied === key ? "Copied" : "Copy query"}
            </button>
          </div>
        </div>
        );
      })}
    </div>
    <Pager page={page} size={GAPS_PER_PAGE} total={shown.length} onPage={toPage} noun="tranche" />
    </>
    )}
    </>
  );
}

function FindingQueue({ runId, status }: { runId: string; status: string }) {
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [runId, status]);
  const [ver, setVer] = useState(0);
  const [name, setName] = useReviewer();
  const [why, setWhy] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const { data } = useApi<any[]>(`/runs/${runId}/queue/${status}?page=${page}&size=${ROWS_PER_PAGE}`, [runId, status, page, ver]);
  const unexplained = status === "UNEXPLAINED";
  const decide = async (r: any, decision: string) => {
    const missing = missingActor(name, why);
    if (missing) { setErr(missing); return; }
    setErr(null);
    try {
      await post(`/runs/${r.run_id}/review/unexplained`, { loan_id: r.loan_id, period_start: r.period_start, decision, reviewer: name, reason: why });
      setVer((v) => v + 1);
    } catch (e: any) { setErr(e.message); }
  };
  if (!data) return <div className="loading">Loading…</div>;
  if (!data.length) return <div className="empty">Nothing in this queue for this run.</div>;
  const total = Number(data[0].total_rows ?? data.length);
  const onPage = (p: number) => { setPage(p); window.scrollTo({ top: 0 }); };
  return (
    <>
    {unexplained && (
      <>
        <p className="small muted" style={{ marginTop: 0 }}>Record the outcome of a manual look. This moves no money: to change a refund, correct the evidence or the policy and re-run.</p>
        <ActorFields name={name} setName={setName} reason={why} setReason={setWhy} why="What did you find?" sticky />
        <Toast err={err} onClose={() => setErr(null)} />
      </>
    )}
    <div className="card">
      <div className="pad" style={{ borderBottom: "1px solid var(--rule-2)", paddingTop: 10, paddingBottom: 10 }}>
        <Pager page={page} size={ROWS_PER_PAGE} total={total} onPage={onPage} noun="billing month" />
      </div>
      <table className="t">
        <thead><tr><th>Borrower</th><th>Loan</th><th>Month</th><th className="r">Posted</th><th className="r">Fair</th><th className="r">Difference</th><th>Why it is here</th>{unexplained && <th>Review</th>}</tr></thead>
        <tbody>
          {data.map((r) => (
            <tr key={r.loan_id + r.period_start + (r.practice_code ?? "")} className="click" onClick={() => go(`/loan/${r.loan_id}?period=${r.period_start}`)}>
              <td>{r.display_name}</td>
              <td className="mono small">{r.loan_id}</td>
              <td className="small">{month(r.period_start)}</td>
              <td className="r">{inr(r.posted_paise)}</td>
              <td className="r">{inr(r.fair_paise)}</td>
              <td className="r">{inr(r.excess_paise)}</td>
              <td className="small muted" style={{ maxWidth: 420 }}>{reason(r)}</td>
              {unexplained && (
                <td className="small" onClick={(e) => e.stopPropagation()}>
                  <span className={`tag ${r.review_state}`}>{REVIEW_WORDS[r.review_state]}</span>
                  {r.decided_by && <div className="tiny faint" title={r.review_reason}>{r.decided_by}: {r.review_reason}</div>}
                  <div className="nowrap" style={{ marginTop: 4 }}>
                    <button className="btn mini" onClick={() => decide(r, "CLEARED")}>Clear</button>{" "}
                    <button className="btn ghost mini" onClick={() => decide(r, "HOLD")}>Hold</button>
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="pad" style={{ borderTop: "1px solid var(--rule-2)", paddingTop: 10, paddingBottom: 10 }}>
        <Pager page={page} size={ROWS_PER_PAGE} total={total} onPage={onPage} noun="billing month" />
      </div>
    </div>
    </>
  );
}

/** The SQL reason, with the closest method and gap shown in words and rupees for the unexplained queue. */
function reason(r: any): string {
  if (r.closest_convention_id && r.closest_diff_paise !== null && r.closest_diff_paise !== undefined && String(r.reason).startsWith("No known")) {
    const off = inr(String(r.closest_diff_paise).replace("-", ""));
    return `No known calculation method reproduces the posted amount. Closest: ${describeConvention(r.closest_convention_id).toLowerCase()}, off by ${off}.${r.has_manual ? " A manual journal entry was posted for this month." : ""}`;
  }
  return r.reason;
}
