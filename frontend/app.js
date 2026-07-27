const $ = (sel) => document.querySelector(sel);

function el(tag, opts = {}) {
  const node = document.createElement(tag);
  if (opts.text !== undefined) node.textContent = opts.text;
  if (opts.className) node.className = opts.className;
  return node;
}

function showError(message) {
  const banner = $("#error-banner");
  banner.textContent = message;
  banner.hidden = false;
  clearTimeout(showError._timer);
  showError._timer = setTimeout(() => {
    banner.hidden = true;
  }, 6000);
}

async function fetchJSON(url, options) {
  let res;
  try {
    res = await fetch(url, options);
  } catch (e) {
    showError("Network error — is the server reachable?");
    throw e;
  }
  if (!res.ok) {
    let detail = `Request failed: ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (e) {
      // ignore, use default detail
    }
    showError(detail);
    throw new Error(detail);
  }
  return res.json();
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

async function loadHealth() {
  try {
    const health = await fetchJSON("/api/health");
    const hint = $("#data-source-hint");
    hint.textContent = `Data source: ${health.youtube_live_data ? "live YouTube API" : "estimated (set YOUTUBE_API_KEY for live data)"} | Content generation: ${health.ai_content_generation ? "Claude AI" : "template fallback (set ANTHROPIC_API_KEY for AI-written scripts)"}`;
    $("#videos-per-month").value = health.assumed_videos_per_month;
  } catch (e) {
    // non-fatal, already surfaced via showError
  }
}

async function loadNiches() {
  const videosPerMonth = parseInt($("#videos-per-month").value, 10) || 8;
  const data = await fetchJSON(`/api/niches?limit=15&videos_per_month=${videosPerMonth}`);
  const body = $("#niches-body");
  body.textContent = "";
  for (const n of data.niches) {
    const tr = document.createElement("tr");
    const cells = [
      n.keyword,
      n.category,
      n.opportunity_score,
      n.avg_views.toLocaleString(),
      n.competitor_uploads_per_month,
      `${n.trend_growth_pct}%`,
      `$${n.rpm_usd}`,
      `$${n.projected_revenue_per_video_usd}`,
      `$${n.projected_monthly_revenue_usd}`,
      n.videos_needed_for_goal,
    ];
    for (const c of cells) {
      tr.appendChild(el("td", { text: String(c) }));
    }
    const useTd = document.createElement("td");
    const useBtn = el("button", { text: "Use" });
    useBtn.addEventListener("click", () => {
      $("#content-keyword").value = n.keyword;
      $("#content-category").value = n.category;
      $("#content-keyword").scrollIntoView({ behavior: "smooth" });
    });
    useTd.appendChild(useBtn);
    tr.appendChild(useTd);
    body.appendChild(tr);
  }
}

async function pollNiches() {
  const btn = $("#poll-btn");
  btn.disabled = true;
  btn.textContent = "Polling…";
  try {
    await fetchJSON("/api/niches/poll", { method: "POST" });
    await loadNiches();
  } finally {
    btn.disabled = false;
    btn.textContent = "Poll Now";
  }
}

async function loadProgress() {
  const p = await fetchJSON("/api/progress");
  $("#progress-summary").textContent =
    `$${p.current_revenue_usd.toFixed(2)} of $${p.goal_usd.toFixed(2)} goal this month (${p.percent_to_goal}%) — ${p.videos_counted} videos tracked, $${p.remaining_usd.toFixed(2)} remaining`;
  $("#progress-bar-fill").style.width = `${p.percent_to_goal}%`;

  const gapDiv = $("#gap-suggestions");
  gapDiv.textContent = "";
  if (p.remaining_usd > 0 && p.gap_closing_suggestions.length) {
    const heading = el("strong", { text: "To close the gap:" });
    gapDiv.appendChild(heading);
    const list = document.createElement("ul");
    for (const s of p.gap_closing_suggestions) {
      const li = el("li", {
        text: s.additional_videos_needed_to_close_gap
          ? `${s.additional_videos_needed_to_close_gap} more "${s.keyword}" videos (~$${s.projected_revenue_per_video_usd}/video)`
          : `Publish more videos in "${s.keyword}"`,
      });
      list.appendChild(li);
    }
    gapDiv.appendChild(list);
  }
}

function renderTagPills(container, tags) {
  for (const tag of tags) {
    container.appendChild(el("span", { className: "tag-pill", text: tag }));
  }
}

async function handleContentSubmit(e) {
  e.preventDefault();
  const niche_keyword = $("#content-keyword").value.trim();
  const category = $("#content-category").value.trim() || "general";
  const video_topic = $("#content-topic").value.trim() || null;

  const btn = $("#generate-btn");
  btn.disabled = true;
  btn.textContent = "Generating…";

  try {
    const result = await fetchJSON("/api/content/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ niche_keyword, category, video_topic }),
    });

    const out = $("#content-result");
    out.textContent = "";

    out.appendChild(el("h3", { text: `Titles (source: ${result.source})` }));
    const titleList = document.createElement("ul");
    for (const t of result.titles) titleList.appendChild(el("li", { text: t }));
    out.appendChild(titleList);

    out.appendChild(el("h3", { text: "Description" }));
    out.appendChild(el("pre", { text: result.description }));

    out.appendChild(el("h3", { text: "Tags" }));
    const tagWrap = el("div");
    renderTagPills(tagWrap, result.tags);
    out.appendChild(tagWrap);

    out.appendChild(el("h3", { text: "Script" }));
    out.appendChild(el("pre", { text: result.script }));

    out.appendChild(el("h3", { text: "Thumbnail Text Ideas" }));
    const thumbList = document.createElement("ul");
    for (const t of result.thumbnail_text_ideas) thumbList.appendChild(el("li", { text: t }));
    out.appendChild(thumbList);

    await loadContent();
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate";
  }
}

async function loadContent() {
  const data = await fetchJSON("/api/content?limit=20");
  const body = $("#content-body");
  body.textContent = "";
  for (const c of data.content) {
    const tr = document.createElement("tr");
    tr.appendChild(el("td", { text: c.niche_keyword }));
    tr.appendChild(el("td", { text: c.video_topic }));
    tr.appendChild(el("td", { text: c.source }));

    const actionTd = document.createElement("td");
    const deleteBtn = el("button", { className: "btn-delete", text: "Delete" });
    deleteBtn.addEventListener("click", async () => {
      await fetchJSON(`/api/content/${c.id}`, { method: "DELETE" });
      await loadContent();
    });
    actionTd.appendChild(deleteBtn);
    tr.appendChild(actionTd);

    body.appendChild(tr);
  }
}

async function loadVideos() {
  const data = await fetchJSON("/api/videos");
  const body = $("#videos-body");
  body.textContent = "";
  for (const v of data.videos) {
    const tr = document.createElement("tr");
    const revenue = v.actual_revenue_usd !== null && v.actual_revenue_usd !== undefined ? v.actual_revenue_usd : v.estimated_revenue_usd;
    const cells = [v.title, v.niche_keyword || "—", v.published_at || "—", v.views.toLocaleString(), `$${Number(revenue).toFixed(2)}`];
    for (const c of cells) {
      tr.appendChild(el("td", { text: String(c) }));
    }

    const actionTd = document.createElement("td");
    const deleteBtn = el("button", { className: "btn-delete", text: "Delete" });
    deleteBtn.addEventListener("click", async () => {
      await fetchJSON(`/api/videos/${v.id}`, { method: "DELETE" });
      await Promise.all([loadVideos(), loadProgress()]);
    });
    actionTd.appendChild(deleteBtn);
    tr.appendChild(actionTd);

    body.appendChild(tr);
  }
}

async function handleVideoSubmit(e) {
  e.preventDefault();
  const title = $("#video-title").value.trim();
  const niche_keyword = $("#video-niche").value.trim() || null;
  const published_at = $("#video-published").value || todayISO();
  const views = parseInt($("#video-views").value, 10) || 0;
  const estimated_revenue_usd = parseFloat($("#video-revenue").value) || 0;

  await fetchJSON("/api/videos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, niche_keyword, published_at, views, estimated_revenue_usd }),
  });

  $("#video-form").reset();
  $("#video-published").value = todayISO();
  await Promise.all([loadVideos(), loadProgress()]);
}

async function init() {
  $("#video-published").value = todayISO();
  $("#poll-btn").addEventListener("click", pollNiches);
  $("#content-form").addEventListener("submit", handleContentSubmit);
  $("#video-form").addEventListener("submit", handleVideoSubmit);
  $("#videos-per-month").addEventListener("change", loadNiches);

  await loadHealth();
  await Promise.all([loadNiches(), loadProgress(), loadVideos(), loadContent()]);
}

init();
