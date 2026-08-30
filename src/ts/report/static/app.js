/* Renders /api/replay. Every value on screen comes from the response; there is no generator,
   no placeholder series and no sample data in this file. If the run produced nothing, the page
   says so rather than drawing something. */
"use strict";

const UNKNOWN = "unknown";

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;   // textContent, never innerHTML: chat is untrusted data
  return node;
};

const timecode = (tsMs, startMs) => {
  const s = Math.max(0, Math.floor((tsMs - startMs) / 1000));
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
};

/* verified / abstained / rejected.
   A rejected card is not called "uncertain": its evidence did not check out, and softening that
   would hide the one failure this product exists to surface. */
const statusOf = (card) => {
  if (!(card.gate && card.gate.ok)) return "rejected";
  const triggerId = (card.trigger || {}).event_id;
  return (!triggerId || triggerId === UNKNOWN) ? "abstained" : "verified";
};

const pill = (label, className) => {
  const node = el("span", className ? `pill ${className}` : "pill");
  if (className) node.appendChild(el("span", "dot"));
  node.appendChild(document.createTextNode(label));
  return node;
};

/* A chart needs something to compare. With one bucket, or with every bucket equal, the bars
   carry no information and the layout degrades into a column of numbers with a vertical label —
   which is what it was doing. Below two distinct non-zero buckets, print the fact as a line. */
const MIN_CHART_BUCKETS = 2;

function distribution(card) {
  const dist = card.distribution;
  if (!dist || typeof dist !== "object" || Array.isArray(dist)) return null;
  const entries = Object.entries(dist).filter(([, v]) => typeof v === "number" && v > 0);
  if (!entries.length) return null;

  const distinct = new Set(entries.map(([, v]) => v)).size;
  if (entries.length < MIN_CHART_BUCKETS || (entries.length > 1 && distinct === 1)) {
    const line = el("p", "dist-flat");
    line.appendChild(el("span", "label", "Spread"));
    line.appendChild(document.createTextNode(
      entries.map(([k, v]) => `${k} · ${v}`).join(", ")));
    return line;
  }

  const values = entries.map(([, v]) => v);
  const total = values.reduce((a, b) => a + b, 0);

  const wrap = el("div", "dist");
  for (const [key, value] of entries) {
    const row = el("div", "dist-row");
    row.appendChild(el("span", null, key));
    const bar = el("div", "dist-bar");
    const fill = el("span");
    fill.style.width = total ? `${(value / total) * 100}%` : "0%";
    bar.appendChild(fill);
    row.appendChild(bar);
    row.appendChild(el("span", "dist-num", total ? `${value} · ${Math.round((value / total) * 100)}%` : `${value}`));
    wrap.appendChild(row);
  }
  return wrap;
}

function trigger(card, events, startMs) {
  const t = card.trigger || {};
  const id = t.event_id;
  const block = el("p", "trigger");

  if (!id || id === UNKNOWN) {
    /* One sentence. It used to print the label with no gap ("CAUSENot established.") and the
       stage printed the kind and the id when both were the literal string "unknown". */
    block.className = "trigger unknown";
    block.appendChild(el("span", "label", "Cause"));
    block.appendChild(document.createTextNode(
      "No cause established — chat reacted to something the system could not tie to a stream moment."));
    return block;
  }

  const event = events[id];
  block.appendChild(el("span", "label",
    `Cause · ${t.kind || "event"} · ${id}${event ? ` · ${timecode(event.ts_ms, startMs)}` : ""}`));
  if (t.quote) {
    block.appendChild(el("span", "quote", `“${t.quote}”`));
  } else if (event) {
    block.appendChild(el("span", "quote", `“${event.text}”`));
  }
  return block;
}

