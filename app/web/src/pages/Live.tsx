import { useEffect, useRef, useState } from "react";
import { api, n, seconds, sentence } from "../lib";

const FAST_MS = 500;
const IDLE_MS = 3000;

/** Polls /live: quickly while a run is going or about to start, slowly otherwise, not at all in a hidden tab. */
function useLive(starting = false) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const startingRef = useRef(starting);
  startingRef.current = starting;
  const wake = useRef(() => {});
  useEffect(() => {
    let live = true;
    let timer: number;
    const tick = async () => {
      let fast = startingRef.current;
      if (!document.hidden) {
        try {
          const d = await api<any>("/live");
          if (!live) return;
          setData(d); setError(null);
          fast = fast || d.running;
        } catch {
          if (!live) return;
          setError("Cannot read live status from Exasol. A run already started is not affected.");
        }
      }
      timer = window.setTimeout(tick, fast ? FAST_MS : IDLE_MS);
    };
    wake.current = () => { clearTimeout(timer); tick(); };
    tick();
    return () => { live = false; clearTimeout(timer); };
  }, []);
  // a run has just been started: do not wait out the slow interval
  useEffect(() => { if (starting) wake.current(); }, [starting]);
  return { data, error };
}

/** "S60_CANDIDATE_CONVENTIONS" to "Candidate conventions". */
const stepName = (id: string) => {
  const s = id.replace(/^S\d+_/, "").replace(/_/g, " ").toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
};
const stepCode = (id: string) => id.split("_")[0];
const STEP_WORDS: Record<string, string> = { done: "Done", running: "Running", failed: "Failed", waiting: "Waiting" };

function Steps({ steps, starting, selected, onPick }: { steps: any[]; starting: boolean; selected?: number; onPick?: (i: number) => void }) {
  const Cell = onPick ? "button" : "div";
  return (
    <ol className="live-steps">
      {steps.map((s, i) => {
        const state = starting ? "waiting" : s.state;
        return (
          <li key={s.step_id} className={`${state} ${selected === i ? "selected" : ""}`} title={s.purpose}>
            <Cell className="cell" onClick={onPick ? () => onPick(i) : undefined}>
              <span className="mono tiny">{stepCode(s.step_id)}</span>
              <b>{stepName(s.step_id)}</b>
              <span className="mono tiny">{!starting && s.duration_ms != null ? seconds(s.duration_ms) : STEP_WORDS[state]}</span>
            </Cell>
          </li>
        );
      })}
    </ol>
  );
}

/** The step's first sentence: the rest of a SQL file's purpose line is detail for someone reading the file. */
const firstSentence = (s: string) => sentence(s.split(/\.\s/)[0].replace(/\.$/, "")) + ".";

function runWords(d: any, starting: boolean, loadFirst = false): string {
  if (starting) return loadFirst ? "Loading the book into Exasol" : "Starting audit in Exasol";
  if (!d?.run) return "No audit has run yet";
  if (d.running) return "Audit running in Exasol";
  if (d.run.status === "FAILED") return "The latest audit did not finish";
  return `Latest audit finished in ${seconds(d.run.duration_ms)}`;
}

/** Until the new run shows up, the latest run in the log is the previous one: do not show its steps as this run's. */
function useStarting(running: boolean, data: any) {
  const seen = useRef(false);
  const was = useRef(false);
  if (running && !was.current) seen.current = false;
  was.current = running;
  if (data?.running) seen.current = true;
  return running && !seen.current;
}

/** Step progress only, for screens where a re-run is a side step. */
export function LiveStrip({ running }: { running: boolean }) {
  const { data, error } = useLive(running);
  const starting = useStarting(running, data);
  if (!data && !error) return null;
  return (
    <div className="card pad" style={{ marginBottom: 16 }}>
      {error && <p className="small muted" style={{ marginTop: 0 }}>{error}</p>}
      {data && (
        <>
          <div className="live-head">
            <span className={`live-dot ${data.running || starting ? "on" : ""}`} />
            <b>{runWords(data, starting)}</b>
          </div>
          <Steps steps={data.steps} starting={starting} />
        </>
      )}
    </div>
  );
}

