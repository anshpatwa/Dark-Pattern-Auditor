"use strict";

const $ = (sel) => document.querySelector(sel);

const SEV_ORDER = ["critical", "high", "medium", "low"];
const GRADE_COLOR = {
  A: "var(--good)", B: "#8fe34a", C: "var(--low)", D: "var(--medium)", F: "var(--high)",
};

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// --- Boot ----------------------------------------------------------------
async function boot() {
  try {
    const health = await fetch("/api/health").then((r) => r.json());
    const pill = $("#enginePill");
    if (health.engine === "claude") {
      pill.textContent = `AI · Claude (${health.model})`;
      pill.classList.add("ai");
    } else {
      pill.textContent = "Heuristic mode (add API key for AI)";
      pill.classList.add("heuristic");
    }
  } catch {
    $("#enginePill").textContent = "offline";
  }

  try {
    const tax = await fetch("/api/taxonomy").then((r) => r.json());
    $("#taxonomyChips").innerHTML = tax.categories
      .map((c) => `<span class="tax" title="${esc(c.description)}"><b>${esc(c.name)}</b> · ${c.patterns.length}</span>`)
      .join("");
  } catch { /* non-fatal */ }
}

// --- Audit flow ----------------------------------------------------------
$("#auditForm").addEventListener("submit", (e) => {
  e.preventDefault();
  runAudit($("#urlInput").value.trim());
});

document.querySelectorAll(".chip").forEach((chip) =>
  chip.addEventListener("click", () => {
    $("#urlInput").value = chip.dataset.url;
    runAudit(chip.dataset.url);
  })
);

async function runAudit(url) {
  if (!url) return;
  const btn = $("#auditBtn");
  const status = $("#status");
  const results = $("#results");

  btn.disabled = true;
  results.classList.add("hidden");
  status.className = "status";
  status.innerHTML = `<div class="spinner"></div><div>Auditing <b>${esc(url)}</b> — rendering page and analysing…</div>`;
  status.classList.remove("hidden");

  try {
    const resp = await fetch("/api/audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, use_browser: $("#browserToggle").checked }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${resp.status})`);
    }
    const report = await resp.json();
    status.classList.add("hidden");
    render(report);
  } catch (err) {
    status.className = "status error";
    status.innerHTML = `⚠️ ${esc(err.message)}`;
  } finally {
    btn.disabled = false;
  }
}

// --- Rendering -----------------------------------------------------------
function render(report) {
  const results = $("#results");

  // Score ring
  const ring = $("#gradeRing");
  ring.style.setProperty("--ring-color", GRADE_COLOR[report.grade] || "var(--good)");
  ring.style.setProperty("--ring-deg", `${Math.round((report.score / 100) * 360)}deg`);
  $("#gradeLetter").textContent = report.grade;
  $("#gradeLetter").style.color = GRADE_COLOR[report.grade] || "var(--good)";

  $("#scoreValue").textContent = report.score;
  $("#riskLine").textContent = `${cap(report.risk_level)} risk`;
  $("#metaLine").textContent =
    `Engine: ${report.engine}${report.model ? ` (${report.model})` : ""} · ${report.findings.length} finding(s)`;

  // Severity counts
  const counts = report.counts_by_severity || {};
  $("#sevCounts").innerHTML = SEV_ORDER.map(
    (s) => `<div class="pill ${s}"><b>${counts[s] || 0}</b><small>${s}</small></div>`
  ).join("");

  $("#summary").textContent = report.summary || "";

  // Findings
  const findingsEl = $("#findings");
  $("#findingsTitle").textContent = `Findings (${report.findings.length})`;
  if (!report.findings.length) {
    findingsEl.innerHTML = `<div class="clean">✅ No dark patterns were detected on this page.</div>`;
  } else {
    const sorted = [...report.findings].sort(
      (a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity)
    );
    findingsEl.innerHTML = sorted.map(findingCard).join("");
  }

  // Notes
  const notes = report.notes || [];
  $("#notesWrap").classList.toggle("hidden", notes.length === 0);
  $("#notes").innerHTML = notes.map((n) => `<li>${esc(n)}</li>`).join("");

  // Shareable report (built client-side from the data — no second audit)
  const link = $("#reportLink");
  const blob = new Blob([standaloneHtml(report)], { type: "text/html" });
  link.href = URL.createObjectURL(blob);

  results.classList.remove("hidden");
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function findingCard(f) {
  const conf = Math.round((f.confidence ?? 0) * 100);
  const label = (f.category || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return `
    <div class="finding ${f.severity}">
      <div class="finding-head">
        <span class="sev-badge ${f.severity}">${esc(f.severity)}</span>
        <h3>${esc(f.title)}</h3>
        <span class="confidence">${conf}% confidence</span>
      </div>
      <div class="finding-meta">${esc(label)} · <code>${esc(f.pattern_key)}</code>${f.location ? " · " + esc(f.location) : ""}</div>
      <p>${esc(f.description)}</p>
      <blockquote>${esc(f.evidence)}</blockquote>
      <p class="rec"><strong>Fix:</strong> ${esc(f.recommendation)}</p>
    </div>`;
}

function standaloneHtml(report) {
  const rows = (report.findings || [])
    .map(
      (f) => `<div style="border-left:4px solid #888;padding:12px 16px;margin:10px 0;background:#181b24;border-radius:10px">
      <strong>${esc(f.title)}</strong> — ${esc(f.severity).toUpperCase()}<br>
      <small style="color:#8a90a2">${esc(f.category)} · ${esc(f.pattern_key)}</small>
      <p>${esc(f.description)}</p>
      <blockquote style="color:#c9cdd8;font-style:italic">${esc(f.evidence)}</blockquote>
      <em style="color:#9fb4d8">Fix: ${esc(f.recommendation)}</em></div>`
    )
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>Audit — ${esc(report.url)}</title>
    <style>body{font-family:system-ui;background:#0f1117;color:#e6e8ee;max-width:820px;margin:0 auto;padding:32px}</style>
    </head><body>
    <h1>Dark Pattern Audit</h1>
    <p style="color:#8a90a2">${esc(report.url)}</p>
    <h2>${esc(report.grade)} · ${report.score}/100 · ${esc(report.risk_level)} risk</h2>
    <p>${esc(report.summary)}</p>
    ${rows || "<p>No dark patterns detected.</p>"}
    <hr><small style="color:#5b6072">Generated by Dark Pattern Auditor</small>
    </body></html>`;
}

const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

boot();
