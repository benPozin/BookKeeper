import React, { useEffect, useState } from "react";
import { api } from "../api";
import { Icon } from "../components/icons";
import { CountUp } from "../components/ui";

const STAT_META = [
  { key: "businesses", label: "Businesses", icon: "briefcase", tone: "blue",
    sub: "Consulting, rental & real estate" },
  { key: "emails", label: "Emails scanned", icon: "gmail", tone: "green",
    sub: "From your Business labels" },
  { key: "documents", label: "Documents filed", icon: "documents", tone: "violet",
    sub: "Matched & organized" },
];

// check: which year-end-checklist item drives this step's Done stamp.
const WORKFLOW = [
  { id: "gmail", label: "Gmail Scan", check: "gmail" },
  { id: "documents", label: "PDF Matching", check: "documents" },
  { id: "templates", label: "Template Fill", check: null },
  { id: "organizer", label: "Folder Organizer", check: "organizer" },
  { id: "export", label: "Export", check: "export" },
];

const money = (v, compact = false) => {
  if (v == null) return "—";
  if (compact) {
    if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
    if (v >= 1000) return `$${(v / 1000).toFixed(v >= 100000 ? 0 : 1)}K`;
    return `$${Math.round(v)}`;
  }
  return `$${Math.round(v).toLocaleString()}`;
};

