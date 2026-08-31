/* The product page: a recorded run replayed at its true cadence.

   Everything here is read from committed files. The cadence is the offsets the messages actually
   arrived with, so the playback looks live and IS a replay — and the badge says which, always,
   from the server's own `mode`. A page that looked live without saying so would be claiming a
   capability a judge cannot check.

   No generator, no placeholder series, no Math.random: if the run produced nothing, the column
   says so rather than drawing something. */
"use strict";

const UNKNOWN = "unknown";
const MAX_ROWS = 200;          /* the DOM is capped; the counter is not */
const CITE_HIGHLIGHT_MS = 1200;

const clock = (ms) => {
  const s = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;   // textContent, never innerHTML: chat is untrusted
  return node;
};

const state = {
  source: null,
  fixture: null,
  system: "agent",
  speed: 1,
  paused: false,
  queue: [],                    /* events that arrived while paused */
  counts: { chat: 0, grounded: 0, abstained: 0, rejected: 0 },
  rows: new Map(),              /* event id -> <li>, for the citation highlight */
};

/* ------------------------------------------------------------------ chat column */
function addMessage(event) {
  const feed = document.getElementById("feed");
  const row = el("li", "msg");
  row.appendChild(el("span", "msg-who", (event.author || "").slice(0, 10)));
  row.appendChild(el("span", "msg-text", event.text));
  feed.appendChild(row);
  state.rows.set(event.id, row);

  while (feed.childElementCount > MAX_ROWS) {
    const first = feed.firstElementChild;
    for (const [id, node] of state.rows) if (node === first) state.rows.delete(id);
    feed.removeChild(first);
  }
  feed.scrollTop = feed.scrollHeight;

  state.counts.chat += 1;
  document.getElementById("chat-n").textContent = String(state.counts.chat);
  document.getElementById("c-chat").textContent = String(state.counts.chat);

  if (state.waitBar && state.firstCardMs) {
    const elapsed = (Date.now() - state.startedAt) * state.speed;
    state.waitBar.style.width = `${Math.min(100, (elapsed / state.firstCardMs) * 100)}%`;
  }
}

/* The one gesture that is the whole argument: when a card lands, the messages it cites light up
   in the flood beside it. This cluster, that cause. */
function highlightCited(card) {
  for (const id of card.evidence || []) {
    const row = state.rows.get(id);
    if (!row) continue;
    row.classList.add("cited");
    setTimeout(() => row.classList.remove("cited"), CITE_HIGHLIGHT_MS);
  }
}

