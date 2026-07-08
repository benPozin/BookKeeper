import { useEffect, useState } from "react";
import { api, setAuthToken } from "./api";
import { Icon } from "./components/icons";
import { ShimoSetup } from "./components/ShimoSetup";
import { Dashboard } from "./pages/Dashboard";
import { Settings } from "./pages/Settings";
import { Organizer } from "./pages/Organizer";
import { GmailPage } from "./pages/Gmail";
import { DocumentsPage } from "./pages/Documents";
import { NewScanPage } from "./pages/NewScan";
import { TemplatesPage } from "./pages/Templates";
import { AutomationPage } from "./pages/Automation";
import { ExportPage } from "./pages/Export";

const NAV = [
  { id: "dashboard", name: "Dashboard" },
  { id: "gmail", name: "Gmail" },
  { id: "documents", name: "Documents" },
  { id: "scan", name: "New Scan" },
  { id: "templates", name: "Templates" },
  { id: "organizer", name: "Organizer" },
  { id: "automation", name: "Automation" },
  { id: "export", name: "Export" },
];

const TODAY_LABEL = new Date()
  .toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" })
  .toUpperCase();

function PinGate({ onUnlocked }) {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!pin || busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await api.authLogin(pin);
      setAuthToken(res.token);
      onUnlocked();
    } catch {
      setError("Wrong PIN — try again.");
      setPin("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="main" style={{ display: "grid", placeItems: "center", minHeight: "60vh" }}>
      <form onSubmit={submit} className="panel" style={{ maxWidth: 340, width: "100%", textAlign: "center" }}>
        <div style={{ marginBottom: 10 }}><Icon name="settings" size={26} /></div>
        <h2 style={{ marginTop: 0 }}>Enter PIN</h2>
        <p className="muted" style={{ fontSize: 13 }}>
          This BookKeeper is PIN-protected (Settings → App PIN).
        </p>
        <div className="field">
          <input
            type="password"
            inputMode="numeric"
            autoFocus
            autoComplete="off"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            placeholder="PIN"
            style={{ textAlign: "center", letterSpacing: 4 }}
          />
        </div>
        {error && <p style={{ color: "var(--rose)", fontSize: 13 }}>{error}</p>}
        <button className="btn" type="submit" disabled={busy || !pin} style={{ width: "100%" }}>
          {busy ? "Checking…" : "Unlock"}
        </button>
      </form>
    </main>
  );
}

export default function App() {
  const [view, setView] = useState("dashboard");
  const [locked, setLocked] = useState(false);
  const [showSetup, setShowSetup] = useState(false);
  const [gmail, setGmail] = useState(null);
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("bk-theme") || "dark";
    } catch {
      return "dark";
    }
  });

  // The PIN lock: any 401 from the API raises this event (listener must be
  // registered before the first data fetch below).
  useEffect(() => {
    const onAuth = () => setLocked(true);
    window.addEventListener("bk-auth-required", onAuth);
    return () => window.removeEventListener("bk-auth-required", onAuth);
  }, []);

  useEffect(() => {
    if (!locked) api.gmailStatus().then(setGmail).catch(() => {});
  }, [view, locked]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("bk-theme", theme);
    } catch {
      /* private browsing — theme just won't persist */
    }
  }, [theme]);

  const connected = gmail?.mode === "real" && gmail?.connected;

  return (
    <>
      <header className="masthead-row">
        <div className="brand" onClick={() => setView("dashboard")} style={{ cursor: "pointer" }}>
          <div className="brand-text">
            <div className="brand-name">BookKeeper</div>
            <small>Tax document organizer</small>
          </div>
        </div>
        <div className="topbar-right">
          <span className="masthead-date">{TODAY_LABEL}</span>
          <span className={`status-chip ${connected ? "" : "amber"}`}>
            <span className={`dot ${connected ? "green" : "amber"}`} />
            {connected ? "Connected" : "Not linked"}
          </span>
          <button
            className={`icon-btn ${showSetup ? "active" : ""}`}
            onClick={() => setShowSetup(true)}
            title="Set up on the Windows PC (shimo) — step-by-step guide"
          >
            <Icon name="help" size={18} />
          </button>
          <button
            className="icon-btn"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            <Icon name={theme === "dark" ? "sun" : "moon"} size={17} />
          </button>
          <button
            className={`icon-btn ${view === "settings" ? "active" : ""}`}
            onClick={() => setView("settings")}
            title="Settings"
          >
            <Icon name="settings" size={18} />
          </button>
        </div>
      </header>
      <nav className="topnav">
        {NAV.map((n) => (
          <button
            key={n.id}
            className={`topnav-item ${view === n.id ? "active" : ""}`}
            onClick={() => setView(n.id)}
          >
            <Icon name={n.id} size={17} />
            <span>{n.name}</span>
          </button>
        ))}
      </nav>
      {locked ? (
        <PinGate onUnlocked={() => window.location.reload()} />
      ) : (
      <main className="main">
        {view === "dashboard" && <Dashboard onOpen={setView} />}
        {view === "settings" && <Settings />}
        {view === "organizer" && <Organizer />}
        {view === "gmail" && <GmailPage />}
        {view === "documents" && <DocumentsPage />}
        {view === "scan" && <NewScanPage />}
        {view === "templates" && <TemplatesPage />}
        {view === "automation" && <AutomationPage />}
        {view === "export" && <ExportPage />}
      </main>
      )}
      {showSetup && !locked && <ShimoSetup onClose={() => setShowSetup(false)} />}
    </>
  );
}