/**
 * What Exasol is doing during a re-run, read from its own system tables. Nothing here is simulated or computed.
 * With loadFirst, the wait before the audit starts is a book being loaded, and its statements are shown too.
 */
export function LivePanel({ running, loadFirst = false, onClose }: { running: boolean; loadFirst?: boolean; onClose: () => void }) {
  const { data, error } = useLive(running);
  const starting = useStarting(running, data);
  const watching = !!data && (data.running || (loadFirst && starting));
  // the last statement a poll saw, kept so there is something to read after a fast run ends
  const [held, setHeld] = useState<{ current: any; operators: any[] } | null>(null);
  const runRef = useRef<string | null>(null);
  // what the polls saw of this run, per step, so the finished run can be walked through at a talking pace
  const [rec, setRec] = useState<{ runId: string; steps: Record<string, any[]> } | null>(null);
  const [pick, setPick] = useState(0);
  const [stmtPick, setStmtPick] = useState<number | null>(null);
  const goStep = (i: number) => { setPick(i); setStmtPick(null); };

  useEffect(() => {
    if (starting) { setRec(null); goStep(0); }
  }, [starting]);

  useEffect(() => {
    if (!data) return;
    const rid = data.run?.run_id ?? null;
    if (rid !== runRef.current) {
      if (runRef.current !== null && data.running) setHeld(null);
      runRef.current = rid;
    }
    // a run too quick to sample still gets its walk-through: times and descriptions come from the run log
    if (data.running) setRec((r) => (r?.runId === rid ? r : { runId: rid, steps: {} }));
    const cur = data.current;
    if (!cur || cur.command_name === "COMMIT") return;
    if (!watching) return; // once the run is over, keep its last statement rather than a screen's read
    if (cur.step_id) {
      const sample = { current: cur, operators: data.operators };
      setRec((r) => {
        const base: { runId: string; steps: Record<string, any[]> } = r && r.runId === data.run.run_id ? r : { runId: data.run.run_id, steps: {} };
        const list: any[] = base.steps[cur.step_id] ?? [];
        const at = list.findIndex((x) => x.current.stmt_id === cur.stmt_id);
        // the same statement sampled twice: keep the later view unless it has lost its plan
        const next = at < 0 ? [...list, sample] : list.map((x, i) => (i === at && sample.operators.length >= x.operators.length ? sample : x));
        return { ...base, steps: { ...base.steps, [cur.step_id]: next } };
      });
    }
    if (!cur.audit && held?.current?.audit) return;
    if (!data.operators.length && held?.operators.length) return; // sampled before its plan existed: keep SQL and plan together
    setHeld({ current: cur, operators: data.operators });
  }, [data]);

  const executing = watching && data.current && data.current.command_name !== "COMMIT";
  const replay = !running && !starting && !data?.running && data?.run?.status === "DONE" && rec?.runId === data.run.run_id;
  const count = data?.steps?.length ?? 0;
  const step = replay ? data.steps[pick] : null;
  const caught: any[] = step ? rec!.steps[step.step_id] ?? [] : [];
  const fullest = caught.reduce((best, x, i) => (x.operators.length > caught[best].operators.length ? i : best), 0);
  const shown = stmtPick ?? fullest;
  const showing = replay ? caught[shown] : executing ? data : held;
  const stmt = showing?.current;

  useEffect(() => {
    if (!replay) return;
    const on = (e: KeyboardEvent) => {
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      if ((e.target as HTMLElement).closest?.("input, textarea, select, [contenteditable]")) return;
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      setStmtPick(null);
      setPick((p) => Math.min(count - 1, Math.max(0, p + (e.key === "ArrowLeft" ? -1 : 1))));
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [replay, count]);

  return (
    <div className="card pad live-panel">
      <div className="live-head">
        <span className={`live-dot ${data?.running || starting ? "on" : ""}`} />
        <b>{runWords(data, starting, loadFirst)}</b>
        {data && <span className="small muted">Exasol {data.version} · read from its system tables</span>}
        <button className="btn ghost mini" style={{ marginLeft: "auto" }} onClick={onClose}>Close</button>
      </div>
      {error && <p className="small muted">{error}</p>}
      {data && <Steps steps={data.steps} starting={starting} selected={replay ? pick : undefined} onPick={replay ? goStep : undefined} />}
      {step && (
        <div className="live-walk">
          <button className="btn ghost mini" aria-label="Previous step" disabled={pick === 0} onClick={() => goStep(pick - 1)}>←</button>
          <div>
            <div><b>Step {pick + 1} of {count} · {stepName(step.step_id)}</b> <span className="mono small muted">{seconds(step.duration_ms)}</span></div>
            <div className="small muted">{firstSentence(step.purpose)}</div>
          </div>
          <button className="btn ghost mini" aria-label="Next step" disabled={pick === count - 1} onClick={() => goStep(pick + 1)}>→</button>
        </div>
      )}
      <div className="grid g2 live-detail">
        <div>
          <div className="live-title">
            <h3>{replay ? "SQL sampled in this step" : executing ? "Executing now" : "Last statement seen"}</h3>
            {stmt && <span className="tag PERMITTED">{stmt.command_name}</span>}
          </div>
          {stmt ? (
            <>
              <p className="tiny muted mono">
                {stmt.user_name} · statement {stmt.stmt_id} · {stmt.temp_db_ram} MiB temporary memory{stmt.activity ? ` · ${stmt.activity}` : ""}
              </p>
              <pre className="live-sql">{stmt.sql_text}</pre>
            </>
          ) : <div className="empty">{replay ? "This step finished between samples." : "The SQL appears here as Exasol executes it."}</div>}
          {step && (
            <p className="tiny muted live-caught">
              {caught.length > 1 && caught.map((_, i) => (
                <button key={i} className={`btn mini ${i === shown ? "" : "ghost"}`} onClick={() => setStmtPick(i)}>{i + 1}</button>
              ))}
              {caught.length > 1 && <span>{caught.length} statements caught by sampling. </span>}
              <a href={`#/method/${step.step_id}`} target="_blank" rel="noreferrer">All SQL for this step</a>
            </p>
          )}
        </div>
        <div>
          <h3>{replay ? "Query plan when sampled" : executing ? "Query plan as it runs" : "Query plan at the last sample"}</h3>
          <p className="tiny muted">Sampled twice a second from <span className="mono">EXA_DBA_PROFILE_RUNNING</span>.</p>
          {showing?.operators?.length ? (
            <div className="live-plan">
              <table className="t">
                <thead><tr><th>Operator</th><th>Object</th><th className="r">Rows in</th><th className="r">Rows out</th><th className="r">Seconds</th><th>State</th></tr></thead>
                <tbody>{showing.operators.map((o: any) => (
                  <tr key={o.part_id}>
                    <td className="small">{o.part_name}</td>
                    <td className="small mono">{o.object_name?.startsWith("tmp_") ? <span className="faint">temporary result</span> : o.object_name ?? ""}</td>
                    <td className="r">{n(o.object_rows)}</td>
                    <td className="r">{n(o.out_rows)}</td>
                    <td className="r">{o.duration}</td>
                    <td className="small">{o.part_finished ? "Done" : executing ? <b>Running</b> : "Unfinished at sample"}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          ) : <div className="empty">{replay ? "No operators were caught for this step." : "Operators appear while a statement executes."}</div>}
        </div>
      </div>
    </div>
  );
}