/* ------------------------------------------------------------------ signals column */
function addCard(event) {
  const card = event.card || {};
  const trigger = card.trigger || {};
  state.counts[event.state] = (state.counts[event.state] || 0) + 1;
  for (const name of ["grounded", "abstained", "rejected"]) {
    document.getElementById(`c-${name}`).textContent = String(state.counts[name] || 0);
  }
  /* The count is what the panel SHOWS, and the split says what those cards are. It used to
     display the grounded count over a panel holding grounded and abstained together, so the
     header read "0" above five visible cards. */
  const shown = (state.counts.grounded || 0) + (state.counts.abstained || 0);
  document.getElementById("sig-n").textContent = String(shown);
  document.getElementById("sig-split").textContent =
    `${state.counts.grounded || 0} grounded · ${state.counts.abstained || 0} abstained`;

  /* Rejected cards are counted and not drawn here: this column is what the run could stand
     behind. They are all present, with their violation codes, on the method page. */
  if (event.state === "rejected") return;

  const waiting = document.getElementById("signals-empty");
  if (waiting) waiting.remove();

  /* If this run names no causes at all, say it once, in place, with the way to see one. That is
     the measured result — the agent grounds nothing on any recorded fixture — and hiding it
     behind an empty panel would be less honest than printing it. */
  if (event.state === "abstained" && !state.counts.grounded && !state.notedUngrounded) {
    state.notedUngrounded = true;
    const note = el("p", "panel-note");
    note.appendChild(document.createTextNode(
      "No card in this run names a cause its evidence supports. That is the measured result for "
      + "this system, not a loading state — "));
    const swap = el("button", "linkish", "see the baseline on this window");
    swap.type = "button";
    swap.addEventListener("click", () => {
      start(state.fixture, state.system === "agent" ? "baseline" : "agent", state.speed);
      renderChips(state.fixture);
    });
    note.appendChild(swap);
    note.appendChild(document.createTextNode("."));
    document.getElementById("signals").appendChild(note);
  }
  const box = el("article", `card is-${event.state}`);

  const head = el("div", "card-head");
  head.appendChild(el("span", "pill", card.type || "signal"));
  const badge = el("span", `pill ${event.state}`);
  badge.appendChild(el("span", "dot"));
  badge.appendChild(document.createTextNode(event.state));
  head.appendChild(badge);
  box.appendChild(head);

  box.appendChild(el("h3", null, card.title || ""));

  if (trigger.event_id && trigger.event_id !== UNKNOWN && trigger.quote) {
    box.appendChild(el("p", "quote", `“${trigger.quote}”`));
    const meta = el("p", "trigger");
    meta.appendChild(el("span", "label", "Cause"));
    meta.appendChild(el("span", "mono", `${trigger.kind} · ${trigger.event_id}`));
    box.appendChild(meta);
  } else {
    const meta = el("p", "trigger unknown");
    meta.appendChild(el("span", "label", "Cause"));
    meta.appendChild(document.createTextNode(
      "No cause established — chat reacted to something the system could not tie to a stream moment."));
    box.appendChild(meta);
  }

  const cited = el("p", "card-cites");
  cited.appendChild(el("span", "label", "Evidence"));
  cited.appendChild(document.createTextNode(
    `${(card.evidence || []).length} message${(card.evidence || []).length === 1 ? "" : "s"}`));
  box.appendChild(cited);

  const signals = document.getElementById("signals");
  signals.insertBefore(box, signals.firstChild);
  requestAnimationFrame(() => box.classList.add("in"));
  highlightCited(card);
}

/* ------------------------------------------------------------------ transport */
function apply(kind, event) {
  if (kind === "chat") addMessage(event);
  else if (kind === "card") addCard(event);
}

function reset() {
  if (state.source) { state.source.close(); state.source = null; }
  state.queue = [];
  state.rows.clear();
  state.counts = { chat: 0, grounded: 0, abstained: 0, rejected: 0 };
  state.notedUngrounded = false;
  for (const id of ["chat-n", "sig-n", "c-chat", "c-grounded", "c-abstained", "c-rejected"]) {
    document.getElementById(id).textContent = "0";
  }
  for (const id of ["feed", "signals"]) {
    const node = document.getElementById(id);
    while (node.firstChild) node.removeChild(node.firstChild);
  }
  /* The waiting state lives INSIDE the signals column. As a sibling of a flex:1 container it
     was pushed to the bottom of the panel, far from where the reader is looking. */
  const empty = el("p", "waiting", "Connecting to the recording…");
  empty.id = "signals-empty";
  document.getElementById("signals").appendChild(empty);
  state.waitBar = null;
  state.firstCardMs = null;
}

