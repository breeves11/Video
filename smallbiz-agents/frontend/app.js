const API = "/api";

function showError(message) {
  const banner = document.getElementById("error-banner");
  banner.textContent = message;
  banner.style.display = "block";
  setTimeout(() => { banner.style.display = "none"; }, 6000);
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch (e) {}
    throw new Error(detail);
  }
  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? response.json() : response.text();
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function badge(value, kind) {
  return `<span class="badge badge-${escapeHtml(value)}">${escapeHtml(value)}</span>`;
}

// --- Tabs -------------------------------------------------------------

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "contacts") loadContacts();
    if (btn.dataset.tab === "report") { loadReport(); loadReportSettings(); }
  });
});

// --- Inbox / emails ------------------------------------------------------

async function loadEmails() {
  const status = document.getElementById("email-status-filter").value;
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  try {
    const { emails } = await api(`/emails${query}`);
    renderEmails(emails);
  } catch (err) {
    showError(`Failed to load emails: ${err.message}`);
  }
}

function renderEmails(emails) {
  const list = document.getElementById("email-list");
  const empty = document.getElementById("email-empty");
  list.innerHTML = "";
  empty.style.display = emails.length ? "none" : "block";

  for (const email of emails) {
    const item = document.createElement("div");
    item.className = "inbox-item";
    const canAct = ["pending", "queued_send_unconfigured", "send_failed"].includes(email.status);
    item.innerHTML = `
      <div class="inbox-item-head">
        <strong>${escapeHtml(email.subject || "(no subject)")}</strong>
        <div>${badge(email.category)} ${badge(email.urgency)}</div>
      </div>
      <div class="meta">From ${escapeHtml(email.contact_name || email.contact_email)} &lt;${escapeHtml(email.contact_email)}&gt; -- ${escapeHtml(email.status)} -- drafted by ${escapeHtml(email.ai_source)}</div>
      <div class="body-text">${escapeHtml(email.body)}</div>
      ${(email.attachments || []).length ? `
        <div class="attachments">📎 ${email.attachments.length} attachment${email.attachments.length === 1 ? "" : "s"}: ${email.attachments.map(escapeHtml).join(", ")}
          <span class="hint">-- the AI can't see these; open them in your mailbox before replying. Never auto-sent.</span>
        </div>` : ""}
      <div class="draft-box">
        <textarea data-id="${email.id}" class="draft-text" ${canAct ? "" : "disabled"}>${escapeHtml(email.ai_draft || "")}</textarea>
      </div>
      <div class="actions">
        ${canAct ? `<button class="send-btn" data-id="${email.id}">Approve &amp; send</button>` : ""}
        ${canAct ? `<button class="btn-delete dismiss-btn" data-id="${email.id}">Dismiss</button>` : ""}
        <button class="btn-delete delete-btn" data-id="${email.id}">Delete</button>
      </div>
    `;
    list.appendChild(item);
  }

  list.querySelectorAll(".send-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      const text = list.querySelector(`.draft-text[data-id="${id}"]`).value;
      try {
        await api(`/emails/${id}/send`, { method: "POST", body: JSON.stringify({ text }) });
        loadEmails();
      } catch (err) {
        showError(`Failed to send: ${err.message}`);
      }
    });
  });
  list.querySelectorAll(".dismiss-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api(`/emails/${btn.dataset.id}/dismiss`, { method: "POST" });
      loadEmails();
    });
  });
  list.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api(`/emails/${btn.dataset.id}`, { method: "DELETE" });
      loadEmails();
    });
  });
}

document.getElementById("refresh-emails").addEventListener("click", loadEmails);
document.getElementById("email-status-filter").addEventListener("change", loadEmails);

document.getElementById("simulate-email-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const from_address = document.getElementById("sim-from").value;
  const subject = document.getElementById("sim-subject").value;
  const body = document.getElementById("sim-body").value;
  try {
    await api("/emails/simulate", {
      method: "POST",
      body: JSON.stringify({ from_address, subject, body }),
    });
    document.getElementById("simulate-email-form").reset();
    document.getElementById("email-status-filter").value = "";
    loadEmails();
  } catch (err) {
    showError(`Failed to simulate email: ${err.message}`);
  }
});

// --- Calls ---------------------------------------------------------------

async function loadCalls() {
  try {
    const { calls } = await api("/calls");
    renderCalls(calls);
  } catch (err) {
    showError(`Failed to load calls: ${err.message}`);
  }
}

