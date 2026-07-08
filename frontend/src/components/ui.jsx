import { useEffect, useState } from "react";
import { api } from "../api";
import { Icon } from "./icons";

// Polls GET /api/jobs/{id} until the job finishes, calling onUpdate with each
// poll so the caller can render live progress. Resolves with the job's result
// or throws if the job failed.
export async function pollJob(jobId, onUpdate, intervalMs = 600) {
  for (;;) {
    const job = await api.jobStatus(jobId);
    onUpdate?.(job);
    if (job.state === "done") return job.result;
    if (job.state === "error") throw new Error(job.error || "Job failed");
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

export function JobProgress({ job }) {
  if (!job) return null;
  const pct = job.total > 0 ? Math.round((job.done / job.total) * 100) : null;
  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, color: "var(--text-dim)", marginBottom: 6 }}>
        <span>{job.message || "Working…"}</span>
        {pct != null && <span className="mono">{job.done}/{job.total}</span>}
      </div>
      <div className="job-progress-track">
        <div
          className={`job-progress-fill ${pct == null ? "indeterminate" : ""}`}
          style={pct != null ? { width: `${pct}%` } : undefined}
        />
      </div>
    </div>
  );
}

// Counts a stat numeral up from 0 on mount/change — skipped for non-numeric
// placeholders ("—") and under prefers-reduced-motion.
export function CountUp({ value, duration = 900 }) {
  const [display, setDisplay] = useState(typeof value === "number" ? 0 : value);

  useEffect(() => {
    if (typeof value !== "number") {
      setDisplay(value);
      return;
    }
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setDisplay(value);
      return;
    }
    let raf;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(value * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  return <>{display}</>;
}

export function EmptyState({ icon = "documents", title, hint }) {
  return (
    <div style={{ textAlign: "center", padding: "34px 20px", color: "var(--text-faint)" }}>
      <div style={{
        width: 56, height: 56, margin: "0 auto 14px", borderRadius: "50%",
        border: "1.5px solid var(--border-strong)", display: "grid", placeItems: "center",
        boxShadow: "inset 0 0 0 4px var(--surface-2)",
      }}>
        <Icon name={icon} size={22} />
      </div>
      <div style={{ fontSize: 14.5, fontWeight: 600, color: "var(--text-dim)" }}>{title}</div>
      {hint && <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>{hint}</div>}
    </div>
  );
}
