import { useEffect, useState } from "react";
import { api } from "../api";
import { Icon } from "../components/icons";

export function Settings() {
  const [cfg, setCfg] = useState(null);
  const [values, setValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [warnings, setWarnings] = useState({});

  useEffect(() => {
    api.getSettings().then((c) => {
      setCfg(c);
      setValues(c.values);
    });
  }, []);

  if (!cfg) return <p className="muted">Loading settings…</p>;

  const save = async () => {
    setSaving(true);
    const updated = await api.saveSettings(values);
    setCfg(updated);
    setValues(updated.values);
    setWarnings(updated.warnings || {});
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2200);
  };

  return (
    <>
      <div className="page-head">
        <h1>
          <Icon name="settings" size={26} />
          Settings
        </h1>
        <p>Editable now — persisted to the local database.</p>
      </div>
      <div className="panel" style={{ maxWidth: 660 }}>
        {cfg.fields.map((f) => {
          const status = cfg.path_status?.[f.key];
          const isPath = f.key in (cfg.path_status || {});
          return (
            <div className="field" key={f.key}>
              <label>{f.label}</label>
              {f.type === "select" ? (
                <select
                  value={values[f.key] ?? ""}
                  onChange={(e) =>
                    setValues({ ...values, [f.key]: e.target.value })
                  }
                >
                  {(f.options || []).map((opt) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              ) : (
                <input
                  type={f.type === "password" ? "password" : "text"}
                  autoComplete={f.type === "password" ? "new-password" : "off"}
                  value={values[f.key] ?? ""}
                  onChange={(e) =>
                    setValues({ ...values, [f.key]: e.target.value })
                  }
                />
              )}
              {f.help && <div className="help">{f.help}</div>}
              {isPath && (
                <div className={status ? "path-ok" : "path-missing"}>
                  <Icon name={status ? "check" : "alert"} size={14} />
                  {status
                    ? "Folder exists on this host"
                    : "Folder not found on this host (expected — it lives on the Windows PC)"}
                </div>
              )}
              {warnings[f.key] && !isPath && (
                <div className="path-missing">
                  <Icon name="alert" size={14} /> {warnings[f.key]}
                </div>
              )}
            </div>
          );
        })}
        <button className="btn" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save settings"}
        </button>
      </div>
      {saved && (
        <div className="toast">
          <Icon name="check" size={16} /> Settings saved
        </div>
      )}
    </>
  );
}