function renderCalls(calls) {
  const body = document.getElementById("calls-body");
  const empty = document.getElementById("calls-empty");
  body.innerHTML = "";
  empty.style.display = calls.length ? "none" : "block";

  for (const call of calls) {
    const row = document.createElement("tr");
    const summary = call.ai_summary || call.transcript || "";
    const recording = call.recording_url
      ? `<audio controls preload="none" style="max-width:200px;"><source src="${API}/calls/${call.id}/recording" type="audio/mpeg"></audio>`
      : "";
    row.innerHTML = `
      <td>${escapeHtml(call.from_number)}</td>
      <td>${escapeHtml(call.status)}</td>
      <td>${badge(call.category)}</td>
      <td>${badge(call.urgency)}</td>
      <td style="white-space:normal; max-width:280px;">${escapeHtml(summary)}</td>
      <td>${recording}</td>
      <td>${call.callback_requested ? "Yes" : "No"}</td>
      <td>${call.handled ? "" : `<button class="btn-delete handled-btn" data-id="${call.id}">Mark handled</button>`}</td>
    `;
    body.appendChild(row);
  }

  body.querySelectorAll(".handled-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api(`/calls/${btn.dataset.id}/handled`, { method: "POST" });
      loadCalls();
    });
  });
}

document.getElementById("refresh-calls").addEventListener("click", loadCalls);

// --- Test call simulator (posts Twilio-shaped form data directly) --------

let testCallSid = null;

function extractSpokenText(twimlXml) {
  const matches = [...twimlXml.matchAll(/<Say>([\s\S]*?)<\/Say>/g)].map((m) => m[1]);
  return matches.join("\n");
}

document.getElementById("test-call-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  testCallSid = `TEST${Date.now()}`;
  const from = document.getElementById("test-caller").value || "+15550001234";
  const form = new FormData();
  form.append("CallSid", testCallSid);
  form.append("From", from);
  const response = await fetch(`${API}/phone/simulate/voice`, { method: "POST", body: form });
  const xml = await response.text();
  document.getElementById("test-call-output").textContent = `AI: ${extractSpokenText(xml)}`;
  document.getElementById("test-speech-form").style.display = "flex";
});

document.getElementById("test-speech-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!testCallSid) return;
  const speech = document.getElementById("test-speech").value;
  const form = new FormData();
  form.append("CallSid", testCallSid);
  form.append("SpeechResult", speech);
  const response = await fetch(`${API}/phone/simulate/gather`, { method: "POST", body: form });
  const xml = await response.text();
  const output = document.getElementById("test-call-output");
  output.textContent += `\nCaller: ${speech}\nAI: ${extractSpokenText(xml)}`;
  document.getElementById("test-speech").value = "";
  loadCalls();
});

// --- Contacts --------------------------------------------------------------

async function loadContacts() {
  try {
    const { contacts } = await api("/contacts");
    renderContacts(contacts);
  } catch (err) {
    showError(`Failed to load contacts: ${err.message}`);
  }
}

function renderContacts(contacts) {
  const body = document.getElementById("contacts-body");
  const empty = document.getElementById("contacts-empty");
  body.innerHTML = "";
  empty.style.display = contacts.length ? "none" : "block";

  for (const contact of contacts) {
    const row = document.createElement("tr");
    const who = contact.name
      ? `${escapeHtml(contact.name)} <span class="hint">${escapeHtml(contact.identity)}</span>`
      : escapeHtml(contact.identity);
    const last = contact.last_contact_at ? new Date(contact.last_contact_at).toLocaleString() : "";
    row.innerHTML = `
      <td>${who}</td>
      <td>${contact.channels.map((c) => `<span class="badge badge-other">${escapeHtml(c)}</span>`).join(" ")}</td>
      <td>${contact.interactions}</td>
      <td>${contact.open_items ? `<span class="badge badge-medium">${contact.open_items} open</span>` : "--"}</td>
      <td>${escapeHtml(last)}</td>
    `;
    body.appendChild(row);
  }
}

document.getElementById("refresh-contacts").addEventListener("click", loadContacts);

// --- Report ----------------------------------------------------------------

let reportData = null;

function humanizeMinutes(minutes) {
  if (minutes === null || minutes === undefined) return "--";
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const hours = minutes / 60;
  if (hours < 48) return `${Number(hours.toFixed(1))} h`;
  return `${Math.round(hours / 24)} days`;
}

function shortDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

// A stat tile: label, value (+ optional unit), then optional sub-line,
// delta (vs previous period) and status. Status always pairs its color with
// an icon and words, never color alone.
function tile({ label, value, unit, sub, delta, status }) {
  const node = el("div", "tile");
  node.appendChild(el("div", "tile-label", label));
  const valueEl = el("div", "tile-value", value);
  if (unit) {
    valueEl.appendChild(document.createTextNode(" "));
    valueEl.appendChild(el("span", "unit", unit));
  }
  node.appendChild(valueEl);
  if (sub) node.appendChild(el("div", "tile-sub", sub));
  if (delta) node.appendChild(el("div", `tile-delta ${delta.tone || ""}`, delta.text));
  if (status) node.appendChild(el("div", `tile-status ${status.tone}`, status.text));
  return node;
}

function countDelta(current, previous) {
  if (!current && !previous) return null;
  const diff = current - previous;
  if (diff === 0) return { text: "Same as the previous 7 days" };
  return { text: `${diff > 0 ? "▲" : "▼"} ${Math.abs(diff)} vs the previous 7 days` };
}

function durationDelta(current, previous) {
  if (current === null || previous === null) return null;
  const diff = current - previous;
  if (Math.abs(diff) < 1) return { text: "Same as the previous 7 days" };
  return diff < 0
    ? { text: `▼ ${humanizeMinutes(-diff)} faster than the previous 7 days`, tone: "good" }
    : { text: `▲ ${humanizeMinutes(diff)} slower than the previous 7 days`, tone: "bad" };
}

function renderBeforeAfter(baseline) {
  const container = document.getElementById("report-before-after");
  container.innerHTML = "";
  const tiles = [];

  if (baseline.missed_calls_per_week !== null) {
    const before = baseline.missed_calls_per_week;
    const now = baseline.missed_calls_per_week_now;
    const fewer = before - now;
    tiles.push(tile({
      label: "Missed calls per week",
      value: `${before}`,
      unit: `before → ${now} now`,
      status: fewer > 0
        ? { text: `✓ ${Number(fewer.toFixed(1))} fewer per week`, tone: "good" }
        : { text: "No improvement yet", tone: "" },
    }));
  }
  if (baseline.email_reply_hours !== null && baseline.email_reply_hours_now !== null) {
    const beforeMin = baseline.email_reply_hours * 60;
    const nowMin = baseline.email_reply_hours_now * 60;
    tiles.push(tile({
      label: "Typical email reply time",
      value: humanizeMinutes(beforeMin),
      unit: `before → ${humanizeMinutes(nowMin)} now`,
      status: nowMin < beforeMin
        ? { text: `✓ ${humanizeMinutes(beforeMin - nowMin)} faster`, tone: "good" }
        : { text: "No improvement yet", tone: "" },
    }));
  }

  if (tiles.length) {
    container.appendChild(el("h3", "", "Before vs now"));
    container.lastChild.style.cssText = "margin:1rem 0 0; font-size:0.95rem;";
    const row = el("div", "tile-row before-after");
    tiles.forEach((t) => row.appendChild(t));
    container.appendChild(row);
  } else {
    const prompt = el("div", "baseline-prompt", "Add the business's numbers from before the agents went live to see before vs now. ");
    const link = el("a", "", "Set the starting point ↓");
    link.href = "#report-settings";
    link.addEventListener("click", (e) => {
      e.preventDefault();
      document.getElementById("report-settings").scrollIntoView({ behavior: "smooth" });
      document.getElementById("baseline-missed").focus({ preventScroll: true });
    });
    prompt.appendChild(link);
    container.appendChild(prompt);
  }
}

