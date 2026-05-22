"use strict";

const form = document.getElementById("analyze-form");
const status = document.getElementById("status");
const result = document.getElementById("result");
const submitBtn = document.getElementById("submit-btn");
const panels = document.querySelectorAll(".mode-panel");

document.querySelectorAll('input[name="mode"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    panels.forEach((p) => {
      p.hidden = p.dataset.panel !== radio.value;
    });
  });
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  status.className = "";
  status.textContent = "Analyzing… (~30 s for first run)";
  result.innerHTML = "";
  submitBtn.disabled = true;

  const mode = document.querySelector('input[name="mode"]:checked').value;
  const model = document.querySelector('input[name="model"]:checked').value;
  const useCache = document.getElementById("use-cache").checked;

  try {
    let response;
    if (mode === "url") {
      const url = document.getElementById("input-url").value.trim();
      response = await fetch("/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, model, use_cache: useCache }),
      });
    } else if (mode === "paste") {
      const text = document.getElementById("input-paste").value;
      const sourceUrl = document.getElementById("input-source-url").value.trim();
      const body = { text, model, use_cache: useCache };
      if (sourceUrl) body.source_url = sourceUrl;
      response = await fetch("/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } else {
      const fileInput = document.getElementById("input-file");
      if (!fileInput.files[0]) {
        throw new Error("Select a file to upload.");
      }
      const fd = new FormData();
      fd.append("file", fileInput.files[0]);
      fd.append("model", model);
      fd.append("use_cache", useCache ? "true" : "false");
      response = await fetch("/analyze", { method: "POST", body: fd });
    }

    const data = await response.json();
    if (!response.ok) {
      renderError(data);
    } else {
      renderReport(data);
    }
  } catch (err) {
    renderError({ error: "ClientError", message: err.message });
  } finally {
    submitBtn.disabled = false;
    status.textContent = "";
  }
});

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function sevClass(s) { return `sev-${s}`; }

function renderError(body) {
  status.className = "error";
  status.textContent = `${body.error || "Error"}: ${body.message || "(no message)"}`;
}

function renderReport(data) {
  const r = data.report;
  const dir = data.report_dir;

  const parts = [];
  parts.push(`<div class="headline">${escapeHtml(r.headline)}</div>`);
  parts.push(
    `<div class="meta">Overall risk: <span class="${sevClass(r.overall_risk)}">` +
    `${escapeHtml(r.overall_risk.toUpperCase())}</span> &nbsp; Model: ${escapeHtml(r.model)}` +
    ` &nbsp; Taxonomy: ${escapeHtml(r.taxonomy_version)}</div>`
  );
  if (dir) {
    parts.push(
      `<div class="meta">Wrote: <a href="file://${escapeHtml(dir)}">${escapeHtml(dir)}</a>` +
      (data.cache_hit ? " <em>(cache hit)</em>" : "") + "</div>"
    );
  }

  parts.push("<h2>Core findings</h2>");
  parts.push("<table class='core'><thead><tr><th>Category</th><th>Severity</th>" +
             "<th>Summary &amp; why it matters</th></tr></thead><tbody>");
  for (const f of r.core_findings) {
    const evList = (f.evidence || [])
      .map((e) => `<blockquote>${escapeHtml(e.quote)}</blockquote>`).join("");
    parts.push(
      `<tr><td>${escapeHtml(f.category)}</td>` +
      `<td class="${sevClass(f.severity)}">${escapeHtml(f.severity.toUpperCase())}</td>` +
      `<td><strong>${escapeHtml(f.summary)}</strong><br>` +
      `<span class="meta">${escapeHtml(f.why_it_matters)}</span>` +
      `<details class="evidence"><summary>Evidence</summary>${evList}</details></td></tr>`
    );
  }
  parts.push("</tbody></table>");

  parts.push("<h2>Flags</h2><div class='flags'>");
  for (const f of r.flags) {
    parts.push(
      `<span class="flag-chip flag-${f.presence}" title="${escapeHtml(f.note)}">` +
      `${escapeHtml(f.category)}: ${escapeHtml(f.presence)}</span>`
    );
  }
  parts.push("</div>");

  if (r.notes && r.notes.length) {
    parts.push("<h2>Notes</h2><ul>");
    for (const n of r.notes) parts.push(`<li>${escapeHtml(n)}</li>`);
    parts.push("</ul>");
  }

  result.innerHTML = parts.join("\n");
}