function drawer(card, events, startMs) {
  const ids = card.evidence || [];
  const details = el("details", "drawer");

  /* An abstention has nothing to cite, and "Evidence — 0 messages" reads as a defect rather
     than as the system correctly declining to claim anything. */
  if (card.type === "none" && !ids.length) {
    details.appendChild(el("summary", null, "Nothing to verify"));
    details.appendChild(el("p", "note",
      "The system reported no audience signal in this window and cited nothing, which is what " +
      "it is supposed to do when it cannot prove anything. There is no claim here to check."));
    return details;
  }

  details.appendChild(el("summary", null,
    `Evidence — ${ids.length} message${ids.length === 1 ? "" : "s"}`));

  const list = el("ul", "evidence");
  for (const id of ids) {
    const event = events[id];
    const row = el("li");
    row.appendChild(el("code", null, id));
    if (event) {
      row.appendChild(el("code", null, timecode(event.ts_ms, startMs)));
      row.appendChild(el("span", null, `${event.author ? event.author + ": " : ""}${event.text}`));
    } else {
      row.appendChild(el("code", null, "—"));
      row.appendChild(el("span", "missing", "not in the fixture — this citation does not exist"));
    }
    list.appendChild(row);
  }
  details.appendChild(list);

  const violations = (card.gate && card.gate.violations) || [];
  if (violations.length) {
    const ul = el("ul", "violations");
    for (const v of violations) ul.appendChild(el("li", null, `${v.code} — ${v.detail}`));
    details.appendChild(ul);
  }
  return details;
}

/* The one outward action. It is a human checkpoint, so it is a button — a card that says
   "pending approval" with nothing to press is a chain that ends in a label.

   Approving renders the draft and nothing else. There is no fetch in this function and no
   endpoint behind it: the streamer copies the text into Twitch themselves, deliberately. */
function approval(card) {
  const draft = card.poll_draft;
  if (!draft) return null;

  const block = el("div", "approval");
  const button = el("button", "btn-primary", "Approve → draft poll");
  const panel = el("div", "draft");
  panel.hidden = true;

  panel.appendChild(el("p", "draft-q", draft.question));
  const list = el("ol", "draft-options");
  for (const option of draft.options) {
    list.appendChild(el("li", null,
      `${option.label} — ${option.votes} (${Math.round(option.share * 100)}%)`));
  }
  panel.appendChild(list);
  for (const warning of draft.warnings || []) {
    panel.appendChild(el("p", "draft-warning", warning));
  }
  panel.appendChild(el("p", "note",
    "Draft only. Nothing was posted and nothing can be: this page has no Twitch credentials " +
    "and makes no request. Copy it across yourself."));

  button.addEventListener("click", () => {
    panel.hidden = false;
    button.disabled = true;
    button.textContent = "Approved — draft below, nothing posted";
  });

  block.appendChild(button);
  block.appendChild(panel);
  return block;
}

function renderCard(card, events, startMs) {
  const status = statusOf(card);
  const node = el("article", "card");

  const head = el("div", "card-head");
  head.appendChild(el("h3", null, card.title || card.type));

  const badges = el("div", "badges");
  badges.appendChild(pill((card.type || "").replace(/_/g, " ")));
  if (typeof card.confidence === "number") badges.appendChild(pill(`conf ${card.confidence}`));
  badges.appendChild(pill(status, status));
  head.appendChild(badges);
  node.appendChild(head);

  const dist = distribution(card);
  if (dist) node.appendChild(dist);
  node.appendChild(trigger(card, events, startMs));
  node.appendChild(drawer(card, events, startMs));

  const action = approval(card);
  if (action) node.appendChild(action);

  const foot = el("p", "meta");
  foot.appendChild(document.createTextNode(`trace ${card.trace_id || "—"}`));
  if (card.action && !action) {
    foot.appendChild(document.createTextNode(
      ` · action ${card.action.kind} (${card.action.state.replace(/_/g, " ")})`));
  }
  node.appendChild(foot);
  return node;
}

function renderDebug(data) {
  const { meta, result } = data;
  const dl = document.getElementById("debug-body");
  const rows = [
    ["mode", result.mode],
    ["fixture", result.fixture_id],
    ["windows", result.counts.windows],
    ["window size", `${result.window_size_ms} ms`],
    ["verified", result.counts.verified],
    ["rejected", result.counts.rejected],
    ["cache hits", result.cache.hits],
    ["cache misses", result.cache.misses],
    ["latency", "not measured in replay"],
    ["cost", "0.00 — cached responses"],
    ["channel", meta.channel || "—"],
  ];
  for (const [term, value] of rows) {
    dl.appendChild(el("dt", null, term));
    dl.appendChild(el("dd", null, String(value)));
  }
}