function renderTiles(report) {
  const { calls, emails } = report.current;
  const prev = report.previous;
  const open = report.open;
  const container = document.getElementById("report-tiles");
  container.innerHTML = "";

  container.appendChild(tile({
    label: "Calls answered by the AI",
    value: `${calls.answered_by_ai}`,
    sub: `${calls.resolved_on_call} resolved on the call`,
    delta: countDelta(calls.answered_by_ai, prev.calls.answered_by_ai),
  }));

  if (calls.missed) {
    const outstanding = calls.missed - calls.missed_followed_up;
    container.appendChild(tile({
      label: "Missed calls followed up",
      value: `${calls.missed_followed_up}`,
      unit: `of ${calls.missed}`,
      sub: `${calls.missed_texted_back} texted back automatically`,
      status: outstanding
        ? { text: `⚠ ${outstanding} not followed up yet`, tone: "warn" }
        : { text: "✓ All followed up", tone: "good" },
    }));
  } else {
    container.appendChild(tile({
      label: "Missed calls",
      value: "0",
      status: calls.total ? { text: "✓ Every call was answered", tone: "good" } : null,
      sub: calls.total ? null : "No calls yet",
    }));
  }

  container.appendChild(tile({
    label: "Typical email reply time",
    value: humanizeMinutes(emails.median_reply_minutes),
    sub: emails.replied_within_hour_pct === null ? "No replies sent yet" : `${emails.replied_within_hour_pct}% replied within an hour`,
    delta: durationDelta(emails.median_reply_minutes, prev.emails.median_reply_minutes),
  }));

  container.appendChild(tile({
    label: "Emails replied",
    value: `${emails.replied}`,
    unit: `of ${emails.received}`,
    sub: `${emails.auto_replied} automatically · ${emails.owner_replied} by you`,
  }));

  const waiting = open.emails_waiting + open.callbacks_waiting;
  const waitingParts = [];
  if (open.emails_waiting) waitingParts.push(`oldest email waiting ${humanizeMinutes(open.oldest_email_waiting_minutes)}`);
  if (open.callbacks_waiting) waitingParts.push(`${open.callbacks_waiting} callback${open.callbacks_waiting === 1 ? "" : "s"}`);
  container.appendChild(tile({
    label: "Waiting for you now",
    value: `${waiting}`,
    sub: `${open.emails_waiting} email${open.emails_waiting === 1 ? "" : "s"} · ${open.callbacks_waiting} callback${open.callbacks_waiting === 1 ? "" : "s"}`,
    status: waiting
      ? { text: `⚠ ${waitingParts.join(", ")}`, tone: "warn" }
      : { text: "✓ All caught up", tone: "good" },
  }));
}

function niceTicks(max) {
  if (max <= 0) return [0, 1, 2, 3, 4];
  const steps = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000];
  const step = steps.find((s) => max / s <= 4) || Math.ceil(max / 4);
  const top = Math.ceil(max / step) * step;
  const ticks = [];
  for (let v = 0; v <= top; v += step) ticks.push(v);
  return ticks;
}

function compact(n) {
  return n >= 1000 ? `${Number((n / 1000).toFixed(1))}K` : `${n}`;
}

const SVG_NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs, className) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
  if (className) node.setAttribute("class", className);
  return node;
}

// Rounded 4px at the data end (top), square at the baseline.
function topRoundedBar(x, y, w, h) {
  const r = Math.min(4, h, w / 2);
  return `M${x},${y + h} L${x},${y + r} Q${x},${y} ${x + r},${y} L${x + w - r},${y} Q${x + w},${y} ${x + w},${y + r} L${x + w},${y + h} Z`;
}

