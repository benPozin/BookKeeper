import React, { useEffect, useState } from "react";
import QRCode from "qrcode";
import { api } from "../api";
import { Icon } from "../components/icons";

function PhoneQr() {
  const [lan, setLan] = useState(null);
  const [qr, setQr] = useState("");

  useEffect(() => {
    api.scanLanUrl().then(setLan).catch(() => {});
  }, []);

  useEffect(() => {
    if (!lan?.url) return;
    QRCode.toDataURL(lan.url, { width: 168, margin: 1, color: { dark: "#04130c", light: "#f4fbf7" } })
      .then(setQr)
      .catch(() => {});
  }, [lan]);

  if (!lan) return null;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
      {qr && (
        <img src={qr} alt={`QR code for ${lan.url}`} width={84} height={84}
          style={{ borderRadius: "var(--radius-sm)", border: "1px solid var(--border-strong)" }} />
      )}
      <div>
        <div className="dz-title" style={{ fontSize: 14 }}>Scan with your phone</div>
        <div className="muted" style={{ fontSize: 12.5, marginTop: 2 }}>
          Same WiFi network, then open <code>{lan.url}</code>
        </div>
      </div>
    </div>
  );
}

export function NewScanPage() {
  const [status, setStatus] = useState(null);
  const [uploads, setUploads] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileRef = React.useRef(null);

  const load = () => api.scanStatus().then(setStatus).catch(() => {});
  useEffect(() => { load(); }, []);

  const onFiles = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setUploading(true);
    for (const f of files) {
      try {
        const res = await api.scanUpload(f);
        setUploads((u) => [{ name: f.name, ...res }, ...u].slice(0, 20));
      } catch {
        setUploads((u) => [{ name: f.name, error: "upload failed" }, ...u]);
      }
    }
    setUploading(false);
    load();
    if (fileRef.current) fileRef.current.value = "";
  };

  const toggleWatch = async () => {
    if (status?.watch?.running) await api.scanWatchStop();
    else await api.scanWatchStart();
    load();
  };

  if (!status) return <p className="muted">Loading…</p>;

  return (
    <>
      <div className="page-head">
        <h1><Icon name="scan" size={26} />New Scan<span className="badge phase">Phase 3</span></h1>
        <p>Add documents two ways: snap or upload from your phone over WiFi, or let
          BookKeeper watch the ScanSnap ix1600 output folder and auto-ingest.</p>
      </div>

      <div className="panel">
        <h2><Icon name="scan" size={17} /> Upload from phone or computer</h2>
        <label
          className={`dropzone ${dragging ? "dragging" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); onFiles(e.dataTransfer.files); }}
        >
          <input
            ref={fileRef} type="file" accept="image/*,application/pdf" multiple
            capture="environment" style={{ display: "none" }}
            onChange={(e) => onFiles(e.target.files)}
          />
          <Icon name="scan" size={30} />
          <div className="dz-title">{uploading ? "Uploading…" : "Tap to take a photo or choose files"}</div>
          <div className="muted" style={{ fontSize: 12 }}>Images become PDFs automatically · drag &amp; drop works too</div>
        </label>
        {uploads.length > 0 && (
          <div style={{ marginTop: 14 }}>
            {uploads.map((u, i) => (
              <div key={i} className="upload-row">
                <Icon name="documents" size={15} />
                <span className="subj">{u.saved_as || u.name}</span>
                {u.result ? (
                  <span className={`pill st-${u.result.status === "matched" ? "matched" : u.result.status === "duplicate" ? "filed" : "review"}`}>
                    {u.result.status}{u.result.confidence ? ` · ${u.result.confidence}` : ""}
                  </span>
                ) : <span className="pill st-unmatched">error</span>}
              </div>
            ))}
          </div>
        )}
        <PhoneQr />
      </div>

      <div className="panel">
        <div className="conn-row">
          <div className="conn-left">
            <h2 style={{ margin: 0 }}><Icon name="automation" size={17} /> ScanSnap auto-watch</h2>
            {status.watch?.running
              ? <span className="badge active"><span className="dot green" /> Watching</span>
              : <span className="badge coming">Stopped</span>}
          </div>
          <button className="btn" onClick={toggleWatch} disabled={!status.path_exists}>
            {status.watch?.running ? "Stop watching" : "Start watching"}
          </button>
        </div>
        <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
          Watching <code>{status.scan_path || "(no path)"}</code>
          {status.watch?.running ? ` — ${status.watch.ingested_this_session} ingested this session.` : "."}
        </p>
        <div className="needs">
          <h4 style={{ color: "var(--gold)" }}>ScanSnap ix1600 setup</h4>
          <ol style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8, fontSize: 13, color: "var(--text-dim)" }}>
            <li>In ScanSnap Home, set the scan profile to save PDFs into the folder above (the ScanSnap path in Settings).</li>
            <li>Click <strong>Start watching</strong> — new scans are ingested and matched automatically.</li>
            <li>Review any low-confidence matches on the <strong>Documents</strong> page.</li>
          </ol>
        </div>
      </div>

      {status.recent?.length > 0 && (
        <div className="panel">
          <h2><Icon name="documents" size={17} /> Recently ingested</h2>
          <div className="table-wrap">
            <table className="email-table">
              <thead><tr><th>File</th><th>Source</th><th>Status</th></tr></thead>
              <tbody>
                {status.recent.map((r, i) => (
                  <tr key={i}>
                    <td className="subj">{r.filename}</td>
                    <td><span className="pill cat-consulting">{r.source}</span></td>
                    <td><span className={`pill st-${r.status === "matched" ? "matched" : r.status === "needs_review" ? "review" : "unmatched"}`}>{r.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
