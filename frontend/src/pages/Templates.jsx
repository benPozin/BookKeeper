import { useEffect, useState } from "react";
import { api } from "../api";
import { Icon } from "../components/icons";

// internal bucket code -> plain folder name (no codes shown anywhere)
const BUCKET_NAMES = {
  "6a": "Car Expenses", "6b": "Car Lease", "6c": "Insurance",
  "6d": "Property Tax", "6e": "Mortgages", "6f": "Real Estate",
  "6g": "Rental Expenses", "6h": "T-Forms", "6i": "Utilities",
};

export function TemplatesPage() {
  const [data, setData] = useState(null);
  const [year, setYear] = useState("");
  const [building, setBuilding] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    api.templatesList().then((d) => {
      setData(d);
      setYear(d.years?.[0] || "");
    }).catch(() => {});
  }, []);

  const build = async () => {
    if (!year) return;
    setBuilding(true);
    setResult(null);
    try { setResult(await api.templatesBuild(year)); }
    finally { setBuilding(false); }
  };

  if (!data) return <p className="muted">Loading…</p>;

  return (
    <>
      <div className="page-head">
        <h1><Icon name="templates" size={26} />Expense Templates<span className="badge phase">Phase 4</span></h1>
        <p>Your real Excel templates, loaded. BookKeeper builds a working copy per
          year and attaches a "Supporting Docs" sheet of the matched receipts —
          your formulas stay untouched.</p>
      </div>

      <div className="panel">
        <h2><Icon name="templates" size={17} /> Loaded templates</h2>
        <div className="biz-grid">
          {data.templates.map((t) => (
            <div className="biz-card" key={t.key}>
              <div className="biz-name">{t.label}</div>
              <div className="biz-meta">
                {t.available
                  ? <>sheet: {t.sheets.join(", ") || "—"}</>
                  : <span style={{ color: "var(--rose)" }}>file missing</span>}
              </div>
              <div style={{ marginTop: 8 }}>
                <span className="pill cat-rental">{BUCKET_NAMES[t.bucket] || t.bucket}</span>{" "}
                {t.available
                  ? <span className="pill st-matched">loaded</span>
                  : <span className="pill st-unmatched">missing</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <h2><Icon name="export" size={17} /> Build working copies</h2>
        <div className="conn-row">
          <div className="conn-left">
            <span className="muted">Tax year</span>
            <select value={year} onChange={(e) => setYear(e.target.value)} style={{ width: "auto", minWidth: 120 }}>
              {(data.years || []).map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <button className="btn" onClick={build} disabled={building || !year}>
            <Icon name="templates" size={16} />{building ? "Building…" : "Build templates"}
          </button>
        </div>
        {result && (
          <div style={{ marginTop: 14 }}>
            <div className="scan-summary">Built {result.templates.filter((t) => t.status === "built").length} templates into <code>{result.out_dir}</code></div>
            <div className="table-wrap" style={{ marginTop: 12 }}>
              <table className="email-table">
                <thead><tr><th>Template</th><th>File</th><th>Bucket</th><th>Supporting docs</th></tr></thead>
                <tbody>
                  {result.templates.map((t, i) => (
                    <tr key={i}>
                      <td className="subj">{t.template}</td>
                      <td>{t.file || <span className="muted">—</span>}</td>
                      <td>{t.bucket ? <span className="pill cat-rental">{BUCKET_NAMES[t.bucket] || t.bucket}</span> : "—"}</td>
                      <td><span className="pill st-matched">{t.supporting_docs ?? 0}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
