import { useEffect, useState } from "react";
import { api } from "../api";
import { Icon } from "../components/icons";

export function Organizer() {
  const [rows, setRows] = useState([]);
  const [years, setYears] = useState([]);
  const [year, setYear] = useState("");
  const [plan, setPlan] = useState(null);
  const [result, setResult] = useState(null);
  const [unfileResult, setUnfileResult] = useState(null);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    api.folderStructure().then((r) => setRows(r.structure)).catch(() => {});
    api.organizerYears().then((d) => { setYears(d.years); setYear(d.years?.[0] || ""); }).catch(() => {});
  }, []);

  const preview = async () => {
    setBusy("plan"); setResult(null);
    try { setPlan(await api.organizerPlan(year)); } finally { setBusy(""); }
  };
  const apply = async () => {
    setBusy("apply");
    try { setResult(await api.organizerApply(year)); setPlan(null); setUnfileResult(null); } finally { setBusy(""); }
  };
  const unfile = async () => {
    if (!window.confirm(`Remove the built ${year} folder tree's copies and mark those documents matched again? Originals are never touched.`)) return;
    setBusy("unfile");
    try {
      setUnfileResult(await api.organizerUnfile(year));
      setResult(null);
    } finally { setBusy(""); }
  };

  return (
    <>
      <div className="page-head">
        <h1>
          <Icon name="organizer" size={26} />
          Folder Organizer
          <span className="badge phase">Phase 5</span>
        </h1>
        <p>Build the accountant-ready <strong>folder tree</strong> for a year:
          matched documents are copied into the right category folders and your
          templates are placed alongside. Preview first, then build — originals
          are never moved.</p>
      </div>

      <div className="panel">
        <div className="conn-row">
          <div className="conn-left">
            <span className="muted">Year</span>
            <select value={year} onChange={(e) => { setYear(e.target.value); setPlan(null); setResult(null); setUnfileResult(null); }}
              style={{ width: "auto", minWidth: 110 }}>
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn secondary" onClick={preview} disabled={!year || !!busy}>
              {busy === "plan" ? "…" : "Preview (dry-run)"}
            </button>
            <button className="btn secondary" onClick={unfile} disabled={!year || !!busy}>
              {busy === "unfile" ? "Removing…" : "Un-file year"}
            </button>
            <button className="btn" onClick={apply} disabled={!year || !!busy}>
              <Icon name="organizer" size={16} />{busy === "apply" ? "Building…" : "Build folders"}
            </button>
          </div>
        </div>

        {unfileResult && (
          <div className="scan-summary" style={{ marginTop: 14 }}>
            Un-filed <strong>{year}</strong>: {unfileResult.documents_reset} document{unfileResult.documents_reset === 1 ? "" : "s"} reset to matched,{" "}
            {unfileResult.files_removed} copied file{unfileResult.files_removed === 1 ? "" : "s"} removed. Originals were untouched.
          </div>
        )}
        {result && (
          <div className="scan-summary" style={{ marginTop: 14 }}>
            Built <strong>{year}</strong>: {result.documents_filed} documents filed,{" "}
            {result.templates_placed} templates placed in <code>{result.year_dir}</code>
          </div>
        )}
        {result?.skipped?.length > 0 && (
          <div className="scan-summary" style={{ marginTop: 10, background: "var(--rose-soft)", color: "var(--rose)", borderColor: "rgba(251,113,133,.3)" }}>
            {result.skipped.length} file{result.skipped.length > 1 ? "s" : ""} could not be copied:{" "}
            {result.skipped.map((s) => s.file).join(", ")}
          </div>
        )}
        {plan && (
          <div style={{ marginTop: 14 }}>
            <div className="muted" style={{ marginBottom: 10, fontSize: 13 }}>
              Dry-run: <strong>{plan.doc_count}</strong> documents → buckets,{" "}
              {plan.templates.length} templates. Nothing written yet.
            </div>
            <div className="table-wrap">
              <table className="email-table">
                <thead><tr><th>File</th><th>Business</th><th>Bucket</th><th>Destination</th></tr></thead>
                <tbody>
                  {plan.moves.map((m, i) => (
                    <tr key={i}>
                      <td className="subj">{m.file}</td>
                      <td>{m.business || <span className="muted">—</span>}</td>
                      <td><span className="pill cat-rental">{m.bucket}</span></td>
                      <td className="from">{m.to}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <h2><Icon name="organizer" size={17} /> Target folder structure</h2>
        {rows.map((r) => (
          <div className="tree-row" key={r.code}>
            <span className="code">{r.code}</span>
            <span className="name">{r.name}</span>
            <span className="note">{r.note}</span>
          </div>
        ))}
      </div>
    </>
  );
}