/* ------------------------------------------------------------------ editorial sections
   The hero counters and the scores table are read from what `make eval` wrote, never computed
   here: evals/scorer.py owns every published metric, and a rate recomputed in the browser would
   eventually disagree with the one in evidence/report.md. When the eval has not been run the
   section stays hidden rather than rendering zeros that read like a measured result. */
const rate = (v) => (typeof v === "number" ? v.toFixed(3) : "—");

function stat(dl, label, value) {
  const wrap = el("div");
  wrap.appendChild(el("dt", null, label));
  wrap.appendChild(el("dd", null, value));
  dl.appendChild(wrap);
}

function renderHero(result, evaluation) {
  const dl = document.getElementById("hero-stats");
  const counts = result.counts || {};
  stat(dl, "windows analysed", String(counts.windows != null ? counts.windows : "—"));
  stat(dl, "cards verified", String(counts.verified != null ? counts.verified : "—"));
  stat(dl, "rejected by the gate", String(counts.rejected != null ? counts.rejected : "—"));

  const cache = result.cache || {};
  if (cache.misses === 0) stat(dl, "api calls this run", "0");

  const note = document.getElementById("hero-note");
  if (evaluation && evaluation.systems) {
    const cases = (evaluation.systems.agent || {}).cases;
    note.textContent =
      `Everything below is served from a recorded run and reproduces from the committed cache ` +
      `with no API keys. The comparison further down covers ${cases} frozen cases.`;
  } else {
    note.textContent =
      "Everything below is served from a recorded run. Run `make eval` to populate the measured " +
      "comparison — it is hidden rather than shown empty.";
  }
}

/* Rows are ordered agent, baseline, then the diagnostic, so the comparison reads in the order it
   is argued. The ablation is dimmed because it is not the headline baseline. */
const SYSTEM_ORDER = ["agent", "baseline", "ablation_chat_only"];
const SYSTEM_LABEL = {
  agent: "agent",
  baseline: "baseline — one prompt, same events",
  ablation_chat_only: "ablation — chat only, diagnostic",
};

function renderScores(evaluation) {
  if (!evaluation || !evaluation.systems) return;
  const body = document.getElementById("scores-body");
  let rows = 0;
  for (const name of SYSTEM_ORDER) {
    const agg = evaluation.systems[name];
    if (!agg) continue;
    const tr = el("tr", name === "agent" ? "is-agent"
                      : (name === "ablation_chat_only" ? "is-diagnostic" : null));
    const cells = [
      SYSTEM_LABEL[name] || name,
      String(agg.cards),
      rate(agg.trigger_accuracy),
      rate(agg.unmatched_rate),
      rate(agg.unsupported_rate),
      rate(agg.signal_recall),
    ];
    for (const value of cells) tr.appendChild(el("td", null, value));
    body.appendChild(tr);
    rows += 1;
  }
  if (rows) document.getElementById("measured").hidden = false;
}


/* ------------------------------------------------------------------ the stage
   The hero argument, played with REAL data from a recorded run, pinned server-side to the window
   where the argument is provable: nobody speaking, chat guessing at an on-screen word game, the
   cause visible only in the frame.

   It shows ONE card, not three. It used to show three reading "Chat mention of X" over the line
   "caused by unknown unknown" — echoes under a headline about causation, which disproved the
   headline. One card that names its cause is worth more than three that do not, and if the
   server finds none the stage does not render at all.

   No randomness: timing is index-derived, so two plays are identical and it can be filmed. */
const STAGE_STEP_MS = 240;
const STAGE_FREEZE_MS = 1700;
const STAGE_COLLAPSE_MS = 640;

let stageTimers = [];
function stageStop() {
  for (const id of stageTimers) clearTimeout(id);
  stageTimers = [];
}