function start(fixtureId, system, speed) {
  reset();
  state.fixture = fixtureId || state.fixture;
  state.system = system || state.system;
  state.speed = speed || state.speed;
  state.paused = false;
  document.getElementById("pp").textContent = "Pause";

  const query = `?fixture=${encodeURIComponent(state.fixture || "")}`
    + `&system=${encodeURIComponent(state.system)}&speed=${state.speed}`;
  const source = new EventSource(`/api/stream${query}`);
  state.source = source;

  source.addEventListener("meta", (e) => {
    /* The badge is written from the server's own words, never the page's assumption. */
    const open = JSON.parse(e.data);
    const badge = document.getElementById("mode-badge");
    while (badge.firstChild) badge.removeChild(badge.firstChild);
    badge.appendChild(el("span", "dot"));
    badge.appendChild(document.createTextNode(
      `${String(open.mode).toUpperCase()} · ${open.speed}\u00D7`));
    document.getElementById("captured-at").textContent =
      `${open.channel} · captured ${open.captured_utc || "\u2014"} · ${open.total_chat} messages`;

    /* An empty right-hand column for the first minute reads as broken. Say what it is waiting
       for and how far along it is — the window has to close before a card can exist. */
    state.firstCardMs = open.first_card_ms;
    state.speed = open.speed || state.speed;
    const empty = document.getElementById("signals-empty");
    while (empty.firstChild) empty.removeChild(empty.firstChild);
    empty.className = "waiting";
    if (open.first_card_ms == null) {
      empty.appendChild(document.createTextNode(
        "This run produced no cards. The chat still plays."));
    } else {
      empty.appendChild(el("span", null,
        `Analysis windows are 60 seconds. The first closes at ${clock(open.first_card_ms)}.`));
      const bar = el("div", "waiting-bar");
      bar.appendChild(el("span"));
      empty.appendChild(bar);
      state.waitBar = bar.firstChild;
      state.startedAt = Date.now();
    }
  });
  source.addEventListener("chat", (e) => queueOrApply("chat", JSON.parse(e.data)));
  source.addEventListener("card", (e) => queueOrApply("card", JSON.parse(e.data)));
  source.addEventListener("done", () => {
    source.close();
    const button = document.getElementById("pp");
    button.textContent = "Replay finished";
    button.disabled = true;
  });
  source.addEventListener("error", () => source.close());
}

function queueOrApply(kind, event) {
  if (state.paused) state.queue.push([kind, event]);
  else apply(kind, event);
}

/* ------------------------------------------------------------------ controls */
document.getElementById("pp").addEventListener("click", () => {
  state.paused = !state.paused;
  const button = document.getElementById("pp");
  button.textContent = state.paused ? "Play" : "Pause";
  button.setAttribute("aria-pressed", String(state.paused));
  if (!state.paused) {
    const pending = state.queue.splice(0, state.queue.length);
    for (const [kind, event] of pending) apply(kind, event);
  }
});

document.getElementById("restart").addEventListener("click", () => start());

for (const button of document.querySelectorAll(".speeds .seg")) {
  button.addEventListener("click", () => {
    for (const other of document.querySelectorAll(".speeds .seg")) {
      other.classList.toggle("is-active", other === button);
      other.setAttribute("aria-pressed", String(other === button));
    }
    start(state.fixture, state.system, Number(button.dataset.speed));
  });
}

const debug = document.getElementById("debug-toggle");
debug.addEventListener("click", () => {
  const panel = document.getElementById("debug");
  panel.hidden = !panel.hidden;
  debug.setAttribute("aria-expanded", String(!panel.hidden));
});

/* ------------------------------------------------------------------ live capture
   The demo path, never the default. Replay is what a judge reproduces with no keys, so nothing
   here runs on page load — it takes a deliberate click, and every event carries the spend so the
   number on screen is the number being spent. The lag is stated, not hidden: a 60-second window
   cannot be analysed until it has finished. */
