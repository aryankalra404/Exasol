import { useEffect, useRef, useState } from "react";
import { api, day, go, inr, seconds, useApi, useRoute } from "./lib";
import Book from "./pages/Book";
import Ledger from "./pages/Ledger";
import Loan from "./pages/Loan";
import Queues from "./pages/Queues";
import Regression from "./pages/Regression";
import Policy from "./pages/Policy";
import Method from "./pages/Method";
import Letter from "./pages/Letter";
import Review from "./pages/Review";
import Data, { FirstRun } from "./pages/Data";

export type Run = {
  run_id: string; dataset_id: string; started_at: string; duration_ms: number; status: string; label: string;
  refund_paise: number; refund_loans: number;
};

const NAV: [string, [string, string][]][] = [
  ["Audit", [["book", "Overview"], ["ledger", "Refund ledger"], ["review", "Review & release"], ["queues", "Work queues"], ["regression", "Fix coverage"]]],
  ["Controls", [["policy", "Policy & re-runs"], ["method", "Method & lineage"], ["data", "Data"]]],
];

export default function App() {
  const { parts, params } = useRoute();
  const [runs, setRuns] = useState<Run[]>([]);
  const [runId, setRunId] = useState<string>(() => localStorage.getItem("run") ?? "latest");
  const [ver, setVer] = useState(0);
  const status = useApi<any>("/data/status", [ver]).data;

  useEffect(() => {
    api<Run[]>("/runs").then((r) => {
      const done = r.filter((x) => x.status === "DONE");
      setRuns(done);
      if (runId !== "latest" && !done.some((x) => x.run_id === runId)) setRunId("latest");
    }).catch(() => setRuns([]));
  }, [ver, parts[0]]);

  const pickRun = (id: string) => {
    setRunId(id);
    try { localStorage.setItem("run", id); } catch { /* private mode */ }
  };
  const current = runs.find((r) => r.run_id === runId) ?? runs[0];
  const rid = runId === "latest" ? "latest" : runId;
  const page = parts[0] ?? "book";
  const empty = status && (!status.loaded || !status.latest_run);
  const topbar = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // sticky bars on the pages sit directly under the top bar, whose height changes when it wraps
    const el = topbar.current;
    if (!el) return;
    const ro = new ResizeObserver(() => document.documentElement.style.setProperty("--topbar-h", `${el.offsetHeight}px`));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">
          <b>Sahi <i>Byaaj</i></b>
          <span>सही ब्याज · interest audit</span>
        </div>
        <nav className="nav">
          {NAV.map(([group, items]) => (
            <div key={group} className="nav-group">
              <div className="nav-label">{group}</div>
              {items.map(([k, label]) => (
                <a key={k} href={`#/${k}`} className={page === k || (k === "ledger" && (page === "loan" || page === "letter")) ? "on" : ""}>{label}</a>
              ))}
            </div>
          ))}
        </nav>
        <div className="side-foot">
          All figures are computed by SQL in Exasol.
          <br />Demo data is synthetic.
        </div>
      </aside>
      <main className="main">
        <div className="topbar" ref={topbar}>
          <div className="runchip">
            <span className="dot" />
            <span>Audit run</span>
            <select value={runId} onChange={(e) => pickRun(e.target.value)}>
              <option value="latest">Latest run</option>
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id.slice(0, 8)} · {r.label || r.dataset_id} · {inr(r.refund_paise, { paise: false })}
                </option>
              ))}
            </select>
            {current && <span className="faint">{current.dataset_id} · {day(current.started_at)} · {seconds(current.duration_ms)} in Exasol</span>}
            {status?.loaded && <a href="#/data" className={`tag ${status.synthetic ? "PERMITTED" : "FAIR"}`} style={{ textDecoration: "none" }}>{status.synthetic ? "Synthetic sample" : "Uploaded extract"}</a>}
          </div>
          <Search />
        </div>
        {page === "data" && <Data onChanged={() => { pickRun("latest"); setVer((v) => v + 1); }} />}
        {page !== "data" && empty && <FirstRun />}
        {!empty && page === "book" && <Book runId={rid} />}
        {!empty && page === "ledger" && <Ledger runId={rid} params={params} />}
        {!empty && page === "review" && <Review runId={rid} params={params} onLatest={() => pickRun("latest")} />}
        {!empty && page === "loan" && <Loan runId={rid} loanId={parts[1]} period={params.get("period")} />}
        {!empty && page === "queues" && <Queues runId={rid} tab={parts[1] ?? "gaps"} onRun={() => { pickRun("latest"); setVer((v) => v + 1); }} />}
        {!empty && page === "regression" && <Regression runId={rid} branch={parts[1]} />}
        {!empty && page === "policy" && <Policy runs={runs} onRun={() => { pickRun("latest"); setVer((v) => v + 1); }} />}
        {!empty && page === "method" && <Method runId={rid} step={parts[1]} />}
        {!empty && page === "letter" && <Letter runId={rid} loanId={parts[1]} lang={params.get("lang") ?? ""} />}
      </main>
    </div>
  );
}

function Search() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const { data } = useApi<any[]>(q.length >= 2 ? `/search?q=${encodeURIComponent(q)}` : null, [q]);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);
  return (
    <div className="search" ref={ref}>
      <input
        placeholder="Search by loan ID or borrower name"
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onKeyDown={(e) => { if (e.key === "Enter" && data?.[0]) { go(`/loan/${data[0].loan_id}`); setOpen(false); } }}
      />
      {open && q.length >= 2 && data && (
        <div className="results">
          {data.length === 0 && <div className="pad small muted">No match</div>}
          {data.map((r) => (
            <a key={r.loan_id} href={`#/loan/${r.loan_id}`} onClick={() => setOpen(false)}>
              <span>{r.display_name}</span>
              <span className="mono small faint">{r.loan_id} · {r.branch_id}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
