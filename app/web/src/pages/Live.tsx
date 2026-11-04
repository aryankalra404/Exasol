import { useEffect, useRef, useState } from "react";
import { api, n, post, seconds } from "../lib";

const FAST_MS = 500;
const IDLE_MS = 3000;

/** Polls /live: quickly while a run is going or about to start, slowly otherwise, not at all in a hidden tab. */
function useLive(starting = false) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const startingRef = useRef(starting);
  startingRef.current = starting;
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
        } catch (e: any) {
          if (!live) return;
          setError(String(e.message ?? e));
        }
      }
      timer = window.setTimeout(tick, fast ? FAST_MS : IDLE_MS);
    };
    tick();
    return () => { live = false; clearTimeout(timer); };
  }, []);
  return { data, error };
}

/** "S60_CANDIDATE_CONVENTIONS" to "Candidate conventions". */
const stepName = (id: string) => {
  const s = id.replace(/^S\d+_/, "").replace(/_/g, " ").toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
};
const stepCode = (id: string) => id.split("_")[0];
const STEP_WORDS: Record<string, string> = { done: "Done", running: "Running", failed: "Failed", waiting: "Waiting" };

function Steps({ steps }: { steps: any[] }) {
  return (
    <ol className="live-steps">
      {steps.map((s) => (
        <li key={s.step_id} className={s.state} title={s.purpose}>
          <span className="mono tiny">{stepCode(s.step_id)}</span>
          <b>{stepName(s.step_id)}</b>
          <span className="mono tiny">{s.duration_ms != null ? seconds(s.duration_ms) : STEP_WORDS[s.state]}</span>
        </li>
      ))}
    </ol>
  );
}

function runWords(d: any): string {
  if (!d?.run) return "No audit has run yet";
  if (d.running) return "Audit running in Exasol";
  if (d.run.status === "FAILED") return "The latest audit did not finish";
  return `Latest audit finished in ${seconds(d.run.duration_ms)}`;
}

/** Step progress for the screens that start a run. */
export function LiveStrip({ running }: { running: boolean }) {
  const { data } = useLive(running);
  if (!data) return null;
  return (
    <div className="card pad" style={{ marginBottom: 16 }}>
      <div className="live-head">
        <span className={`live-dot ${data.running ? "on" : ""}`} />
        <b>{runWords(data)}</b>
        <a className="small" href="#/live" style={{ marginLeft: "auto" }}>See the SQL and operators</a>
      </div>
      <Steps steps={data.steps} />
    </div>
  );
}

const key = (s: any) => `${s.session_id}:${s.stmt_id}`;

export default function Live({ onRun }: { onRun: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const { data, error } = useLive(busy);
  // what the polls saw during the latest run, kept so the view still has something to read after a fast run ends
  const [seen, setSeen] = useState<any[]>([]);
  const [held, setHeld] = useState<{ current: any; operators: any[] } | null>(null);
  const runRef = useRef<string | null>(null);

  useEffect(() => {
    if (!data) return;
    const rid = data.run?.run_id ?? null;
    if (rid !== runRef.current) {
      runRef.current = rid;
      if (data.running) { setSeen([]); setHeld(null); }
    }
    const cur = data.current;
    if (!cur || cur.command_name === "COMMIT") return;
    if (!data.running && !cur.audit && held?.current?.audit) return; // keep the audit's last statement over a screen's read
    setHeld({ current: cur, operators: data.operators });
    if (cur.audit) {
      setSeen((list) => {
        const hit = list.find((x) => key(x) === key(cur));
        if (hit) return list.map((x) => (key(x) === key(cur) ? cur : x));
        return [cur, ...list].slice(0, 60);
      });
    }
  }, [data]);

  const start = async () => {
    setBusy(true); setErr(null);
    try {
      await post("/runs", { label: "Re-run from Exasol live view" });
      onRun();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  const executing = data?.current && data.current.command_name !== "COMMIT";
  const showing = executing ? data : held;
  const stmt = showing?.current;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Exasol live</h1>
          <p>What the database is doing right now, read from its own system tables. Nothing on this page is simulated or computed by the app.</p>
        </div>
        <button className="btn" onClick={start} disabled={busy || data?.running}>{busy || data?.running ? "Running in Exasol…" : "Re-run audit with current policy"}</button>
      </div>
      {(err || error) && <div className="verdict warn" style={{ marginBottom: 16 }}>{err || error}</div>}

      {data && (
        <div className="card pad" style={{ marginBottom: 16 }}>
          <div className="live-head">
            <span className={`live-dot ${data.running ? "on" : ""}`} />
            <b>{runWords(data)}</b>
            <span className="small muted">Exasol {data.version} · {n(data.open_sessions)} open sessions{data.run?.label ? ` · ${data.run.label}` : ""}</span>
          </div>
          <Steps steps={data.steps} />
        </div>
      )}

      <div className="grid g2" style={{ alignItems: "start" }}>
        <div className="card pad">
          <div className="live-title">
            <h2>{executing ? "Executing now" : "Last statement seen"}</h2>
            {stmt && <span className="tag PERMITTED">{stmt.command_name}</span>}
          </div>
          {stmt ? (
            <>
              <p className="small muted mono">
                {stmt.user_name} · statement {stmt.stmt_id} · {stmt.temp_db_ram} MiB temporary memory{stmt.activity ? ` · ${stmt.activity}` : ""}
              </p>
              <pre className="live-sql">{stmt.sql_text}</pre>
            </>
          ) : <div className="empty">Nothing executing. Start a re-run to watch it here.</div>}
          {executing && data.others.length > 0 && (
            <p className="small muted">Also executing: {data.others.map((o: any) => `${o.command_name} by ${o.user_name}`).join(", ")}</p>
          )}
        </div>
        <div className="card">
          <div className="pad" style={{ paddingBottom: 0 }}>
            <h2>{executing ? "Query plan as it runs" : "Query plan at the last sample"}</h2>
            <p className="small muted">Each operator as Exasol reports it for this statement, from <span className="mono">EXA_DBA_PROFILE_RUNNING</span>.</p>
          </div>
          {showing?.operators?.length ? (
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
          ) : <div className="empty">Operators appear while a statement executes.</div>}
        </div>
      </div>

      <section className="section">
        <header><div><h2>Audit statements seen</h2>
          <p>Newest first. The screen samples Exasol twice a second, so a statement that finishes between samples is not listed. Step times above are complete.</p></div></header>
        <div className="card">
          {seen.length > 0 ? (
            <table className="t">
              <thead><tr><th>Statement</th><th>Command</th><th>SQL</th></tr></thead>
              <tbody>{seen.map((s) => (
                <tr key={key(s)}><td className="mono small">{s.stmt_id}</td><td className="small">{s.command_name}</td>
                  <td className="mono small live-line">{s.sql_text.replace(/\s+/g, " ").slice(0, 120)}</td></tr>
              ))}</tbody>
            </table>
          ) : <div className="empty">Start a re-run with this page open to fill this list.</div>}
        </div>
      </section>
    </>
  );
}
