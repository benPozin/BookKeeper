// Tiny fetch wrapper. Same-origin in production; proxied to :8765 in dev.

let authToken = "";
try {
  authToken = localStorage.getItem("bk-auth") || "";
} catch {
  /* private browsing */
}

export function setAuthToken(token) {
  authToken = token || "";
  try {
    localStorage.setItem("bk-auth", authToken);
  } catch {
    /* private browsing — PIN will be asked again next visit */
  }
}

// File links and iframes can't send headers — those URLs carry ?auth= instead.
const authQuery = () => (authToken ? `?auth=${authToken}` : "");
const authHeaders = () => (authToken ? { "X-BK-Auth": authToken } : {});

async function request(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401 && !path.startsWith("/api/auth")) {
    window.dispatchEvent(new Event("bk-auth-required"));
    throw new Error("PIN required");
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  health: () => request("/api/health"),
  dashboard: () => request("/api/dashboard/summary"),
  dashboardChecklist: (year) => request(`/api/dashboard/checklist/${encodeURIComponent(year)}`),
  feature: (id) => request(`/api/features/${id}`),
  folderStructure: () => request("/api/features/organizer/folder-structure"),
  getSettings: () => request("/api/settings"),
  saveSettings: (values) =>
    request("/api/settings", {
      method: "PUT",
      body: JSON.stringify({ values }),
    }),

  gmailStatus: () => request("/api/gmail/status"),
  gmailScan: (full = false) =>
    request(`/api/gmail/scan${full ? "?full=true" : ""}`, { method: "POST" }),
  gmailScanAsync: (full = false) =>
    request(`/api/gmail/scan-async${full ? "?full=true" : ""}`, { method: "POST" }),
  gmailConnect: () => request("/api/gmail/connect", { method: "POST" }),
  gmailDisconnect: () => request("/api/gmail/disconnect", { method: "POST" }),
  gmailBusinesses: () => request("/api/gmail/businesses"),
  gmailAttachmentsStatus: () => request("/api/gmail/attachments/status"),
  gmailAttachmentsAsync: () =>
    request("/api/gmail/attachments-async", { method: "POST" }),

  docStatus: () => request("/api/documents/status"),
  docScan: () => request("/api/documents/scan", { method: "POST" }),
  docScanAsync: () => request("/api/documents/scan-async", { method: "POST" }),
  docGenerateSamples: () => request("/api/documents/generate-samples", { method: "POST" }),
  docList: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null && v !== "")
    ).toString();
    return request(`/api/documents${qs ? `?${qs}` : ""}`);
  },
  docConfirm: (id, body) =>
    request(`/api/documents/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  docFileUrl: (id) => `/api/documents/${id}/file${authQuery()}`,
  docReviewQueue: () => request("/api/documents/review-queue"),
  docExtractFieldsAsync: () =>
    request("/api/documents/extract-fields-async", { method: "POST" }),
  docBulk: (body) =>
    request("/api/documents/bulk", { method: "PUT", body: JSON.stringify(body) }),

  scanStatus: () => request("/api/scan/status"),
  scanLanUrl: () => request("/api/scan/lan-url"),
  scanWatchStart: () => request("/api/scan/watch/start", { method: "POST" }),
  scanWatchStop: () => request("/api/scan/watch/stop", { method: "POST" }),
  scanUpload: (fileObj) => {
    const fd = new FormData();
    fd.append("file", fileObj);
    return fetch("/api/scan/upload", {
      method: "POST",
      body: fd,
      headers: authHeaders(),
    }).then((r) => r.json());
  },

  templatesList: () => request("/api/templates"),
  templatesBuild: (year) =>
    request("/api/templates/build", { method: "POST", body: JSON.stringify({ year }) }),

  organizerYears: () => request("/api/organizer/years"),
  organizerPlan: (year) => request(`/api/organizer/plan?year=${encodeURIComponent(year)}`),
  organizerApply: (year) =>
    request("/api/organizer/apply", { method: "POST", body: JSON.stringify({ year }) }),
  organizerUnfile: (year) =>
    request("/api/organizer/unfile", { method: "POST", body: JSON.stringify({ year }) }),

  automationStatus: () => request("/api/automation/status"),
  automationEnable: (hour, minute) =>
    request("/api/automation/enable", { method: "POST", body: JSON.stringify({ hour, minute }) }),
  automationDisable: () => request("/api/automation/disable", { method: "POST" }),
  automationRunNow: () => request("/api/automation/run-now", { method: "POST" }),

  exportYears: () => request("/api/export/years"),
  exportSummary: (year) => request(`/api/export/summary?year=${encodeURIComponent(year)}`),
  exportBuild: (year) =>
    request("/api/export/build", { method: "POST", body: JSON.stringify({ year }) }),
  exportTree: (year) => request(`/api/export/tree?year=${encodeURIComponent(year)}`),
  exportReveal: (year, target = "folder") =>
    request("/api/export/reveal", { method: "POST", body: JSON.stringify({ year, target }) }),
  exportDownloadUrl: (year) =>
    `/api/export/download/${encodeURIComponent(year)}${authQuery()}`,

  diagnostics: () => request("/api/diagnostics"),
  authStatus: () => request("/api/auth/status"),
  authLogin: (pin) =>
    request("/api/auth/login", { method: "POST", body: JSON.stringify({ pin }) }),

  aiStatus: () => request("/api/ai/status"),
  aiReview: () => request("/api/ai/review", { method: "POST" }),
  aiReviewAsync: () => request("/api/ai/review-async", { method: "POST" }),
  aiOverview: () => request("/api/ai/overview"),
  aiEnable: (enabled) =>
    request("/api/ai/enable", { method: "POST", body: JSON.stringify({ enabled }) }),

  jobStatus: (id) => request(`/api/jobs/${id}`),
  gmailEmails: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null && v !== "")
    ).toString();
    return request(`/api/gmail/emails${qs ? `?${qs}` : ""}`);
  },
};