function renderTrendChart(weekly) {
  const wrap = document.getElementById("report-chart");
  wrap.innerHTML = "";
  const width = Math.max(wrap.clientWidth, 280);
  const height = 230;
  const m = { top: 20, right: 6, bottom: 28, left: 34 };
  const plotW = width - m.left - m.right;
  const plotH = height - m.top - m.bottom;
  const totals = weekly.map((w) => w.emails + w.calls);
  const ticks = niceTicks(Math.max(...totals, 0));
  const yMax = ticks[ticks.length - 1];
  const y = (v) => m.top + plotH - (v / yMax) * plotH;
  const band = plotW / weekly.length;
  const barW = Math.min(24, band * 0.6);
  const GAP = 2;

  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "img",
    "aria-label": "Customer contacts per week, last 8 weeks. Full values in the table below." });

  for (const t of ticks) {
    svg.appendChild(svgEl("line", { x1: m.left, x2: width - m.right, y1: y(t), y2: y(t) }, t === 0 ? "baseline-rule" : "gridline"));
    const label = svgEl("text", { x: m.left - 8, y: y(t) + 4, "text-anchor": "end" }, "axis-text");
    label.textContent = compact(t);
    svg.appendChild(label);
  }

  const tooltip = el("div", "chart-tooltip");
  tooltip.hidden = true;

  const showTooltip = (week, cx) => {
    tooltip.innerHTML = "";
    tooltip.appendChild(el("div", "tt-title", `${shortDate(week.start)} – ${shortDate(week.end)}`));
    for (const [label, value, color] of [
      ["Emails", week.emails, "var(--series-email)"],
      ["Calls", week.calls, "var(--series-call)"],
      ["Total", week.emails + week.calls, null],
    ]) {
      const row = el("div", "tt-row");
      const key = el("span", "tt-key");
      key.style.background = color || "transparent";
      row.append(key, el("span", "tt-value", `${value}`), el("span", "tt-label", label));
      tooltip.appendChild(row);
    }
    tooltip.hidden = false;
    const left = Math.min(Math.max(cx - tooltip.offsetWidth / 2, 0), width - tooltip.offsetWidth);
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${Math.max(m.top - 10, 0)}px`;
  };
  const hideTooltip = () => { tooltip.hidden = true; };

  const labelEvery = band < 46 ? 2 : 1;
  weekly.forEach((week, i) => {
    const cx = m.left + band * i + band / 2;
    const x = cx - barW / 2;
    const group = svgEl("g", { tabindex: "0", role: "img",
      "aria-label": `Week of ${shortDate(week.start)}: ${week.emails} emails, ${week.calls} calls` }, "col");
    group.appendChild(svgEl("rect", { x: m.left + band * i, y: m.top, width: band, height: plotH, rx: 4 }, "hit"));

    // Emails at the bottom, calls stacked on top; the top-most non-empty
    // segment gets the rounded data end, and a 2px surface gap separates them.
    const segments = [["bar-email", week.emails], ["bar-call", week.calls]].filter(([, v]) => v > 0);
    let base = y(0);
    segments.forEach(([cls, v], idx) => {
      let h = (v / yMax) * plotH;
      if (idx > 0) { base -= GAP; h = Math.max(h - GAP, 1); }
      const top = base - h;
      const isTop = idx === segments.length - 1;
      group.appendChild(isTop
        ? svgEl("path", { d: topRoundedBar(x, top, barW, h) }, cls)
        : svgEl("rect", { x, y: top, width: barW, height: h }, cls));
      base = top;
    });

    if (i % labelEvery === (weekly.length - 1) % labelEvery) {
      const label = svgEl("text", { x: cx, y: height - 8, "text-anchor": "middle" }, "axis-text");
      label.textContent = shortDate(week.start);
      group.appendChild(label);
    }
    // Direct label on the latest week only -- the table carries the rest.
    if (i === weekly.length - 1 && totals[i] > 0) {
      const value = svgEl("text", { x: cx, y: y(totals[i]) - 6, "text-anchor": "middle" }, "value-text");
      value.textContent = `${totals[i]}`;
      group.appendChild(value);
    }

    group.addEventListener("pointerenter", () => showTooltip(week, cx));
    group.addEventListener("pointerleave", hideTooltip);
    group.addEventListener("focus", () => showTooltip(week, cx));
    group.addEventListener("blur", hideTooltip);
    svg.appendChild(group);
  });

  wrap.append(svg, tooltip);

  const table = document.getElementById("report-table-body");
  table.innerHTML = "";
  for (const week of weekly) {
    const row = el("tr");
    row.append(
      el("td", "", `${shortDate(week.start)} – ${shortDate(week.end)}`),
      el("td", "num", `${week.emails}`),
      el("td", "num", `${week.calls}`),
      el("td", "num", `${week.emails + week.calls}`),
    );
    table.appendChild(row);
  }
}

async function loadReport() {
  const container = document.getElementById("tab-report");
  container.style.opacity = reportData ? "0.6" : "1"; // keep the old frame while refetching
  try {
    reportData = await api("/report?days=7&weeks=8");
    const { period } = reportData;
    document.getElementById("report-period").textContent =
      `${shortDate(period.start)} – ${shortDate(period.end)}`;
    renderBeforeAfter(reportData.baseline);
    renderTiles(reportData);
    renderTrendChart(reportData.weekly);
  } catch (err) {
    showError(`Failed to load report: ${err.message}`);
  } finally {
    container.style.opacity = "1";
  }
}

async function loadReportSettings() {
  try {
    const settings = await api("/settings");
    const num = (v) => (v === null || v === undefined ? "" : v);
    document.getElementById("baseline-missed").value = num(settings.baseline_missed_calls_per_week);
    document.getElementById("baseline-reply").value = num(settings.baseline_email_reply_hours);
    document.getElementById("report-email").value = settings.weekly_report_email || "";
    const tzInput = document.getElementById("report-timezone");
    const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if ((!settings.timezone || settings.timezone === "UTC") && browserTz && browserTz !== "UTC") {
      tzInput.value = browserTz;
      const status = document.getElementById("report-settings-status");
      status.className = "save-status info";
      status.textContent = "Timezone filled in from your browser -- Save to keep it";
    } else {
      tzInput.value = settings.timezone || "UTC";
    }
  } catch (err) {
    showError(`Failed to load report settings: ${err.message}`);
  }
}

function flashReportStatus(text) {
  const status = document.getElementById("report-settings-status");
  status.className = "save-status";
  status.textContent = text;
  setTimeout(() => { if (status.textContent === text) status.textContent = ""; }, 4000);
}

document.getElementById("report-settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const numberOrNull = (id) => {
    const raw = document.getElementById(id).value.trim();
    return raw === "" ? null : Number(raw);
  };
  try {
    await api("/settings", {
      method: "PUT",
      body: JSON.stringify({
        baseline_missed_calls_per_week: numberOrNull("baseline-missed"),
        baseline_email_reply_hours: numberOrNull("baseline-reply"),
        weekly_report_email: document.getElementById("report-email").value.trim(),
        timezone: document.getElementById("report-timezone").value.trim() || "UTC",
      }),
    });
    flashReportStatus("Saved");
    loadReport();
  } catch (err) {
    showError(`Couldn't save: ${err.message}`);
  }
});

