(function (window) {
  "use strict";

  function sanitizeFileName(value) {
    return String(value || "report")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 80) || "report";
  }

  function downloadJsonReport(filename, payload) {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function formatValue(value) {
    if (value === null || value === undefined || value === "") {
      return "--";
    }
    if (Array.isArray(value)) {
      if (!value.length) {
        return "--";
      }
      return value
        .map((item) => (typeof item === "object" ? JSON.stringify(item) : String(item)))
        .join(", ");
    }
    if (typeof value === "object") {
      return JSON.stringify(value, null, 2);
    }
    return String(value);
  }

  function buildRows(report) {
    const rows = [];
    rows.push(["Generated at", report.generated_at ? new Date(report.generated_at).toLocaleString() : "--"]);
    rows.push(["Model used", report.model_used || "--"]);
    if (report.scope) {
      rows.push(["Scope", report.scope]);
    }
    if (report.structured_context && Object.keys(report.structured_context).length) {
      rows.push(["Structured context", report.structured_context]);
    }
    return rows;
  }

  function citationsMarkup(citations) {
    if (!Array.isArray(citations) || !citations.length) {
      return `<p class="report-empty">No source citations available.</p>`;
    }

    return `
      <table class="report-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Source</th>
            <th>Score</th>
            <th>Excerpt</th>
          </tr>
        </thead>
        <tbody>
          ${citations
            .map(
              (item) => `
                <tr>
                  <td>${escapeHtml(item.title || "--")}</td>
                  <td>${escapeHtml(item.source_name || item.source_type || "--")}</td>
                  <td>${escapeHtml(Number(item.score || 0).toFixed(2))}</td>
                  <td>${escapeHtml(item.excerpt || "--")}</td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    `;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function buildPrintableHtml(report, options = {}) {
    const title = options.title || report.title || "Report";
    const subtitle = options.subtitle || "Printable summary";
    const rows = buildRows(report)
      .map(
        ([label, value]) => `
          <div class="report-row">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(formatValue(value))}</strong>
          </div>
        `,
      )
      .join("");

    const citations = citationsMarkup(report.citations || []);
    const summary = escapeHtml(report.summary || "No summary available.");

    return `
      <!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>${escapeHtml(title)}</title>
        <style>
          :root { color-scheme: light; }
          body {
            margin: 0;
            padding: 32px;
            font-family: Arial, Helvetica, sans-serif;
            color: #102033;
            background: #f6f8fb;
          }
          .report-shell {
            max-width: 980px;
            margin: 0 auto;
            background: #ffffff;
            border: 1px solid #d8e0ea;
            border-radius: 18px;
            padding: 28px;
            box-shadow: 0 20px 40px rgba(16, 32, 51, 0.08);
          }
          h1 {
            margin: 0 0 6px;
            font-size: 30px;
          }
          .subtitle {
            margin: 0 0 18px;
            color: #5c6d82;
          }
          .summary {
            padding: 16px;
            border-radius: 14px;
            background: #f2f6fb;
            line-height: 1.7;
            white-space: pre-wrap;
          }
          .report-grid {
            display: grid;
            gap: 10px;
            margin: 20px 0;
          }
          .report-row {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            padding: 12px 14px;
            border-radius: 12px;
            border: 1px solid #d8e0ea;
            background: #fbfdff;
          }
          .report-row span {
            color: #5c6d82;
          }
          .report-section {
            margin-top: 24px;
          }
          .report-section h2 {
            margin: 0 0 12px;
            font-size: 18px;
          }
          .report-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
          }
          .report-table th,
          .report-table td {
            text-align: left;
            vertical-align: top;
            border-bottom: 1px solid #d8e0ea;
            padding: 10px 8px;
          }
          .report-table th {
            color: #5c6d82;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
          }
          .report-empty {
            color: #5c6d82;
            font-style: italic;
          }
          pre {
            margin: 0;
            white-space: pre-wrap;
            word-break: break-word;
            background: #f2f6fb;
            padding: 14px;
            border-radius: 12px;
            overflow: auto;
          }
          @media print {
            body {
              background: #ffffff;
              padding: 0;
            }
            .report-shell {
              border: 0;
              box-shadow: none;
              border-radius: 0;
              padding: 0;
            }
          }
        </style>
      </head>
      <body>
        <div class="report-shell">
          <h1>${escapeHtml(title)}</h1>
          <p class="subtitle">${escapeHtml(subtitle)}</p>
          <div class="summary">${summary}</div>
          <div class="report-grid">
            ${rows
              .map(
                ([label, value]) => `
                  <div class="report-row">
                    <span>${escapeHtml(label)}</span>
                    <strong>${escapeHtml(formatValue(value))}</strong>
                  </div>
                `,
              )
              .join("")}
          </div>
          <div class="report-section">
            <h2>Source citations</h2>
            ${citations}
          </div>
        </div>
      </body>
      </html>
    `;
  }

  function openPrintWindow(options = {}) {
    const win = window.open("", "_blank", "noopener,noreferrer");
    if (!win) {
      return null;
    }
    const title = options.title || "Report";
    const loadingMessage = options.loadingMessage || "Loading report...";
    win.document.open();
    win.document.write(`
      <!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>${escapeHtml(title)}</title>
      </head>
      <body>
        <p style="font-family: Arial, sans-serif; padding: 24px;">${escapeHtml(loadingMessage)}</p>
      </body>
      </html>
    `);
    win.document.close();
    return win;
  }

  function renderPrintWindow(win, report, options = {}) {
    if (!win || win.closed) {
      return false;
    }
    const html = buildPrintableHtml(report, options);
    win.document.open();
    win.document.write(html);
    win.document.close();
    win.focus();
    return true;
  }

  window.EnergyReports = {
    sanitizeFileName,
    downloadJsonReport,
    buildPrintableHtml,
    openPrintWindow,
    renderPrintWindow,
  };
})(window);