function stagePlay(hero) {
  stageStop();
  const stream = document.getElementById("stage-stream");
  const holder = document.getElementById("stage-cards");
  const caption = document.getElementById("stage-trigger");
  const label = document.getElementById("stage-label");

  while (stream.firstChild) stream.removeChild(stream.firstChild);
  while (holder.firstChild) holder.removeChild(holder.firstChild);
  holder.classList.remove("in");
  caption.classList.remove("in");
  label.textContent = "chat, as it arrives — no one is speaking";

  const rows = hero.stream.map((entry) => {
    const li = el("li", null, entry.text);
    if (entry.cited) li.dataset.cited = "1";
    stream.appendChild(li);
    return li;
  });
  let freeze = rows.findIndex((li) => li.dataset.cited === "1");
  if (freeze < 0) freeze = rows.length - 1;

  let at = 0;
  rows.forEach((li, i) => {
    at += Math.max(80, STAGE_STEP_MS - i * 12);
    stageTimers.push(setTimeout(() => li.classList.add("in"), at));
  });

  stageTimers.push(setTimeout(() => {
    rows[freeze].classList.add("frozen");
    label.textContent = "meaningless on its own";
  }, at + 200));

  const collapseAt = at + 200 + STAGE_FREEZE_MS;
  stageTimers.push(setTimeout(() => {
    for (const li of rows) li.classList.add("out");
    label.textContent = "the cause was on screen";
  }, collapseAt));

  stageTimers.push(setTimeout(() => {
    const card = hero.card;
    const trigger = card.trigger || {};
    const box = el("div", "mini");
    box.appendChild(el("div", "mini-type", card.type));
    box.appendChild(el("div", "mini-title", card.title || ""));
    if (trigger.quote) box.appendChild(el("p", "mini-quote", `\u201C${trigger.quote}\u201D`));
    box.appendChild(el("div", "mini-meta",
      `${trigger.kind} \u00B7 ${trigger.id || trigger.event_id}`));
    holder.appendChild(box);
    holder.classList.add("in");

    /* Attribution, because this card came from the single-prompt baseline on this window, not
       from the agent. Presenting it unlabelled would be the quiet misrepresentation. */
    caption.textContent =
      `${hero.speech_in_window} transcript segments in this window \u2014 the cause exists only in the frame. `
      + `Card produced by ${hero.system === "agent" ? "the agent" : "the single-prompt baseline"}, `
      + `replayed from the committed cache.`;
    caption.classList.add("in");
  }, collapseAt + STAGE_COLLAPSE_MS));
}

function renderStage(hero) {
  if (!hero || !hero.card || !(hero.stream || []).length) return;
  document.getElementById("stage").hidden = false;
  document.getElementById("stage-toggle").addEventListener("click", () => stagePlay(hero));

  const still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!still) stagePlay(hero);
}

function render(data) {
  const { meta, result, events, evaluation, hero } = data;
  const startMs = result.span_ms ? result.span_ms[0] : (meta.start_ms || 0);

  document.getElementById("mode-badge").textContent = result.mode;
  document.getElementById("fixture-line").textContent =
    `${result.fixture_id} · ${result.counts.windows} windows · ${result.counts.verified} verified`;
  document.getElementById("footer-line").textContent =
    `Served from ${result.fixture} — nothing on this page is generated. Reproduce with ` +
    `make replay FIXTURE=${result.fixture}`;
  renderDebug(data);
  renderHero(result, evaluation);
  renderStage(hero);
  renderScores(evaluation);

  const verified = [], rejected = [];
  for (const window of result.windows || []) {
    for (const card of window.verified || []) verified.push(card);
    for (const card of window.rejected || []) rejected.push(card);
  }

  const rail = document.getElementById("rail");
  if (!verified.length) {
    rail.appendChild(el("p", "empty",
      "No card in this run had evidence that checked out. That is a result, not an error — it is " +
      "what the system is supposed to say when it cannot prove anything."));
  } else {
    for (const card of verified) rail.appendChild(renderCard(card, events, startMs));
  }

  if (rejected.length) {
    document.getElementById("rejected-block").hidden = false;
    const bin = document.getElementById("rejected-rail");
    for (const card of rejected) bin.appendChild(renderCard(card, events, startMs));
  }
}

function fail(message) {
  document.getElementById("headline").textContent = "Nothing to show yet";
  document.getElementById("lede").textContent = message;
  document.getElementById("fixture-line").textContent = "no replay output";
}

const toggle = document.getElementById("debug-toggle");
toggle.addEventListener("click", () => {
  const panel = document.getElementById("debug");
  panel.hidden = !panel.hidden;
  toggle.setAttribute("aria-expanded", String(!panel.hidden));
});

fetch("/api/replay")
  .then((r) => r.json().then((body) => ({ ok: r.ok, body })))
  .then(({ ok, body }) => (ok ? render(body) : fail(body.error)))
  .catch((err) => fail(String(err)));