document.getElementById("send-report-now").addEventListener("click", async () => {
  try {
    const result = await api("/report/send", { method: "POST" });
    flashReportStatus(`Sent to ${result.sent_to}`);
  } catch (err) {
    showError(`Couldn't send the report: ${err.message}`);
  }
});

document.getElementById("refresh-report").addEventListener("click", loadReport);

let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (reportData && document.getElementById("tab-report").classList.contains("active")) {
      renderTrendChart(reportData.weekly);
    }
  }, 150);
});

// --- Knowledge base --------------------------------------------------------

async function loadKb() {
  try {
    const { entries } = await api("/kb");
    renderKb(entries);
  } catch (err) {
    showError(`Failed to load knowledge base: ${err.message}`);
  }
}

let editingKbId = null;

function renderKb(entries) {
  const body = document.getElementById("kb-body");
  const empty = document.getElementById("kb-empty");
  body.innerHTML = "";
  empty.style.display = entries.length ? "none" : "block";

  for (const entry of entries) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(entry.question)}</td>
      <td style="white-space:normal; max-width:320px;">${escapeHtml(entry.answer)}</td>
      <td>${escapeHtml(entry.category)}</td>
      <td style="white-space:nowrap;">
        <button class="btn-secondary kb-edit-btn" data-id="${entry.id}">Edit</button>
        <button class="btn-delete kb-delete-btn" data-id="${entry.id}">Delete</button>
      </td>
    `;
    body.appendChild(row);
  }

  body.querySelectorAll(".kb-edit-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const entry = entries.find((e) => String(e.id) === btn.dataset.id);
      if (!entry) return;
      editingKbId = entry.id;
      document.getElementById("kb-question").value = entry.question;
      document.getElementById("kb-answer").value = entry.answer;
      document.getElementById("kb-category").value = entry.category;
      document.getElementById("kb-form-submit").textContent = "Save changes";
      document.getElementById("kb-form-cancel").style.display = "inline-block";
      document.getElementById("kb-question").focus();
    });
  });
  body.querySelectorAll(".kb-delete-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api(`/kb/${btn.dataset.id}`, { method: "DELETE" });
      if (editingKbId === Number(btn.dataset.id)) resetKbForm();
      loadKb();
    });
  });
}

function resetKbForm() {
  editingKbId = null;
  document.getElementById("kb-form").reset();
  document.getElementById("kb-form-submit").textContent = "Add entry";
  document.getElementById("kb-form-cancel").style.display = "none";
}

document.getElementById("kb-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = document.getElementById("kb-question").value;
  const answer = document.getElementById("kb-answer").value;
  const category = document.getElementById("kb-category").value || "general";
  try {
    if (editingKbId) {
      await api(`/kb/${editingKbId}`, { method: "PUT", body: JSON.stringify({ question, answer, category }) });
    } else {
      await api("/kb", { method: "POST", body: JSON.stringify({ question, answer, category }) });
    }
    resetKbForm();
    loadKb();
  } catch (err) {
    showError(`Failed to save entry: ${err.message}`);
  }
});

document.getElementById("kb-form-cancel").addEventListener("click", resetKbForm);

// --- Settings --------------------------------------------------------------

async function loadSettings() {
  try {
    const settings = await api("/settings");
    document.getElementById("set-name").value = settings.business_name || "";
    document.getElementById("set-hours").value = settings.business_hours || "";
    document.getElementById("set-greeting").value = settings.greeting_message || "";
    document.getElementById("set-voice-greeting").value = settings.voice_greeting || "";
    document.getElementById("set-ai-disclosure").checked = Boolean(settings.ai_disclosure);
    renderAutoSendToggles(settings.auto_send || {});
  } catch (err) {
    showError(`Failed to load settings: ${err.message}`);
  }
}

function renderAutoSendToggles(autoSend) {
  const container = document.getElementById("auto-send-toggles");
  container.innerHTML = "";
  for (const category of Object.keys(autoSend)) {
    const row = document.createElement("div");
    row.className = "toggle-row";
    row.innerHTML = `
      <span>${badge(category)}</span>
      <label>
        <input type="checkbox" class="auto-send-toggle" data-category="${category}" ${autoSend[category] ? "checked" : ""} />
        Auto-send
      </label>
    `;
    container.appendChild(row);
  }
  container.querySelectorAll(".auto-send-toggle").forEach((toggle) => {
    toggle.addEventListener("change", async () => {
      const current = await api("/settings");
      const autoSendNow = { ...current.auto_send, [toggle.dataset.category]: toggle.checked };
      try {
        await api("/settings", { method: "PUT", body: JSON.stringify({ auto_send: autoSendNow }) });
      } catch (err) {
        showError(`Failed to save: ${err.message}`);
      }
    });
  });
}

document.getElementById("settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/settings", {
      method: "PUT",
      body: JSON.stringify({
        business_name: document.getElementById("set-name").value,
        business_hours: document.getElementById("set-hours").value,
        greeting_message: document.getElementById("set-greeting").value,
        voice_greeting: document.getElementById("set-voice-greeting").value,
        ai_disclosure: document.getElementById("set-ai-disclosure").checked,
      }),
    });
    const saved = document.getElementById("settings-saved");
    saved.textContent = "Saved";
    setTimeout(() => { saved.textContent = ""; }, 2500);
  } catch (err) {
    showError(`Failed to save settings: ${err.message}`);
  }
});

async function loadIntegrationStatus() {
  try {
    const health = await api("/health");
    const container = document.getElementById("integration-status");
    const line = (label, ok) => `<div>${ok ? "✅" : "⬜"} ${label}</div>`;
    const warn = (label) => `<div style="color:var(--danger); font-weight:600;">⚠️ ${label}</div>`;

    let html =
      line("AI drafting (ANTHROPIC_API_KEY)", health.ai_agent_enabled) +
      line("Outbound email (SMTP)", health.smtp_configured) +
      line("Inbound email polling (IMAP)", health.imap_configured) +
      line("Inbound email webhook secret (INBOUND_EMAIL_SECRET)", health.inbound_email_secret_configured) +
      line("Phone / SMS (Twilio)", health.twilio_configured) +
      line("Dashboard auth", health.auth_enabled);

    if (health.auth_misconfigured) {
      html += warn("Only one of APP_USERNAME/APP_PASSWORD is set -- auth is OFF until both are set.");
    }

    if (health.imap_last_poll && health.imap_last_poll.at) {
      const poll = health.imap_last_poll;
      const when = new Date(poll.at).toLocaleString();
      html += poll.success
        ? `<div>✅ Last mailbox poll: ${escapeHtml(when)} (${poll.processed} processed)</div>`
        : warn(`Last mailbox poll failed at ${escapeHtml(when)}: ${escapeHtml(poll.error || "unknown error")}`);
    }

    container.innerHTML = html;
  } catch (err) {
    showError(`Failed to load integration status: ${err.message}`);
  }
}

// --- Init --------------------------------------------------------------

loadEmails();
loadCalls();
loadContacts();
loadKb();
loadSettings();
loadIntegrationStatus();
