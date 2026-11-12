// app.js
// ------------------------------------------------------------------
// 1. Load today's edition (the JSON "data contract").
// 2. Show Unread or Read stories.
// 3. Detect when a story has really been read.
// ------------------------------------------------------------------

const EDITION_URL = "../data/editions/latest.json";

// Read-detection rule: a card counts as read when at least 60% of it
// stays on screen for 10 seconds while the tab is visible.
const READ_VISIBLE_SHARE = 0.6;
const READ_DWELL_MS = 10000; // milliseconds: 10000 = 10 seconds

const PERSONA_LABELS = { exec: "CEO", marketing: "Marketing", product: "Product", tech: "Tech" };
const CATEGORY_LABELS = {
  product_launch: "Product launch", ai_model: "AI model", pricing: "Pricing", partnership: "Partnership",
  funding: "Funding", leadership: "Leadership", regulation: "Regulation", other: "Other"
};
const CATEGORY_COLORS = {
  product_launch: ["#0e4d64", "#1f8a9e"], ai_model: ["#3a3f8f", "#6c74c9"], pricing: ["#7a3b1d", "#c26a3c"],
  partnership: ["#25503a", "#4f9a6c"], funding: ["#5c2a5e", "#a45aa0"], leadership: ["#4a4a4a", "#7d7d7d"],
  regulation: ["#8a2c3b", "#d4566a"], other: ["#33404c", "#66798a"]
};

const state = {
  edition: null,
  readIds: new Set(),
  view: "unread",              // "unread" or "read"
  persona: "product",
  openSources: new Set(),      // story IDs whose full source list is expanded
  readThisVisit: new Set()     // read during this visit: they stay on the Unread page until you switch tabs
};

try { state.persona = localStorage.getItem("mtn-persona") || state.persona; } catch (e) {}

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const niceDate = (d) => new Date(d + "T12:00:00Z").toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

// ---------- Which stories go on the current page ----------
function visibleStories() {
  const all = [...state.edition.stories].sort((a, b) => a.rank - b.rank);
  if (state.view === "read") return all.filter((s) => state.readIds.has(s.id));
  // Unread page: unread stories, plus ones you read during this visit,
  // so cards don't jump away while you are scrolling.
  return all.filter((s) => !state.readIds.has(s.id) || state.readThisVisit.has(s.id));
}

// ---------- Rendering ----------
function cardHtml(s) {
  const [c1, c2] = CATEGORY_COLORS[s.category] || CATEGORY_COLORS.other;
  const primary = s.sources.find((x) => x.official) || s.sources[0];
  const others = s.sources.length - 1;
  const open = state.openSources.has(s.id);
  const isRead = state.readIds.has(s.id);

  return `
  <article class="story ${isRead ? "is-read" : ""}" data-id="${esc(s.id)}">
    <div class="visual" style="background: linear-gradient(140deg, ${c1}, ${c2})">
      ${s.image_url ? `<img src="${esc(s.image_url)}" alt="">` : ""}
      <span class="cat">${esc(CATEGORY_LABELS[s.category] || s.category)}</span>
      <span class="rank">#${s.rank}</span>
      <span class="cname">${esc(s.company)}</span>
    </div>
    <div class="text">
      <h3>${esc(s.headline)}</h3>
      <div class="meta">
        <span>${s.sources.length} source${s.sources.length === 1 ? "" : "s"}</span>
        ${s.is_update ? `<span class="update">Update to an earlier story</span>` : ""}
        ${isRead ? `<span class="read-tag">✓ Read</span>` : ""}
      </div>
      <div class="what"><div class="label">What happened</div><p>${esc(s.what)}</p></div>
      <div class="why"><div class="label">Why it matters for ${PERSONA_LABELS[state.persona]}</div><p>${esc(s.why[state.persona])}</p></div>
      <div class="sources">
        <a class="primary" href="${esc(primary.url)}" target="_blank" rel="noopener">Read more at ${esc(primary.name)} →</a>
        ${others > 0 ? `<button class="link-btn" data-sources="${esc(s.id)}" aria-expanded="${open}">${open ? "Hide sources" : `+${others} more source${others === 1 ? "" : "s"}`}</button>` : ""}
        ${isRead ? `<button class="link-btn" data-unread="${esc(s.id)}">Mark as unread</button>` : ""}
        ${open ? `<ul class="src-list">${s.sources.map((x) => `
          <li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a>
          <span class="src-kind ${x.official ? "official" : ""}">${x.official ? "official" : "coverage"}</span></li>`).join("")}</ul>` : ""}
      </div>
    </div>
  </article>`;
}

