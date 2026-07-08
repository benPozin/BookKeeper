import React, { useEffect, useState } from "react";
import { api } from "../api";
import { Icon } from "../components/icons";
import { EmptyState, JobProgress, pollJob } from "../components/ui";

const CATEGORY_LABELS = {
  consulting: "Consulting (SPAL)",
  rental: "Rental",
  real_estate: "Real Estate",
  home_office: "Home Office",
};
const TYPE_LABELS = {
  consulting: "Consulting",
  rental: "Rental",
  real_estate: "Real Estate",
  home_office: "Home Office",
};

function SetupChecklist({ status }) {
  return (
    <div className="needs" style={{ background: "var(--surface)", borderColor: "var(--border-strong)" }}>
      <h4>Connect your real Gmail (one-time)</h4>
      <ol style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8, fontSize: 13, color: "var(--text-dim)" }}>
        <li>Create a project at console.cloud.google.com.</li>
        <li>Enable the <strong>Gmail API</strong> for that project.</li>
        <li>Configure the OAuth consent screen (External, add your email as a test user).</li>
        <li>Create an OAuth client of type <strong>Desktop app</strong>; download the JSON.</li>
        <li>Save it as <code>{status.credentials_path}</code> on the host machine.</li>
        <li>Restart the app, return here, and click <strong>Connect</strong>.</li>
      </ol>
      <p className="muted" style={{ marginTop: 8, fontSize: 12 }}>
        Scope requested: read-only ({status.scopes?.join(", ")}). No credentials are
        needed to explore the app in mock mode.
      </p>
    </div>
  );
}

