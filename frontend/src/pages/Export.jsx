import { useEffect, useState } from "react";
import { api } from "../api";
import { Icon } from "../components/icons";
import { EmptyState } from "../components/ui";

const fmtSize = (bytes) => {
  if (bytes == null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 10240 ? 1 : 0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};
const fmtMoney = (v) =>
  `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const FILE_ICON = { excel: "templates", pdf: "documents", text: "book" };

function TreeRows({ entries, depth = 0, startIndex = { i: 0 } }) {
  return entries.map((e) => {
    const row = startIndex.i++;
    if (e.type === "folder") {
      return (
        <div key={`${depth}-${e.name}`}>
          <div className="fs-row fs-folder" style={{ "--depth": depth, "--i": Math.min(row, 24) }}>
            <Icon name="organizer" size={16} />
            <span className="fs-name">{e.name}</span>
            {e.files === 0 ? (
              <span className="fs-meta"><span className="pill st-unmatched">empty</span></span>
            ) : (
              <span className="fs-meta">{e.files} file{e.files > 1 ? "s" : ""} · {fmtSize(e.size)}</span>
            )}
          </div>
          <TreeRows entries={e.children} depth={depth + 1} startIndex={startIndex} />
        </div>
      );
    }
    return (
      <div key={`${depth}-${e.name}`} className="fs-row fs-file"
        style={{ "--depth": depth, "--i": Math.min(row, 24) }}>
        <Icon name={FILE_ICON[e.kind] || "documents"} size={15} />
        <span style={{ minWidth: 0 }}>
          <span className="fs-name">{e.name}</span>
          <span className="fs-desc">{e.desc}</span>
        </span>
        <span className="fs-meta">
          {e.amount != null && <span className="pill st-matched">{fmtMoney(e.amount)}</span>}
          {fmtSize(e.size)}
        </span>
      </div>
    );
  });
}

export function ExportPage() {
  const [years, setYears] = useState([]);
  const [year, setYear] = useState("");
  const [summary, setSummary] = useState(null);
  const [tree, setTree] = useState(null);
  const [pkg, setPkg] = useState(null);
  const [busy, setBusy] = useState("");
  const [revealed, setRevealed] = useState("");

  useEffect(() => {
    api.exportYears().then((d) => { setYears(d.years); setYear(d.years?.[0] || ""); }).catch(() => {});
  }, []);
  useEffect(() => {
    setPkg(null);
    setTree(null);
    setRevealed("");
    if (!year) return;
    api.exportSummary(year).then(setSummary).catch(() => {});
    api.exportTree(year).then(setTree).catch(() => {});
  }, [year]);

  const build = async () => {
    if (summary?.pending_documents > 0) {
      const ok = window.confirm(
        `${summary.pending_documents} document(s) for ${year} are still unreviewed and will NOT be in this package. Build it anyway?`
      );
      if (!ok) return;
    }
    setBusy("build");
    try {
      setPkg(await api.exportBuild(year));
      setTree(await api.exportTree(year)); // refresh: the zip card appears
    } finally { setBusy(""); }
  };

  const reveal = async (target) => {
    setBusy(target);
    try {
      const r = await api.exportReveal(year, target);
      setRevealed(r.opened);
    } catch (e) {
      setRevealed("");
      window.alert(e.message);
    } finally { setBusy(""); }
  };

  const onWindows = tree?.platform?.startsWith("win");
  const finderName = onWindows ? "Explorer" : tree?.platform === "darwin" ? "Finder" : "file manager";
  const zip = tree?.zip;

  return (
    <>
      <div className="page-head">
        <h1><Icon name="export" size={26} />Accountant Export<span className="badge phase">Phase 7</span></h1>
        <p>Everything below is <strong>exactly</strong> what lands on disk and inside the
          zip — every folder, every file, and what each one is. When it looks right,
          package it and open it in {finderName} to see the same thing for real.</p>
      </div>

      <div className="panel">
        <div className="conn-row">
          <div className="conn-left">
            <span className="muted">Tax year</span>
            <select value={year} onChange={(e) => setYear(e.target.value)} style={{ width: "auto", minWidth: 110 }}>
              {years.length === 0 && <option value="">— build folders first —</option>}
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
            {tree && !tree.error && (
              <span className="muted" style={{ fontSize: 12.5 }}>
                {tree.total_files} files · {fmtSize(tree.total_size)}
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn secondary" onClick={() => reveal("folder")}
              disabled={!year || !!busy || !tree || !!tree.error}
              title={`Open this exact folder in ${finderName}`}>
              <Icon name="organizer" size={16} />
              {busy === "folder" ? "Opening…" : `Reveal in ${finderName}`}
            </button>
            <button className="btn" onClick={build} disabled={!year || !!busy}>
              <Icon name="export" size={16} />{busy === "build" ? "Packaging…" : "Build package"}
            </button>
          </div>
        </div>

        {summary?.pending_documents > 0 && (
          <div className="scan-summary" style={{ marginTop: 16, background: "var(--gold-soft)", color: "var(--gold-deep)", borderColor: "var(--gold-line)" }}>
            <Icon name="alert" size={15} /> {summary.pending_documents} document{summary.pending_documents > 1 ? "s" : ""} for {year} still{" "}
            {summary.pending_documents > 1 ? "need" : "needs"} review and won't be in this package unless you assign{" "}
            {summary.pending_documents > 1 ? "them" : "it"} on the Documents page first.
          </div>
        )}
        {revealed && (
          <div className="scan-summary" style={{ marginTop: 14 }}>
            Opened in {finderName}: <code>{revealed}</code>
          </div>
        )}
      </div>

      {/* The zip: what downloads, and where it lives on disk */}
      {zip?.exists && (
        <div className="panel certificate">
          <div style={{ display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
            <span className="cert-seal">{tree.total_files}</span>
            <div style={{ minWidth: 0 }}>
              <div className="muted" style={{ fontSize: 13 }}>
                Packaged {zip.built_at ? `on ${zip.built_at.replace("T", " at ")}` : ""}
              </div>
              <div style={{ fontFamily: "var(--display)", fontSize: 18, fontWeight: 600 }}>
                {zip.name} <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>({fmtSize(zip.size)})</span>
              </div>
              <div className="muted" style={{ fontSize: 12.5, overflowWrap: "anywhere" }}>
                Lives at <code>{zip.path}</code>
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 18, flexWrap: "wrap" }}>
            <a className="btn gold" href={api.exportDownloadUrl(year)} style={{ textDecoration: "none" }}>
              <Icon name="export" size={16} /> Download {zip.name}
            </a>
            <button className="btn secondary" onClick={() => reveal("zip")} disabled={!!busy}>
              <Icon name="organizer" size={16} />
              {busy === "zip" ? "Opening…" : `Show zip in ${finderName}`}
            </button>
          </div>
          {pkg?.manifest && <pre className="manifest">{pkg.manifest}</pre>}
        </div>
      )}

      {/* The package, file by file */}
      <div className="panel">
        <h2><Icon name="organizer" size={17} /> Inside the package</h2>
        {tree?.error && (
          <EmptyState icon="organizer" title="Nothing built yet"
            hint={tree.error} />
        )}
        {tree && !tree.error && (
          <>
            <div className="muted" style={{ fontSize: 12.5, margin: "6px 0 12px", overflowWrap: "anywhere" }}>
              On disk at <code>{tree.root}</code> — the zip mirrors this exactly, plus a MANIFEST.txt.
            </div>
            <div className="fs-tree">
              <TreeRows entries={tree.tree} />
            </div>
          </>
        )}
      </div>
    </>
  );
}
