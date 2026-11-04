import { useEffect, useRef, useState } from "react";
import { api, n, seconds } from "../lib";

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

function Steps({ steps, starting }: { steps: any[]; starting: boolean }) {
  return (
    <ol className="live-steps">
      {steps.map((s) => {
        const state = starting ? "waiting" : s.state;
        return (
          <li key={s.step_id} className={state} title={s.purpose}>
            <span className="mono tiny">{stepCode(s.step_id)}</span>
            <b>{stepName(s.step_id)}</b>
            <span className="mono tiny">{!starting && s.duration_ms != null ? seconds(s.duration_ms) : STEP_WORDS[state]}</span>
          </li>
        );
      })}
    </ol>
  );
}

function runWords(d: any, starting: boolean): string {
  if (starting) return "Starting audit in Exasol";
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

/** What Exasol is doing during a re-run, read from its own system tables. Nothing here is simulated or computed. */
export function LivePanel({ running, onClose }: { running: boolean; onClose: () => void }) {
  const { data, error } = useLive(running);
  const starting = useStarting(running, data);
  // the last statement a poll saw, kept so there is something to read after a fast run ends
  const [held, setHeld] = useState<{ current: any; operators: any[] } | null>(null);
  const runRef = useRef<string | null>(null);

  useEffect(() => {
    if (!data) return;
    const rid = data.run?.run_id ?? null;
    if (rid !== runRef.current) {
      if (runRef.current !== null && data.running) setHeld(null);
      runRef.current = rid;
    }
    const cur = data.current;
    if (!cur || cur.command_name === "COMMIT") return;
    if (!data.running) return; // once the run is over, keep its last statement rather than a screen's read
    if (!cur.audit && held?.current?.audit) return;
    setHeld({ current: cur, operators: data.operators });
  }, [data]);

  const executing = data?.running && data.current && data.current.command_name !== "COMMIT";
  const showing = executing ? data : held;
  const stmt = showing?.current;

  return (
    <div className="card pad live-panel">
      <div className="live-head">
        <span className={`live-dot ${data?.running || starting ? "on" : ""}`} />
        <b>{runWords(data, starting)}</b>
        {data && <span className="small muted">Exasol {data.version} · read from its system tables</span>}
        <button className="btn ghost mini" style={{ marginLeft: "auto" }} onClick={onClose}>Close</button>
      </div>
      {error && <p className="small muted">{error}</p>}
      {data && <Steps steps={data.steps} starting={starting} />}
      <div className="grid g2 live-detail">
        <div>
          <div className="live-title">
            <h3>{executing ? "Executing now" : "Last statement seen"}</h3>
            {stmt && <span className="tag PERMITTED">{stmt.command_name}</span>}
          </div>
          {stmt ? (
            <>
              <p className="tiny muted mono">
                {stmt.user_name} · statement {stmt.stmt_id} · {stmt.temp_db_ram} MiB temporary memory{stmt.activity ? ` · ${stmt.activity}` : ""}
              </p>
              <pre className="live-sql">{stmt.sql_text}</pre>
            </>
          ) : <div className="empty">The SQL appears here as Exasol executes it.</div>}
        </div>
        <div>
          <h3>{executing ? "Query plan as it runs" : "Query plan at the last sample"}</h3>
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
          ) : <div className="empty">Operators appear while a statement executes.</div>}
        </div>
      </div>
    </div>
  );
}