export function GmailPage() {
  const PAGE_SIZE = 50;
  const [status, setStatus] = useState(null);
  const [businesses, setBusinesses] = useState([]);
  const [emails, setEmails] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [filters, setFilters] = useState({ category: "", business_id: "", year: "" });
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [scanJob, setScanJob] = useState(null);
  const [showSetup, setShowSetup] = useState(false);
  const [attach, setAttach] = useState(null);
  const [attachBusy, setAttachBusy] = useState(false);
  const [attachResult, setAttachResult] = useState(null);
  const [attachJob, setAttachJob] = useState(null);

  const loadMeta = async () => {
    const [st, bz, at] = await Promise.all([
      api.gmailStatus(), api.gmailBusinesses(),
      api.gmailAttachmentsStatus().catch(() => null),
    ]);
    setStatus(st);
    setBusinesses(bz.businesses);
    setAttach(at);
  };

  const fetchAttachments = async () => {
    setAttachBusy(true);
    setAttachResult(null);
    setAttachJob(null);
    try {
      const { job_id } = await api.gmailAttachmentsAsync();
      const res = await pollJob(job_id, setAttachJob);
      setAttachResult(res);
      await loadMeta();
    } catch (e) {
      setAttachResult({ error: e.message });
    } finally {
      setAttachBusy(false);
      setAttachJob(null);
    }
  };

  const fetchEmails = React.useCallback(() => {
    return api
      .gmailEmails({ ...filters, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then((r) => {
        setEmails(r.emails);
        setTotal(r.total);
      });
  }, [filters, page]);

  useEffect(() => {
    loadMeta().catch(() => {});
  }, []);

  useEffect(() => {
    fetchEmails().catch(() => {});
  }, [fetchEmails]);

  // Changing a filter resets to the first page.
  const updateFilter = (key, value) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(0);
  };

  const scan = async (full = false) => {
    setScanning(true);
    setScanResult(null);
    setScanJob(null);
    try {
      const { job_id } = await api.gmailScanAsync(full);
      const res = await pollJob(job_id, setScanJob);
      setScanResult(res);
      await loadMeta();
      await fetchEmails();
    } catch (e) {
      setScanResult({ error: e.message });
    } finally {
      setScanning(false);
      setScanJob(null);
    }
  };

  if (!status) return <p className="muted">Loading…</p>;

  const years = [...new Set(businesses.flatMap((b) => b.years))].sort();
  const grouped = businesses.reduce((acc, b) => {
    (acc[b.type] = acc[b.type] || []).push(b);
    return acc;
  }, {});

  return (
    <>
      <div className="page-head">
        <h1>
          <Icon name="gmail" size={26} />
          Gmail Scan
          <span className="badge phase">Phase 1</span>
        </h1>
        <p>Scan business email, discover businesses &amp; years, keep a history.</p>
      </div>

      {/* Connection status */}
      <div className="panel">
        <div className="conn-row">
          <div className="conn-left">
            {status.mode === "mock" ? (
              status.debug ? (
                <>
                  <span className="badge coming">Mock mode (debug)</span>
                  <span className="muted">
                    Using sample data. Add Google OAuth credentials to scan your real
                    mailbox — the pipeline below works identically.
                  </span>
                </>
              ) : (
                <>
                  <span className="badge coming">Not connected</span>
                  <span className="muted">
                    Add Google OAuth credentials to scan your real mailbox (see the
                    setup checklist below).
                  </span>
                </>
              )
            ) : status.connected ? (
              <>
                <span className="badge active">
                  <span className="dot green" /> Connected
                </span>
                <span className="muted">Real Gmail account linked (read-only).</span>
              </>
            ) : (
              <>
                <span className="badge coming">Credentials found — consent needed</span>
                <span className="muted">
                  Click Connect to complete Google sign-in on this machine.
                </span>
              </>
            )}
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn secondary" onClick={() => scan(true)} disabled={scanning}
              title="Re-walk every label (slower). 'Scan now' only asks Gmail what changed.">
              Full rescan
            </button>
            <button className="btn" onClick={() => scan(false)} disabled={scanning}>
              <Icon name="automation" size={16} />
              {scanning ? "Scanning…" : "Scan now"}
            </button>
          </div>
        </div>

        {scanning && <JobProgress job={scanJob} />}
        {scanResult && !scanResult.error && (
          <div className="scan-summary">
            Scanned <strong>{scanResult.scanned}</strong> emails (
            {scanResult.incremental ? "changes since last scan" : `mode: ${scanResult.mode}`}
            ) — <strong>{scanResult.new_emails}</strong> new,{" "}
            {scanResult.existing_emails} already on file. Total:{" "}
            {scanResult.total_emails}.
          </div>
        )}
        {scanResult?.error && (
          <div className="scan-summary" style={{ background: "var(--rose-soft)", color: "var(--rose)", borderColor: "rgba(251,113,133,.3)" }}>
            {scanResult.error}
          </div>
        )}

        <button className="back-link" onClick={() => setShowSetup((s) => !s)}>
          <Icon name={showSetup ? "chevronLeft" : "chevronRight"} size={15} />
          {showSetup ? "Hide" : "Show"} Gmail connection setup
        </button>
        {showSetup && <SetupChecklist status={status} />}
      </div>

      {/* Email attachments → Documents */}
      <div className="panel">
        <div className="conn-row">
          <div className="conn-left">
            <h2 style={{ margin: 0 }}><Icon name="paperclip" size={17} /> Email attachments</h2>
            {attach?.connected ? (
              attach.pending_emails > 0 ? (
                <span className="badge coming">{attach.pending_emails} emails to check</span>
              ) : (
                <span className="badge active"><span className="dot green" /> All fetched</span>
              )
            ) : (
              <span className="badge coming">Needs a connected Gmail</span>
            )}
            <span className="muted" style={{ fontSize: 12.5 }}>
              PDFs and photos attached to your matched business emails become
              Documents automatically — business, year, and income/expense come
              from the email's label.
            </span>
          </div>
          <button className="btn" onClick={fetchAttachments}
            disabled={!attach?.connected || attachBusy || scanning}>
            <Icon name="paperclip" size={16} />
            {attachBusy ? "Fetching…" : "Fetch attachments"}
          </button>
        </div>
        {attachBusy && <JobProgress job={attachJob} />}
        {attachResult && !attachResult.error && (
          <div className="scan-summary">
            Checked <strong>{attachResult.emails_processed}</strong> emails —{" "}
            <strong>{attachResult.saved}</strong> new documents saved,{" "}
            {attachResult.duplicates} duplicates skipped
            {attachResult.errors ? `, ${attachResult.errors} errors` : ""}.
          </div>
        )}
        {attachResult?.error && (
          <div className="scan-summary" style={{ background: "var(--rose-soft)", color: "var(--rose)", borderColor: "rgba(251,113,133,.3)" }}>
            {attachResult.error}
          </div>
        )}
      </div>

      {/* Discovered businesses */}
      <div className="panel">
        <h2>
          <Icon name="briefcase" size={17} />
          Discovered businesses &amp; years
        </h2>
        {businesses.length === 0 ? (
          <EmptyState icon="briefcase" title="Nothing yet" hint="Run a scan to discover your businesses and years." />
        ) : (
          Object.entries(grouped).map(([type, list]) => (
            <div key={type} style={{ marginBottom: 16 }}>
              <div className="group-label">{TYPE_LABELS[type] || type}</div>
              <div className="biz-grid">
                {list.map((b) => (
                  <div key={b.id} className="biz-card">
                    <div className="biz-name">{b.name}</div>
                    <div className="biz-meta">
                      {b.email_count} emails · years {b.years.join(", ") || "—"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Email history */}
      <div className="panel">
        <h2>
          <Icon name="gmail" size={17} />
          Email history
        </h2>
        <div className="filters">
          <select
            value={filters.category}
            onChange={(e) => updateFilter("category", e.target.value)}
          >
            <option value="">All categories</option>
            {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <select
            value={filters.business_id}
            onChange={(e) => updateFilter("business_id", e.target.value)}
          >
            <option value="">All businesses</option>
            {businesses.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
          <select
            value={filters.year}
            onChange={(e) => updateFilter("year", e.target.value)}
          >
            <option value="">All years</option>
            {years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>

        {emails.length === 0 ? (
          <EmptyState icon="gmail" title="No emails match" hint="Try a different filter, or scan again." />
        ) : (
          <div className="table-wrap">
            <table className="email-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Category</th>
                  <th>Kind</th>
                  <th>Business</th>
                  <th>Year</th>
                  <th>Subject</th>
                  <th>From</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {emails.map((e, i) => (
                  <tr key={e.id} style={{ "--i": Math.min(i, 20) }}>
                    <td className="nowrap">{e.date}</td>
                    <td>
                      <span className={`pill cat-pill cat-${e.category}`}>
                        {CATEGORY_LABELS[e.category] || e.category}
                      </span>
                    </td>
                    <td>
                      {e.kind && e.kind !== "other" && (
                        <span className={`pill kind-${e.kind}`}>{e.kind}</span>
                      )}
                    </td>
                    <td>{e.business}</td>
                    <td>{e.year}</td>
                    <td className="subj" title={e.snippet}>{e.subject}</td>
                    <td className="from">{e.sender}</td>
                    <td>{e.has_attachments && <Icon name="paperclip" size={15} />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {total > 0 && (
          <div className="pager">
            <span className="muted">
              Showing {page * PAGE_SIZE + 1}–
              {Math.min((page + 1) * PAGE_SIZE, total)} of {total}
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                className="btn secondary"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                <Icon name="chevronLeft" size={16} /> Prev
              </button>
              <button
                className="btn secondary"
                disabled={(page + 1) * PAGE_SIZE >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next <Icon name="chevronRight" size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