function render() {
  const stories = visibleStories();
  const total = state.edition.stories.length;
  const readCount = state.edition.stories.filter((s) => state.readIds.has(s.id)).length;

  $("#countUnread").textContent = total - readCount;
  $("#countRead").textContent = readCount;
  document.querySelectorAll(".tab").forEach((t) => t.setAttribute("aria-selected", t.dataset.view === state.view));
  document.querySelectorAll(".persona button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.p === state.persona));

  if (stories.length === 0) {
    $("#feed").innerHTML = state.view === "unread"
      ? `<p class="empty">You're all caught up: you've read all ${total} stories today.</p>`
      : `<p class="empty">Nothing read yet. Scroll through the Unread page and stories appear here.</p>`;
  } else {
    $("#feed").innerHTML = stories.map(cardHtml).join("");
  }
  watchCards();
}

// ---------- Read detection ----------
const timers = new Map(); // story ID -> timer waiting to mark it read

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    const id = entry.target.dataset.id;
    if (entry.intersectionRatio >= READ_VISIBLE_SHARE) {
      if (!timers.has(id) && !state.readIds.has(id)) {
        timers.set(id, setTimeout(() => markRead(id), READ_DWELL_MS));
      }
    } else {
      clearTimeout(timers.get(id)); // scrolled away too soon: not read
      timers.delete(id);
    }
  });
}, { threshold: [0, READ_VISIBLE_SHARE, 1] });

function watchCards() {
  observer.disconnect();
  timers.forEach(clearTimeout);
  timers.clear();
  if (state.view !== "unread") return; // only the Unread page marks things as read
  document.querySelectorAll(".story").forEach((card) => observer.observe(card));
}

async function markRead(id) {
  timers.delete(id);
  if (document.visibilityState !== "visible") return; // tab in background: don't count it
  await ReadStore.markRead(id);
  state.readIds.add(id);
  state.readThisVisit.add(id);
  // Update counts and this one card only, so the page doesn't jump while scrolling.
  const card = document.querySelector(`.story[data-id="${CSS.escape(id)}"]`);
  if (card) card.outerHTML = cardHtml(state.edition.stories.find((s) => s.id === id));
  const total = state.edition.stories.length;
  $("#countUnread").textContent = total - state.readIds.size;
  $("#countRead").textContent = state.readIds.size;
}

// ---------- Clicks ----------
document.addEventListener("click", async (e) => {
  const tab = e.target.closest(".tab");
  if (tab) {
    state.view = tab.dataset.view;
    state.readThisVisit.clear(); // switching pages tidies up the Unread list
    render();
    window.scrollTo({ top: 0 });
    return;
  }
  const p = e.target.closest(".persona button");
  if (p) {
    state.persona = p.dataset.p;
    try { localStorage.setItem("mtn-persona", state.persona); } catch (err) {}
    render();
    return;
  }
  const src = e.target.closest("[data-sources]");
  if (src) {
    const id = src.dataset.sources;
    state.openSources.has(id) ? state.openSources.delete(id) : state.openSources.add(id);
    render();
    return;
  }
  const un = e.target.closest("[data-unread]");
  if (un) {
    await ReadStore.markUnread(un.dataset.unread);
    state.readIds.delete(un.dataset.unread);
    state.readThisVisit.delete(un.dataset.unread);
    render();
    return;
  }
  if (e.target.closest("#resetBtn")) {
    await ReadStore.clear();
    state.readIds.clear();
    state.readThisVisit.clear();
    state.view = "unread";
    render();
  }
});

// ---------- Start ----------
async function start() {
  try {
    const res = await fetch(EDITION_URL, { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    state.edition = await res.json();
  } catch (err) {
    $("#edTitle").textContent = "Edition could not be loaded";
    $("#feed").innerHTML = `<p class="empty">Error: ${esc(err.message)}. Open the page through Live Server (http://…), not by double-clicking the file.</p>`;
    return;
  }

  // Only remember read stories that exist in today's edition.
  const todaysIds = new Set(state.edition.stories.map((s) => s.id));
  const saved = await ReadStore.getReadIds();
  state.readIds = new Set([...saved].filter((id) => todaysIds.has(id)));

  $("#brandDate").textContent = niceDate(state.edition.date);
  $("#edTitle").textContent = niceDate(state.edition.date);
  $("#edMeta").textContent = `${state.edition.stories.length} stories from ${state.edition.stats?.items_collected ?? "?"} articles · prompt ${state.edition.prompt_version}`;
  if (state.edition.is_sample) {
    const n = $("#notice");
    n.hidden = false;
    n.textContent = "Sample edition: these stories are placeholders for testing the layout, not real news.";
  }
  render();
}

start();