function WorkflowRow({ onOpen, checkmap }) {
  return (
    <div className="workflow-row">
      {WORKFLOW.map((w, i) => {
        const st = w.check ? checkmap?.[w.check] : null;
        return (
          <React.Fragment key={w.id}>
            <button className={`wf-step ${st?.done ? "done" : ""}`} onClick={() => onOpen(w.id)}>
              <span className="wf-icon">
                {st?.done ? <Icon name="check" size={13} /> : i + 1}
              </span>
              <span style={{ textAlign: "left" }}>
                <span className="wf-label">{w.label}</span>
                {st && <span className="wf-detail">{st.detail}</span>}
              </span>
            </button>
            {i < WORKFLOW.length - 1 && <span className="wf-arrow" />}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function smoothPath(pts) {
  if (pts.length < 2) return "";
  let d = `M ${pts[0][0]} ${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
    const c1x = p1[0] + (p2[0] - p0[0]) / 6, c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6, c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C ${c1x.toFixed(1)} ${c1y.toFixed(1)} ${c2x.toFixed(1)} ${c2y.toFixed(1)} ${p2[0]} ${p2[1]}`;
  }
  return d;
}

// data: [[monthLabel, amountSum, docCount], ...]
function MoneyChart({ data }) {
  const W = 760, H = 210, padX = 26, padTop = 26, padBot = 30;
  if (data.length === 0 || data.every((d) => !d[1])) {
    return <p className="muted" style={{ fontSize: 13 }}>No amounts captured yet — scan some documents first.</p>;
  }
  const n = data.length;
  const max = Math.max(1, ...data.map((d) => d[1])) * 1.18;
  const plotH = H - padTop - padBot;
  const baseline = H - padBot;
  const innerW = W - padX * 2;
  const pts = data.map(([, v], i) => [
    padX + innerW * (n > 1 ? i / (n - 1) : 0.5),
    baseline - plotH * (v / max),
  ]);
  const line = smoothPath(pts);
  const area = `${line} L ${pts[n - 1][0]} ${baseline} L ${pts[0][0]} ${baseline} Z`;
  return (
    <svg className="bars money-chart" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label="Dollars captured by month">
      {[0, 0.5, 1].map((g, i) => {
        const y = padTop + plotH * g;
        return <line key={i} className="grid" x1={padX} x2={W - padX} y1={y} y2={y} />;
      })}
      <path className="lc-area" d={area} />
      <path className="lc-line" d={line} pathLength="1" />
      <line className="baseline" x1={padX} x2={W - padX} y1={baseline} y2={baseline} />
      {data.map(([m, v], i) => (
        <g key={`${m}-${i}`}>
          <circle className="lc-dot" cx={pts[i][0]} cy={pts[i][1]} r="3.4" />
          {v > 0 && <text x={pts[i][0]} y={pts[i][1] - 9} className="bv">{money(v, true)}</text>}
          <text x={pts[i][0]} y={H - padBot + 18} className="bx">{m}</text>
        </g>
      ))}
    </svg>
  );
}

function ActivityRow({ a }) {
  const rich = a.vendor || a.amount != null;
  return (
    <div className="act-row">
      <span className="act-main">
        <span className="act-text">
          {rich ? (<>{a.verb} <strong>{a.vendor || a.filename}</strong></>) : a.text}
          {a.amount != null && <span className="act-amount">{money(a.amount)}</span>}
        </span>
        {rich && (
          <span className="act-sub">
            {a.business ? `→ ${a.business}` : ""}
            {a.business && a.vendor ? " · " : ""}
            {a.vendor ? a.filename : ""}
          </span>
        )}
      </span>
      <span className="act-time">{a.time}</span>
    </div>
  );
}

export function Dashboard({ onOpen }) {
  const [data, setData] = useState(null);
  const [years, setYears] = useState([]);
  const [year, setYear] = useState("");
  const [checklist, setChecklist] = useState(null);

  useEffect(() => {
    api.dashboard().then(setData).catch(() => setData({ error: true }));
    api.organizerYears().then((d) => { setYears(d.years); setYear(d.years?.[0] || ""); }).catch(() => {});
  }, []);
  useEffect(() => {
    if (year) api.dashboardChecklist(year).then(setChecklist).catch(() => {});
  }, [year]);

  const amounts = data?.amounts;
  const checkmap = checklist
    ? Object.fromEntries(checklist.items.map((it) => [it.key, it]))
    : null;

  return (
    <div className="dashboard">
      <div className="dash-hero">
        <div>
          <h1>
            Hi <span style={{ color: "var(--green)" }}>Shimon</span>
            {amounts?.latest_year ? `, here are your ${amounts.latest_year} books` : ""}
          </h1>
        </div>
        <div className="hero-figures">
          <div className="hero-fig">
            <span className="hf-num"><CountUp value={data?.counts?.documents ?? "—"} /></span>
            <span className="hf-lbl">Documents</span>
          </div>
          <div className="hero-fig gold">
            <span className="hf-num">{money(amounts?.latest_year_total)}</span>
            <span className="hf-lbl">Captured for {amounts?.latest_year || "—"}</span>
          </div>
          <div className="hero-fig">
            <span className="hf-num"><CountUp value={data?.needs_attention ?? "—"} /></span>
            <span className="hf-lbl">Waiting on you</span>
          </div>
        </div>
      </div>

      {data?.needs_attention > 0 && (
        <div
          className="panel"
          style={{ borderLeft: "3px solid var(--gold)", cursor: "pointer", marginBottom: 20 }}
          onClick={() => onOpen("documents")}
        >
          <div className="conn-row">
            <div className="conn-left">
              <span className="stamp tilt" style={{ color: "var(--gold-deep)" }}>Needs review</span>
              <span>
                <strong>{data.needs_attention}</strong> document{data.needs_attention === 1 ? "" : "s"} waiting on your review
              </span>
            </div>
            <span className="back-link">Open Documents <Icon name="chevronRight" size={15} /></span>
          </div>
        </div>
      )}
      {data && !data.error && data.needs_attention === 0 && (
        <div className="panel" style={{ borderLeft: "3px solid var(--green)", marginBottom: 20 }}>
          <div className="conn-left">
            <span className="stamp" style={{ color: "var(--green)" }}>All caught up</span>
            <span>Every document is reviewed and filed. Nothing needs you today.</span>
          </div>
        </div>
      )}

      <div className="stats">
        {STAT_META.map((s) => (
          <div className="stat" key={s.key} onClick={() => onOpen(s.key === "businesses" ? "gmail" : s.key === "emails" ? "gmail" : "documents")} style={{ cursor: "pointer" }}>
            <div className={`stat-icon ${s.tone}`}>
              <Icon name={s.icon} size={20} />
            </div>
            <div className="stat-body">
              <div className="num"><CountUp value={data?.counts?.[s.key] ?? "—"} /></div>
              <div className="lbl">{s.label}</div>
              <div className="sub">{s.sub}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="panel workflow-panel">
        <div className="conn-row" style={{ marginBottom: 14 }}>
          <div className="section-head" style={{ margin: 0 }}>
            <span>Your workflow</span>
            <span className="section-hint">Where {year || "the year"} stands, inbox → accountant</span>
          </div>
          {years.length > 0 && (
            <select value={year} onChange={(e) => setYear(e.target.value)} style={{ width: "auto", minWidth: 96 }}>
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          )}
        </div>
        <WorkflowRow onOpen={onOpen} checkmap={checkmap} />
      </div>

      <div className="dash-cols">
        <div className="panel chart-card">
          <div className="section-head">
            <span>Dollars captured</span>
            <span className="section-hint">Extracted from your documents, by document date — last 12 months</span>
          </div>
          <MoneyChart data={data?.chart || []} />
        </div>
        <div className="panel activity-card">
          <div className="section-head"><span>Recent activity</span></div>
          <div className="activity-list">
            {(data?.activity || []).length === 0 && (
              <div className="muted" style={{ fontSize: 13, padding: "8px 0" }}>Nothing yet.</div>
            )}
            {(data?.activity || []).map((a, i) => <ActivityRow a={a} key={i} />)}
          </div>
        </div>
      </div>
    </div>
  );
}
