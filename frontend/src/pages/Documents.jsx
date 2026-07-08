import React, { useEffect, useState } from "react";
import { api } from "../api";
import { Icon } from "../components/icons";
import { CountUp, EmptyState, JobProgress, pollJob } from "../components/ui";

const DOC_STATUS_META = {
  matched: { label: "Matched", cls: "st-matched" },
  needs_review: { label: "Needs review", cls: "st-review" },
  unmatched: { label: "Unmatched", cls: "st-unmatched" },
  filed: { label: "Filed", cls: "st-filed" },
  extraction_failed: { label: "Could not read", cls: "st-unmatched" },
};

function DocRow({ doc, index = 0, businesses, buckets, years, selected, onToggleSelect, onSaved }) {
  const [edit, setEdit] = useState(false);
  const [bizId, setBizId] = useState(doc.business_id || "");
  const [year, setYear] = useState(doc.year || "");
  const [bucket, setBucket] = useState(doc.bucket || "");
  const [saving, setSaving] = useState(false);

  const meta = DOC_STATUS_META[doc.status] || { label: doc.status, cls: "" };
  const save = async () => {
    setSaving(true);
    await api.docConfirm(doc.id, {
      business_id: bizId ? Number(bizId) : null, year: year || null,
      bucket: bucket || null, status: "matched",
    });
    setSaving(false);
    setEdit(false);
    onSaved();
  };
  const undo = async () => {
    await api.docConfirm(doc.id, { status: "needs_review" });
    onSaved();
  };

  return (
    <tr style={{ "--i": Math.min(index, 20) }}>
      <td>
        <input type="checkbox" checked={selected} onChange={() => onToggleSelect(doc.id)} />
      </td>
      <td className="subj" title={doc.reason}>
        <a href={api.docFileUrl(doc.id)} target="_blank" rel="noreferrer">{doc.filename}</a>
        {(doc.vendor || doc.doc_date) && (
          <div className="muted" style={{ fontSize: 12 }}>
            {[doc.vendor, doc.doc_date].filter(Boolean).join(" · ")}
          </div>
        )}
        {doc.summary && (
          <div className="ai-summary">
            <span className="pill ai-pill">AI</span> {doc.summary}
          </div>
        )}
      </td>
      <td><span className={`pill ${meta.cls}`}>{meta.label}</span></td>
      <td><span className={`pill conf-${doc.confidence}`}>{doc.confidence}</span></td>
      {edit ? (
        <>
          <td>
            <select value={bizId} onChange={(e) => setBizId(e.target.value)} style={{ minWidth: 130 }}>
              <option value="">—</option>
              {businesses.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </td>
          <td>
            <select value={year} onChange={(e) => setYear(e.target.value)} style={{ minWidth: 84 }}>
              <option value="">—</option>
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </td>
          <td>
            <select value={bucket} onChange={(e) => setBucket(e.target.value)}>
              <option value="">—</option>
              {Object.entries(buckets).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </td>
          <td />
          <td>
            <button className="btn" style={{ padding: "6px 12px" }} onClick={save} disabled={saving}>
              {saving ? "…" : "Save"}
            </button>
          </td>
        </>
      ) : (
        <>
          <td>{doc.business || <span className="muted">—</span>}</td>
          <td>{doc.year || <span className="muted">—</span>}</td>
          <td>{doc.bucket_name ? <span className="pill cat-rental">{doc.bucket_name}</span> : <span className="muted">—</span>}</td>
          <td className="nowrap">
            {doc.amount != null
              ? `$${doc.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
              : <span className="muted">—</span>}
          </td>
          <td>
            <button className="back-link" onClick={() => setEdit(true)}>
              {doc.status === "matched" ? "Edit" : "Assign"}
            </button>
            {(doc.status === "matched" || doc.status === "filed") && (
              <button className="back-link" style={{ marginLeft: 10 }} onClick={undo}>Undo</button>
            )}
          </td>
        </>
      )}
    </tr>
  );
}

function ReviewQueue({ businesses, buckets, onDone }) {
  const [state, setState] = useState(null);
  const [bizId, setBizId] = useState("");
  const [year, setYear] = useState("");
  const [bucket, setBucket] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const s = await api.docReviewQueue();
    setState(s);
    setBizId(s.document?.business_id || "");
    setYear(s.document?.year || "");
    setBucket(s.document?.bucket || "");
  };
  useEffect(() => { load(); }, []);

  const approve = async () => {
    if (!state?.document) return;
    setSaving(true);
    try {
      await api.docConfirm(state.document.id, {
        business_id: bizId ? Number(bizId) : null, year: year || null,
        bucket: bucket || null, status: "matched",
      });
      await load();
      onDone();
    } finally { setSaving(false); }
  };
  const markUnmatched = async () => {
    if (!state?.document) return;
    setSaving(true);
    try {
      await api.docConfirm(state.document.id, { status: "unmatched" });
      await load();
      onDone();
    } finally { setSaving(false); }
  };

  if (!state) return <p className="muted">Loading…</p>;
  if (!state.document) {
    return <EmptyState icon="check" title="All caught up" hint="Nothing is waiting on your review." />;
  }
  const d = state.document;

  return (
    <div>
      <div className="muted" style={{ marginBottom: 14, fontSize: 13 }}>
        <strong>{state.remaining}</strong> document{state.remaining > 1 ? "s" : ""} waiting for a decision
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 20 }}>
        <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", overflow: "hidden" }}>
          <iframe src={api.docFileUrl(d.id)} title={d.filename} style={{ width: "100%", height: 520, border: "none", display: "block" }} />
        </div>
        <div>
          <div style={{ fontFamily: "var(--display)", fontWeight: 600, fontSize: 16, marginBottom: 6 }}>{d.filename}</div>
          <div className="muted" style={{ fontSize: 12.5, marginBottom: 16 }}>{d.reason}</div>
          <div className="field">
            <label>Business</label>
            <select value={bizId} onChange={(e) => setBizId(e.target.value)}>
              <option value="">—</option>
              {businesses.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Year</label>
            <select value={year} onChange={(e) => setYear(e.target.value)}>
              <option value="">—</option>
              {(state.known_years || []).map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Folder</label>
            <select value={bucket} onChange={(e) => setBucket(e.target.value)}>
              <option value="">—</option>
              {Object.entries(buckets).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <button className="btn" onClick={approve} disabled={saving} style={{ width: "100%", marginBottom: 8 }}>
            {saving ? "Saving…" : "Approve & next"}
          </button>
          <button className="btn secondary" onClick={markUnmatched} disabled={saving} style={{ width: "100%" }}>
            Can't tell — skip
          </button>
        </div>
      </div>
    </div>
  );
}

export function DocumentsPage() {
  const [status, setStatus] = useState(null);
  const [docs, setDocs] = useState([]);
  const [businesses, setBusinesses] = useState([]);
  const [years, setYears] = useState([]);
  const [filters, setFilters] = useState({ status: "", business_id: "", confidence: "" });
  const [busy, setBusy] = useState("");
  const [scanResult, setScanResult] = useState(null);
  const [scanJob, setScanJob] = useState(null);
  const [ai, setAi] = useState(null);
  const [aiResult, setAiResult] = useState(null);
  const [aiJob, setAiJob] = useState(null);
  const [overview, setOverview] = useState(null);
  const [view, setView] = useState("table");
  const [selected, setSelected] = useState(() => new Set());

  const loadMeta = async () => {
    const [st, bz, aiSt, yrs] = await Promise.all([
      api.docStatus(), api.gmailBusinesses(), api.aiStatus(), api.organizerYears(),
    ]);
    setStatus(st);
    setBusinesses(bz.businesses);
    setAi(aiSt);
    setYears(yrs.years);
  };

  const runAi = async () => {
    setBusy("ai");
    setAiResult(null);
    setAiJob(null);
    try {
      const { job_id } = await api.aiReviewAsync();
      const res = await pollJob(job_id, setAiJob);
      setAiResult(res);
      await loadMeta();
      await fetchDocs();
    } catch (e) {
      setAiResult({ error: e.message });
    } finally { setBusy(""); setAiJob(null); }
  };
  const toggleAi = async () => { const r = await api.aiEnable(!ai?.enabled); setAi(r); };
  const getOverview = async () => {
    setBusy("overview");
    try { setOverview(await api.aiOverview()); } finally { setBusy(""); }
  };
  const fetchDocs = React.useCallback(() => {
    return api.docList(filters).then((r) => setDocs(r.documents));
  }, [filters]);

  useEffect(() => { loadMeta().catch(() => {}); }, []);
  useEffect(() => { fetchDocs().catch(() => {}); }, [fetchDocs]);

  const run = async (which) => {
    setBusy(which);
    setScanResult(null);
    setScanJob(null);
    try {
      if (which === "samples") await api.docGenerateSamples();
      const { job_id } = which === "extract"
        ? await api.docExtractFieldsAsync()
        : await api.docScanAsync();
      const res = await pollJob(job_id, setScanJob);
      setScanResult(res);
      await loadMeta();
      await fetchDocs();
    } catch (e) {
      setScanResult({ error: e.message });
    } finally {
      setBusy("");
      setScanJob(null);
    }
  };

  const toggleSelect = (id) => {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const approveSelected = async () => {
    if (selected.size === 0) return;
    setBusy("bulk");
    try {
      await api.docBulk({ ids: [...selected], status: "matched" });
      setSelected(new Set());
      await loadMeta();
      await fetchDocs();
    } finally { setBusy(""); }
  };

  const approveAllMediumPlus = async () => {
    const ids = docs
      .filter((d) => d.status === "needs_review" && (d.confidence === "high" || d.confidence === "medium"))
      .map((d) => d.id);
    if (ids.length === 0) return;
    setBusy("bulk");
    try {
      await api.docBulk({ ids, status: "matched" });
      await loadMeta();
      await fetchDocs();
    } finally { setBusy(""); }
  };

  if (!status) return <p className="muted">Loading…</p>;
  const c = status.counts;
  const approvableCount = docs.filter(
    (d) => d.status === "needs_review" && (d.confidence === "high" || d.confidence === "medium")
  ).length;

  return (
    <>
      <div className="page-head">
        <h1>
          <Icon name="documents" size={26} />
          Documents
          <span className="badge phase">Phase 2</span>
        </h1>
        <p>Read scanned PDFs, match each to a business &amp; year, suggest its
          folder, and drop duplicates. Low-confidence matches wait for your OK.</p>
      </div>

      <div className="stats">
        {[["total", "Total", "blue"], ["matched", "Matched", "green"],
          ["needs_review", "Needs review", "violet"], ["unmatched", "Unmatched", "violet"],
          ["extraction_failed", "Could not read", "violet"]].map(
          ([k, lbl, tone]) => (
            <div className="stat" key={k}>
              <div className={`stat-icon ${tone}`}><Icon name="documents" size={20} /></div>
              <div><div className="num"><CountUp value={c[k] ?? 0} /></div><div className="lbl">{lbl}</div></div>
            </div>
          ))}
      </div>

      <div className="panel">
        <div className="conn-row">
          <div className="conn-left">
            {status.path_exists ? (
              <span className="badge active"><span className="dot green" /> Folder ready</span>
            ) : (
              <span className="badge coming">Folder not found on this host</span>
            )}
            <span className="muted"><code>{status.scan_path || "(no path set)"}</code></span>
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            {status.debug && (
              <button className="btn secondary" onClick={() => run("samples")} disabled={!!busy}>
                {busy === "samples" ? "Generating…" : "Generate sample data"}
              </button>
            )}
            <button className="btn secondary" onClick={() => run("extract")} disabled={!!busy}>
              {busy === "extract" ? "Extracting…" : "Extract amounts"}
            </button>
            <button className="btn" onClick={() => run("scan")} disabled={!!busy}>
              <Icon name="scan" size={16} />
              {busy === "scan" ? "Scanning…" : "Scan folder"}
            </button>
          </div>
        </div>
        {(busy === "scan" || busy === "extract") && <JobProgress job={scanJob} />}
        {scanResult && !scanResult.error && (
          <div className="scan-summary">
            {scanResult.updated != null ? (
              <>
                Extracted vendor/date/amount on <strong>{scanResult.updated}</strong> of{" "}
                {scanResult.scanned} documents
                {scanResult.skipped_missing_files
                  ? ` (${scanResult.skipped_missing_files} files missing on disk)` : ""}.
              </>
            ) : (
              <>
                Scanned <strong>{scanResult.scanned}</strong> PDFs —{" "}
                {Object.entries(scanResult.summary || {}).map(([k, v]) => `${v} ${k}`).join(", ")}.
              </>
            )}
          </div>
        )}
        {scanResult?.error && (
          <div className="scan-summary" style={{ background: "var(--rose-soft)", color: "var(--rose)", borderColor: "rgba(251,113,133,.3)" }}>
            {scanResult.error}
          </div>
        )}
      </div>

      {/* AI review */}
      <div className="panel">
        <div className="conn-row">
          <div className="conn-left">
            <h2 style={{ margin: 0 }}><Icon name="automation" size={17} /> AI review</h2>
            {ai?.configured ? (
              ai.enabled
                ? <span className="badge active"><span className="dot green" /> On · {ai.model}</span>
                : <span className="badge coming">Ready · {ai.model}</span>
            ) : (
              <span className="badge coming">No Gemini API key</span>
            )}
            {ai?.configured && (
              <span className="muted" style={{ fontSize: 12 }}>
                {ai.reviewed}/{ai.total} reviewed · {ai.pending} pending
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            {ai?.configured && (
              <button className="btn secondary" onClick={toggleAi}>
                {ai.enabled ? "Disable daily" : "Enable daily"}
              </button>
            )}
            <button className="btn secondary" onClick={getOverview} disabled={!ai?.configured || !!busy}>
              {busy === "overview" ? "…" : "Daily overview"}
            </button>
            <button className="btn" onClick={runAi} disabled={!ai?.configured || !!busy}>
              <Icon name="automation" size={16} />
              {busy === "ai" ? "Reviewing…" : "Review with AI"}
            </button>
          </div>
        </div>
        {!ai?.configured && (
          <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
            Get a <strong>free Gemini API key</strong> at{" "}
            <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer"
              style={{ color: "var(--green)" }}>aistudio.google.com/apikey</a>{" "}
            (sign in with Google → Create API key), paste it into{" "}
            <strong>Settings → Gemini API key</strong> (or set the <code>GEMINI_API_KEY</code> env
            var), and Gemini reads each PDF, writes a short overview, and files it into the right
            business &amp; category. The free tier is plenty for daily reviews.
          </p>
        )}
        {overview?.overview && (
          <div className="scan-summary" style={{ marginTop: 14 }}>{overview.overview}</div>
        )}
        {overview?.error && (
          <div className="scan-summary" style={{ marginTop: 14, background: "var(--rose-soft)", color: "var(--rose)" }}>{overview.error}</div>
        )}
        {busy === "ai" && <JobProgress job={aiJob} />}
        {aiResult && !aiResult.error && (
          <div className="scan-summary" style={{ marginTop: 14 }}>
            Reviewed <strong>{aiResult.reviewed}</strong> documents
            {aiResult.errors ? `, ${aiResult.errors} errors` : ""} with {aiResult.model}.
            {aiResult.stopped && <> {aiResult.stopped}</>}
          </div>
        )}
        {aiResult?.error && (
          <div className="scan-summary" style={{ marginTop: 14, background: "var(--rose-soft)", color: "var(--rose)" }}>{aiResult.error}</div>
        )}
      </div>

      <div className="panel">
        <div className="conn-row">
          <h2 style={{ margin: 0 }}><Icon name="documents" size={17} /> Document review</h2>
          <div style={{ display: "flex", gap: 10 }}>
            <button className={`btn ${view === "table" ? "" : "secondary"}`} onClick={() => setView("table")}>Table</button>
            <button className={`btn ${view === "queue" ? "" : "secondary"}`} onClick={() => setView("queue")}>Review queue</button>
          </div>
        </div>

        {view === "queue" ? (
          <div style={{ marginTop: 16 }}>
            <ReviewQueue businesses={businesses} buckets={status.buckets} onDone={() => { loadMeta(); fetchDocs(); }} />
          </div>
        ) : (
          <>
            <div className="filters" style={{ marginTop: 16 }}>
              <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
                <option value="">All statuses</option>
                {Object.entries(DOC_STATUS_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
              </select>
              <select value={filters.confidence} onChange={(e) => setFilters({ ...filters, confidence: e.target.value })}>
                <option value="">Any confidence</option>
                {["high", "medium", "low", "none"].map((k) => <option key={k} value={k}>{k}</option>)}
              </select>
              {approvableCount > 0 && (
                <button className="btn secondary" onClick={approveAllMediumPlus} disabled={!!busy}>
                  Approve all medium+ confidence ({approvableCount})
                </button>
              )}
              {selected.size > 0 && (
                <button className="btn" onClick={approveSelected} disabled={!!busy}>
                  Approve {selected.size} selected
                </button>
              )}
            </div>
            {docs.length === 0 ? (
              <EmptyState icon="documents" title="No documents yet" hint="Generate sample data or scan a folder to get started." />
            ) : (
              <div className="table-wrap">
                <table className="email-table">
                  <thead>
                    <tr><th></th><th>File</th><th>Status</th><th>Conf.</th><th>Business</th><th>Year</th><th>Folder</th><th>Amount</th><th></th></tr>
                  </thead>
                  <tbody>
                    {docs.map((d, i) => (
                      <DocRow
                        key={d.id} doc={d} index={i} businesses={businesses} buckets={status.buckets}
                        years={years} selected={selected.has(d.id)} onToggleSelect={toggleSelect}
                        onSaved={() => { loadMeta(); fetchDocs(); }}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