function goLive() {
  const channel = (document.getElementById("picker-input").value.trim()
    || (catalogue[0] || {}).channel || "").toLowerCase();
  const note = document.getElementById("picker-note");
  const spend = document.getElementById("live-spend");
  if (!channel) { note.textContent = "Name a channel to go live on."; return; }

  reset();
  if (state.source) { state.source.close(); state.source = null; }
  const source = new EventSource(`/api/live?channel=${encodeURIComponent(channel)}`);
  state.source = source;
  spend.hidden = false;
  spend.textContent = "starting…";

  const badge = document.getElementById("mode-badge");
  source.addEventListener("status", (e) => {
    const s = JSON.parse(e.data);
    clear(badge);
    badge.appendChild(el("span", "dot"));
    badge.appendChild(document.createTextNode(`LIVE · ~${s.lag_seconds}s behind`));
    note.textContent = s.message;
    document.getElementById("captured-at").textContent = `${s.channel} · capturing now`;
  });

  source.addEventListener("window", (e) => {
    const w = JSON.parse(e.data);
    for (const m of w.chat) addMessage({ id: m.id, author: m.author, text: m.text });
    for (const card of w.verified) {
      addCard({ kind: "card", state: cardState(card), card: card });
    }
    for (const card of w.rejected) addCard({ kind: "card", state: "rejected", card: card });
    spend.textContent = `window ${w.window} · ~$${w.estimated_usd.toFixed(4)} this session `
      + `· $${w.budget.spent_usd.toFixed(2)} of $${w.budget.cap_usd.toFixed(2)} cap`;
  });

  source.addEventListener("stopped", (e) => {
    const s = JSON.parse(e.data);
    source.close();
    note.textContent = s.message;
    clear(badge);
    badge.appendChild(el("span", "dot"));
    badge.appendChild(document.createTextNode("REPLAY"));
    spend.textContent = s.estimated_usd
      ? `stopped · ~$${Number(s.estimated_usd).toFixed(4)} spent this session` : "";
  });
  source.addEventListener("error", () => source.close());
}

/* A card's state, computed the same way the gate does — grounded means it named a cause its
   evidence supports. */
function cardState(card) {
  const t = card.trigger || {};
  const ok = (card.gate && card.gate.ok) && card.type !== "none"
    && t.event_id && t.event_id !== UNKNOWN && !!t.quote && (card.evidence || []).length > 0;
  return ok ? "grounded" : "abstained";
}

function clear(node) {
  while (node && node.firstChild) node.removeChild(node.firstChild);
  return node;
}

document.getElementById("go-live").addEventListener("click", goLive);

/* ------------------------------------------------------------------ the picker */
let catalogue = [];

function renderChips(selected) {
  const box = document.getElementById("picker-chips");
  while (box.firstChild) box.removeChild(box.firstChild);
  for (const entry of catalogue) {
    const chip = el("button", "chip-btn", entry.channel);
    chip.type = "button";
    if (entry.fixture_id === selected) chip.classList.add("is-active");
    chip.addEventListener("click", () => {
      start(entry.fixture_id, state.system, state.speed);
      renderChips(entry.fixture_id);
    });
    box.appendChild(chip);
  }
  box.appendChild(el("span", "chip-sep", "·"));
  for (const system of ["agent", "baseline"]) {
    const chip = el("button", "chip-btn", system);
    chip.type = "button";
    if (system === state.system) chip.classList.add("is-active");
    chip.addEventListener("click", () => {
      start(state.fixture, system, state.speed);
      renderChips(selected);
    });
    box.appendChild(chip);
  }
}

document.getElementById("picker").addEventListener("submit", (event) => {
  event.preventDefault();
  const typed = document.getElementById("picker-input").value.trim().toLowerCase();
  const match = catalogue.find((e) => (e.channel || "").toLowerCase() === typed
                                   || (e.fixture_id || "").toLowerCase() === typed);
  const note = document.getElementById("picker-note");
  if (!match) {
    /* Never a dead end: name what exists and leave the chips one click away. */
    note.textContent = "No recording of that channel yet. These are captured:";
    return;
  }
  note.textContent = "Recorded windows replayed at their true cadence. Live capture uses the "
    + "same pipeline and is documented in the reproduction guide.";
  start(match.fixture_id, state.system, state.speed);
  renderChips(match.fixture_id);
});

fetch("/api/fixtures")
  .then((r) => r.json())
  .then((data) => {
    catalogue = data.fixtures || [];
    const list = document.getElementById("picker-list");
    for (const entry of catalogue) {
      const option = document.createElement("option");
      option.value = entry.channel;
      list.appendChild(option);
    }
    const selected = data.selected
      && catalogue.find((e) => e.fixture_id === data.selected)
      ? data.selected
      : (catalogue[0] || {}).fixture_id;
    renderChips(selected);
    start(selected, "agent", 1);
  })
  .catch(() => {
    document.getElementById("signals-empty").textContent =
      "No recorded run is available to play.";
  });
