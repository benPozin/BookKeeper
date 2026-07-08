import { useEffect, useState } from "react";
import { api } from "../api";
import { Icon } from "./icons";

const WIN_SCANSNAP =
  "C:\\Users\\shimo\\AppData\\Roaming\\PFU\\ScanSnap Home\\ScanSnap Home";

// Live checklist for moving BookKeeper to the Windows PC. Each auto step is
// checked against THIS host, so opened on shimo it shows what's actually left.
export function ShimoSetup({ onClose }) {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    Promise.all([api.diagnostics(), api.authStatus(), api.automationStatus()])
      .then(([diag, auth, auto]) => setData({ diag, auth, auto }))
      .catch(() => setFailed(true));
  }, []);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const diag = data?.diag;
  const onWindows = diag?.platform?.startsWith("win");
  const scanPath = diag?.paths?.scansnap_path;
  const scanPathReal = !!scanPath?.exists && /scansnap/i.test(scanPath?.value || "");

  // done: true/false = live check on this machine; null = check by hand.
  const steps = [
    {
      title: "Get the code from GitHub",
      done: null,
      body: (
        <>
          Install Git for Windows, then{" "}
          <code>git clone https://github.com/benPozin/BookKeeper.git</code>{" "}
          (private repo — sign in as benPozin). Later updates are just{" "}
          <code>git pull</code>.
        </>
      ),
    },
    {
      title: "Copy the data\\ folder from the Mac",
      done: null,
      body: (
        <>
          Drop the Mac's <code>data\</code> folder into the cloned BookKeeper
          folder. It carries your email history, matched documents, downloaded
          attachments, and the Gmail login — deliberately NOT on GitHub.
          Nothing needs to be re-scanned or re-connected.
        </>
      ),
    },
    {
      title: "Install Python 3.11+ and Node 20+",
      done: null,
      body: <>One-time installs from python.org and nodejs.org (tick "Add to PATH").</>,
    },
    {
      title: "Launch BookKeeper on shimo",
      done: data ? !!onWindows : undefined,
      body: (
        <>
          Double-click <code>scripts\start_bookkeeper.bat</code> — the first run
          builds everything and opens the app. This step shows Done once you are
          reading this guide on the Windows PC.
        </>
      ),
    },
    {
      title: "Install Tesseract OCR (reads photo-only scans)",
      done: data ? !!diag?.ocr_available : undefined,
      body: (
        <>
          In PowerShell: <code>winget install UB-Mannheim.TesseractOCR</code>.
          BookKeeper finds it automatically in{" "}
          <code>C:\Program Files\Tesseract-OCR</code>.
        </>
      ),
    },
    {
      title: "Point the ScanSnap folder at the real path",
      done: data ? scanPathReal : undefined,
      body: (
        <>
          In <strong>Settings → ScanSnap folder path</strong>, set{" "}
          <code>{WIN_SCANSNAP}</code>. Right now it is{" "}
          <code>{scanPath?.value || "(not set)"}</code>.
        </>
      ),
    },
    {
      title: "Gmail connected",
      done: data ? !!diag?.gmail?.connected : undefined,
      body: (
        <>
          If you copied <code>data\</code>, this is already Done. Otherwise open{" "}
          <strong>Gmail → Connect</strong> and sign in once.
        </>
      ),
    },
    {
      title: "Set an App PIN (recommended)",
      done: data ? !!data?.auth?.pin_required : undefined,
      body: (
        <>
          <strong>Settings → App PIN</strong>. The app is reachable by any device
          on your WiFi so the phone can upload — a PIN keeps everyone else out.
        </>
      ),
    },
    {
      title: "Turn on Daily Automation",
      done: data ? !!data?.auto?.enabled : undefined,
      body: (
        <>
          On the <strong>Automation</strong> page pick a time and enable it —
          daily Gmail scan, attachment fetch, folder ingest, and backup.
        </>
      ),
    },
    {
      title: "Start at login (and restart after crashes)",
      done: null,
      body: (
        <>
          In an <em>administrator</em> PowerShell:{" "}
          <code>powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1</code>
        </>
      ),
    },
    {
      title: "Prove it with real data",
      done: null,
      body: (
        <>
          1) <strong>Gmail → Scan now</strong>, then <strong>Fetch attachments</strong>.{" "}
          2) Scan one paper receipt on the ScanSnap and watch it appear under{" "}
          <strong>Documents</strong>. 3) On your phone (same WiFi), use the{" "}
          <strong>New Scan</strong> QR code to upload a photo.
        </>
      ),
    },
    {
      title: "Optional: Gemini key for AI review",
      done: data ? !!diag?.ai?.configured : undefined,
      body: (
        <>
          Free key from <code>aistudio.google.com/apikey</code> →{" "}
          <strong>Settings → Gemini API key</strong>. Everything works without it;
          AI review just reads tricky documents better.
        </>
      ),
    },
  ];

  const pill = (done) => {
    if (done === null) return <span className="badge">Check by hand</span>;
    if (done === undefined) return <span className="badge">…</span>;
    return done ? (
      <span className="badge active"><span className="dot green" /> Done</span>
    ) : (
      <span className="badge coming">To do</span>
    );
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog"
        aria-label="Windows PC setup guide">
        <div className="modal-head">
          <h2><Icon name="monitor" size={19} /> Moving to the Windows PC (shimo)</h2>
          <button className="icon-btn" onClick={onClose} title="Close" aria-label="Close">
            ×
          </button>
        </div>
        <p className="muted" style={{ margin: "2px 0 4px", fontSize: 13 }}>
          The Done stamps are live checks on <strong>this</strong> machine — open
          this same guide on shimo and it will show exactly what's left there.
          {failed && " (Couldn't reach the API for live checks — statuses hidden.)"}
        </p>
        <ol className="setup-steps">
          {steps.map((s, i) => (
            <li className="setup-step" key={s.title}>
              <span className="num">{i + 1}</span>
              <div style={{ minWidth: 0 }}>
                <h4>{s.title}</h4>
                <p>{s.body}</p>
              </div>
              <span className="step-pill">{pill(s.done)}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
