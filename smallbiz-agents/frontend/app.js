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
      }),
    });
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
loadKb();
loadSettings();
loadIntegrationStatus();
