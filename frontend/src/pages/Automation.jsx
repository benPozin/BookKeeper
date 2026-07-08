import { useEffect, useState } from "react";
import { api } from "../api";
import { Icon } from "../components/icons";

function summarizeGmail(g) {
  if (!g) return null;
  if (g.error) return `Gmail: error — ${g.error}`;
  if (g.skipped) return `Gmail: skipped (${g.skipped}).`;
  return `Gmail: ${g.new} new email${g.new === 1 ? "" : "s"}, ${g.total} total.`;
}

function summarizeDocuments(d) {
  if (!d) return null;
  if (d.error) return `Documents: error — ${d.error}`;
  const parts = [];
  if (d.matched) parts.push(`${d.matched} matched`);
  if (d.needs_review) parts.push(`${d.needs_review} need review`);
  if (d.unmatched) parts.push(`${d.unmatched} unmatched`);
  if (d.duplicate) parts.push(`${d.duplicate} duplicate`);
  if (d.extraction_failed) parts.push(`${d.extraction_failed} could not be read`);
  return `Documents: scanned ${d.scanned ?? 0} file${d.scanned === 1 ? "" : "s"}${parts.length ? " — " + parts.join(", ") : ""}.`;
}

function summarizeAi(a) {
  if (!a) return null;
  if (a.error) return `AI review: error — ${a.error}`;
  if (a.skipped) return `AI review: skipped (${a.skipped}).`;
  return `AI review: ${a.reviewed} reviewed${a.errors ? `, ${a.errors} errors` : ""}.`;
}

function summarizeBackup(b) {
  if (!b) return null;
  if (b.error) return `Backup: error — ${b.error}`;
  return null;
}

export function AutomationPage() {
  const [st, setSt] = useState(null);
  const [hour, setHour] = useState(2);
  const [minute, setMinute] = useState(0);
  const [busy, setBusy] = useState(false);
  const [runError, setRunError] = useState("");

  const load = () => api.automationStatus().then((s) => {
    setSt(s); setHour(s.hour); setMinute(s.minute);
  }).catch(() => {});
  useEffect(() => { load(); }, []);

  const toggle = async () => {
    setBusy(true);
    try {
      if (st?.enabled) await api.automationDisable();
      else await api.automationEnable(Number(hour), Number(minute));
      await load();
    } finally { setBusy(false); }
  };
  const runNow = async () => {
    setRunError("");
    const r = await api.automationRunNow();
    if (r?.error) setRunError(r.error);
    setTimeout(load, 1500);
  };

  if (!st) return <p className="muted">Loading…</p>;
  const ls = st.last_summary;

  return (
    <>
      <div className="page-head">
        <h1><Icon name="automation" size={26} />Daily Automation<span className="badge phase">Phase 6</span></h1>
        <p>Run the full pipeline on a schedule — scan Gmail, ingest new scans, and
          match everything — so your books stay current without lifting a finger.</p>
      </div>

      <div className="panel">
        <div className="conn-row">
          <div className="conn-left">
            {st.enabled
              ? <span className="badge active"><span className="dot green" /> Scheduled daily</span>
              : <span className="badge coming">Disabled</span>}
            {st.enabled && st.next_run && <span className="muted">Next run: <code>{st.next_run}</code></span>}
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <span className="muted">at</span>
            <input value={hour} onChange={(e) => setHour(e.target.value)} style={{ width: 52 }} />
            <span className="muted">:</span>
            <input value={minute} onChange={(e) => setMinute(e.target.value)} style={{ width: 52 }} />
            <button className="btn secondary" onClick={runNow}>Run now</button>
            <button className="btn" onClick={toggle} disabled={busy}>
              {st.enabled ? "Disable" : "Enable"}
            </button>
          </div>
        </div>
        <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
          Time is 24-hour (host local time). The scheduler runs while BookKeeper is
          open — on Windows, launch it at login to keep it always on.
        </p>
        {runError && (
          <div className="scan-summary" style={{ marginTop: 12, background: "var(--gold-soft)", color: "var(--gold-deep)", borderColor: "var(--gold-line)" }}>
            {runError}
          </div>
        )}
      </div>

      <div className="panel">
        <h2><Icon name="automation" size={17} /> Last run</h2>
        {ls ? (
          <div>
            <div className="scan-summary">Finished {ls.finished || ls.started}</div>
            <ul className="bullets" style={{ marginTop: 8 }}>
              {[summarizeGmail(ls.gmail), summarizeDocuments(ls.documents), summarizeAi(ls.ai), summarizeBackup(ls.backup)]
                .filter(Boolean)
                .map((line, i) => <li key={i}>{line}</li>)}
            </ul>
          </div>
        ) : <p className="muted">Hasn't run yet. Click "Run now" to test it.</p>}
      </div>

      <div className="panel">
        <div className="needs">
          <h4 style={{ color: "var(--gold)" }}>Keep it running on Windows</h4>
          <ol style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8, fontSize: 13, color: "var(--text-dim)" }}>
            <li>Add a Task Scheduler entry (or Startup shortcut) that launches BookKeeper at login.</li>
            <li>Enable the daily schedule above — it fires while the app is running.</li>
            <li>Check this page any morning to see the last run's results.</li>
          </ol>
        </div>
      </div>
    </>
  );
}
