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

function distribution(card) {
  const dist = card.distribution;
  if (!dist || !Object.keys(dist).length) return null;
  const values = Object.values(dist).filter((v) => typeof v === "number");
  const total = values.reduce((a, b) => a + b, 0);

  const wrap = el("div", "dist");
  for (const [key, value] of Object.entries(dist)) {
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
    block.className = "trigger unknown";
    block.appendChild(el("span", "label", "Cause"));
    block.appendChild(document.createTextNode(
      "Not established. Chat reacted to something the system could not tie to a stream moment."));
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
   The hero argument, played with REAL data from this run: the messages a verified card actually
   cites, the message it froze on, and the cards the system actually produced.

   Three things this deliberately is not. It is not a synthetic loop — every string comes from
   `events` or from a card the gate verified. It has no randomness — timing is index-derived, so
   two plays are identical and a camera can be pointed at it. And it never runs on an empty run:
   with no verified card there is nothing to argue, so the stage stays hidden rather than
   animating a claim the system did not make. */
const STAGE_STEP_MS = 260;      /* between messages */
const STAGE_FREEZE_MS = 1500;   /* the hold on one meaningless message */
const STAGE_COLLAPSE_MS = 700;

/* The message that best makes the point is the shortest one a card is standing on: alone it is
   noise, and the card says what caused it. Shortest, then earliest id, so the pick is stable. */
function frozenPick(texts) {
  let best = 0;
  for (let i = 1; i < texts.length; i += 1) {
    if (texts[i].text.length < texts[best].text.length) best = i;
  }
  return best;
}

function stageData(result, events) {
  const verified = [];
  for (const window of result.windows || []) {
    for (const card of window.verified || []) {
      if (card.type !== "none" && (card.evidence || []).length) verified.push(card);
    }
  }
  if (!verified.length) return null;

  const cards = verified.slice(0, 3);
  const seen = new Set();
  const texts = [];
  for (const card of cards) {
    for (const id of card.evidence || []) {
      const event = events[id];
      if (event && event.text && !seen.has(id)) {
        seen.add(id);
        texts.push({ id: id, text: event.text });
      }
    }
  }
  if (texts.length < 2) return null;
  return { cards: cards, texts: texts.slice(0, 12), trigger: cards[0].trigger || {} };
}

let stageTimers = [];
function stageStop() {
  for (const id of stageTimers) clearTimeout(id);
  stageTimers = [];
}

function stagePlay(data) {
  stageStop();
  const stream = document.getElementById("stage-stream");
  const cards = document.getElementById("stage-cards");
  const trigger = document.getElementById("stage-trigger");
  const label = document.getElementById("stage-label");

  while (stream.firstChild) stream.removeChild(stream.firstChild);
  while (cards.firstChild) cards.removeChild(cards.firstChild);
  cards.classList.remove("in");
  trigger.classList.remove("in");
  label.textContent = "chat, as it arrives";

  const freeze = frozenPick(data.texts);
  const rows = data.texts.map((entry) => {
    const li = el("li", null, entry.text);
    stream.appendChild(li);
    return li;
  });

  /* accelerating: each message lands a little sooner than the last */
  let at = 0;
  rows.forEach((li, i) => {
    at += Math.max(90, STAGE_STEP_MS - i * 14);
    stageTimers.push(setTimeout(() => li.classList.add("in"), at));
  });

  stageTimers.push(setTimeout(() => {
    rows[freeze].classList.add("frozen");
    label.textContent = "meaningless on its own";
  }, at + 220));

  const collapseAt = at + 220 + STAGE_FREEZE_MS;
  stageTimers.push(setTimeout(() => {
    for (const li of rows) li.classList.add("out");
    label.textContent = "grounded in one stream moment";
  }, collapseAt));

  stageTimers.push(setTimeout(() => {
    for (const card of data.cards) {
      const box = el("div", "mini");
      box.appendChild(el("div", "mini-type", card.type));
      box.appendChild(el("div", "mini-title", card.title || ""));
      cards.appendChild(box);
    }
    cards.classList.add("in");
    const quote = (data.trigger.quote || "").trim();
    const id = data.trigger.event_id;
    trigger.textContent = quote
      ? `caused by ${data.trigger.kind || "event"} ${id} — “${quote}”`
      : `cause recorded as ${id || UNKNOWN}`;
    trigger.classList.add("in");
  }, collapseAt + STAGE_COLLAPSE_MS));
}

function renderStage(result, events) {
  const data = stageData(result, events);
  if (!data) return;                       /* nothing verified: no argument to play */
  document.getElementById("stage").hidden = false;

  const button = document.getElementById("stage-toggle");
  button.addEventListener("click", () => stagePlay(data));

  const still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!still) stagePlay(data);
  else {
    /* Reduced motion: show the end state, which is the part that carries the meaning. */
    stageTimers.push(setTimeout(() => stagePlay(data), 0));
    stageStop();
  }
}

function render(data) {
  const { meta, result, events, evaluation } = data;
  const startMs = result.span_ms ? result.span_ms[0] : (meta.start_ms || 0);

  document.getElementById("mode-badge").textContent = result.mode;
  document.getElementById("fixture-line").textContent =
    `${result.fixture_id} · ${result.counts.windows} windows · ${result.counts.verified} verified`;
  document.getElementById("footer-line").textContent =
    `Served from ${result.fixture} — nothing on this page is generated. Reproduce with ` +
    `make replay FIXTURE=${result.fixture}`;
  renderDebug(data);
  renderHero(result, evaluation);
  renderStage(result, events);
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
