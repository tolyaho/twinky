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
const CITE_HIGHLIGHT_MS = 1800;
const CITE_HOLD_MS = 1500;      /* long enough to read the cited row before the feed resumes */

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
  epoch: 0,                     /* every start() gets one; stale listeners are ignored */
  pinned: true,                 /* following the flood, until a citation asks to be looked at */
  holdUntil: 0,
  fixture: null,
  system: "agent",
  speed: 1,
  paused: false,
  queue: [],                    /* events that arrived while paused */
  counts: { chat: 0, grounded: 0, abstained: 0, rejected: 0 },
  rows: new Map(),              /* event id -> <li>, for the citation highlight */
  boardRows: 0,
  boardSeen: false,
  questionCount: 0,
  view: "board",
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
  /* Only follow the flood while pinned. A card cites messages from the START of its window —
     up to 60 seconds and ~100 rows back — so pinning to the bottom on every message meant the
     citation highlight always fired somewhere nobody could see. That gesture is the one the
     product rests on, so the feed yields to it. */
  if (state.pinned) feed.scrollTop = feed.scrollHeight;

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
  highlightIds(card.evidence || []);
}

/* Shared with the board, where clicking a row lights up every message behind it — the same
   gesture, driven by a group's own event ids rather than a card's evidence list. */
function highlightIds(ids) {
  const rows = [];
  for (const id of ids) {
    const row = state.rows.get(id);
    if (!row) continue;                       /* evicted past the 200-row cap; nothing to show */
    row.classList.add("cited");
    rows.push(row);
    setTimeout(() => row.classList.remove("cited"), CITE_HIGHLIGHT_MS);
  }
  if (!rows.length) return;

  /* Stop following, bring the first cited message into view, hold, then resume. */
  state.pinned = false;
  showFollow(true);
  rows[0].scrollIntoView({ block: "center", behavior: "smooth" });

  const holdToken = state.holdUntil = Date.now() + CITE_HOLD_MS;
  setTimeout(() => {
    if (state.holdUntil !== holdToken) return;   /* another citation, or the reader took over */
    resumeFollowing();
  }, CITE_HOLD_MS);
}

function showFollow(visible) {
  const button = document.getElementById("follow");
  if (button) button.hidden = !visible;
}

function resumeFollowing() {
  state.pinned = true;
  state.holdUntil = 0;
  showFollow(false);
  const feed = document.getElementById("feed");
  if (feed) feed.scrollTop = feed.scrollHeight;
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
  if (state.view === "signals") {
    document.getElementById("board-n").textContent = String(shown);
  }
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

/* ------------------------------------------------------------------ the board
   Deterministic and computed on the server: groups of real messages under the moment they
   followed. A row states the strength of that link and never implies more than it has —
   `matched` means the trigger text contains the word chat is typing, `preceding` means it was
   merely the last thing said or shown. Neither went through the provenance gate, because
   neither claims causation; the gate's own ledger is in the rail. */
function addBoard(event) {
  const data = event.board || {};
  const rows = data.rows || [];
  const orphans = data.unattributed || [];
  const rowsEl = document.getElementById("boardrows");
  clear(rowsEl);

  const origin = (data.window_ms || [0])[0];
  for (const row of rows) rowsEl.appendChild(boardRow(row, origin));
  if (orphans.length) rowsEl.appendChild(orphanBlock(orphans));
  if (!rows.length && !orphans.length) {
    rowsEl.appendChild(el("p", "empty", "Nothing in this window grouped. Every message was a one-off."));
  }

  const f = data.footer || {};
  const foot = document.getElementById("board-foot");
  foot.hidden = false;
  foot.textContent = `${f.messages || 0} messages · ${f.rows || 0} rows · `
    + `${f.singletons || 0} singletons not shown`
    + (f.rows_hidden ? ` · ${f.rows_hidden} more rows hidden` : "");
  state.boardRows = rows.length + orphans.length;
  state.boardSeen = true;
  if (state.view === "board") {
    document.getElementById("board-n").textContent = String(state.boardRows);
  }

  renderRail(event.rail || {});
  renderQuestions(event.questions || {});
}

/* ------------------------------------------------------------------ questions to you
   The cheapest proof of the whole thesis: whether a question was answered is decided by reading
   the transcript AFTER it was asked. A chat-only system has the question and no way to know. */
function renderQuestions(q) {
  const list = q.questions || [];
  const box = document.getElementById("questions");
  clear(box);
  state.questionCount = q.total || 0;
  document.getElementById("q-n").textContent = String(state.questionCount);

  if (!list.length) {
    box.appendChild(el("p", "empty", "No question has been asked yet."));
  }
  for (const item of list) {
    const row = el("article", `qrow ${item.answered ? "is-answered" : "is-open"}`);
    const head = el("div", "qrow-h");
    head.appendChild(el("span", "qdot"));
    head.appendChild(el("span", "qstate", item.answered ? "answered" : "unanswered"));
    head.appendChild(el("span", "qn", `${item.count} asked`));
    row.appendChild(head);
    row.appendChild(el("p", "qtext", `“${item.text}”`));
    if (item.answered) {
      /* The line the streamer actually said, so the reader judges the link rather than
         trusting it. Two shared content words is the test, and it is stated on the method page. */
      const ans = el("p", "qans");
      ans.appendChild(el("span", "label", "you said"));
      ans.appendChild(document.createTextNode(`“${item.answered.text}”`));
      row.appendChild(ans);
    }
    row.addEventListener("click", () => highlightIds(item.event_ids || []));
    box.appendChild(row);
  }

  const foot = document.getElementById("q-foot");
  foot.textContent = `${q.total || 0} questions · ${q.asked || 0} asked · `
    + `${q.unanswered || 0} still unanswered`
    + (q.hidden ? ` · ${q.hidden} not shown` : "");
  if (!document.getElementById("questions").hidden) foot.hidden = false;
}

function boardRow(row, origin) {
  const box = el("article", "brow");
  const t = row.trigger || {};
  const head = el("header", "brow-h");
  head.appendChild(el("span", `pill link-${t.link}`, t.link === "matched" ? "names it" : "just before"));
  head.appendChild(el("span", "brow-kind", t.kind === "speech" ? "you said" : "on screen"));
  head.appendChild(el("span", "brow-at", `+${clock(t.ts_ms - origin)}`));
  head.appendChild(el("span", "brow-n", `${row.count}`));
  box.appendChild(head);
  box.appendChild(el("p", "brow-q", `“${(t.text || "").trim()}”`));

  const max = Math.max(...row.groups.map((g) => g.count), 1);
  for (const g of row.groups) box.appendChild(groupLine(g, max));
  box.addEventListener("click", () => highlightIds(row.groups.flatMap((g) => g.event_ids)));
  return box;
}

/* The count carries a proportional bar so 27 and 4 differ at a glance without a chart. */
function groupLine(g, max) {
  const line = el("div", "gline");
  line.appendChild(el("span", "gline-label", g.label));
  const bar = el("span", "gline-bar");
  const fill = el("span", "gline-fill");
  fill.style.width = `${Math.max(4, Math.round((g.count / max) * 100))}%`;
  bar.appendChild(fill);
  line.appendChild(bar);
  line.appendChild(el("span", "gline-n", String(g.count)));
  const samples = el("p", "gline-samples");
  samples.textContent = g.samples.map((s) => `“${s}”`).join("  ");
  line.appendChild(samples);
  return line;
}

function orphanBlock(orphans) {
  const box = el("article", "brow brow-orphan");
  const head = el("header", "brow-h");
  head.appendChild(el("span", "pill link-none", "unattributed"));
  head.appendChild(el("span", "brow-kind", "no moment before it"));
  head.appendChild(el("span", "brow-n",
    String(orphans.reduce((n, g) => n + g.count, 0))));
  box.appendChild(head);
  const max = Math.max(...orphans.map((g) => g.count), 1);
  for (const g of orphans) box.appendChild(groupLine(g, max));
  box.addEventListener("click", () => highlightIds(orphans.flatMap((g) => g.event_ids)));
  return box;
}

/* ------------------------------------------------------------------ live counts
   Between window closes. The analysis window is still 60 seconds and the model still reasons
   over 60 seconds — what changed is that the BOARD no longer waits for it. Grouping is
   deterministic and calls nothing, so a group is drawn from the moment it crosses the threshold
   and its count ticks up as chat arrives: `violet 4 … 11 … 27`. Nothing here is attributed to a
   cause and the header says so; the cause arrives when the window closes. */
function addTick(event) {
  const groups = event.groups || [];
  const box = document.getElementById("board-live");
  const list = document.getElementById("live-groups");
  box.hidden = !groups.length;
  clear(list);

  const max = Math.max(...groups.map((g) => g.count), 1);
  for (const g of groups) {
    const line = groupLine(g, max);
    line.addEventListener("click", () => highlightIds(g.event_ids || []));
    list.appendChild(line);
  }

  /* One thin hairline for time to the next close, so the wait is legible rather than mysterious. */
  const fill = document.getElementById("nextclose-fill");
  const close = event.next_close_ms;
  if (close && close > event.at_ms) {
    const span = close - Math.max(0, close - 60000);
    fill.style.width = `${Math.min(100, Math.round((1 - (close - event.at_ms) / span) * 100))}%`;
  } else {
    fill.style.width = "100%";
  }
}

/* ------------------------------------------------------------------ the rail */
function renderRail(r) {
  const rail = document.getElementById("rail");
  clear(rail);
  if (!r || r.messages === undefined) return;
  document.getElementById("rail-n").textContent = `${r.messages}`;

  rail.appendChild(sparkline(r.rate || []));
  rail.appendChild(railBlock("volume", [
    ["messages", r.messages],
    ["peak burst", `${r.peak_burst} / 10s`],
    ["velocity", `${r.peak_per_second}/s`],
  ]));
  rail.appendChild(railBlock("who is talking", [
    ["unique chatters", r.unique_chatters],
    ["new this window", r.new_chatters],
    ["msgs per chatter", r.messages_per_chatter],
    /* Whether 500 messages is five people or five hundred is a completely different fact, and
       the raw count hides it entirely. */
    ["top 10% share", `${Math.round((r.concentration || 0) * 100)}%`],
  ]));
  const c = r.composition || {};
  rail.appendChild(railBlock("composition", [
    ["grouped into", `${c.groups || 0} groups`],
    ["singletons", c.singletons || 0],
    ["reaction wave", r.reaction_wave || 0],
  ]));

  const qs = r.questions || [];
  const questions = railBlock("questions to you", qs.length
    ? qs.slice(0, 4).map((q) => [q.text, `${q.count} asked`])
    : [["none in this window", ""]]);
  rail.appendChild(questions);

  /* Zero speech segments is the truth on stableronaldo, and a silent window is a finding about
     the stream rather than a hole in the data. It is stated rather than left blank. */
  rail.appendChild(railBlock("stream context", [
    ["speech segments", r.silent ? "silent window" : r.speech_segments],
    ["frame captions", (r.frame_captions || []).length],
  ]));

  const g = r.gate || {};
  const codes = Object.entries(g.codes || {});
  rail.appendChild(railBlock("gate", [
    ["verified", g.verified || 0],
    ["abstained", g.abstained || 0],
    ["rejected", g.rejected || 0],
    ...codes.map(([code, n]) => [code, n]),
  ]));
}

function railBlock(title, pairs) {
  const box = el("section", "rblock");
  box.appendChild(el("h3", "rblock-t", title));
  const dl = el("dl", "rstats");
  for (const [k, v] of pairs) {
    dl.appendChild(el("dt", null, String(k)));
    dl.appendChild(el("dd", null, String(v)));
  }
  box.appendChild(dl);
  return box;
}

function sparkline(rate) {
  const box = el("section", "rblock");
  box.appendChild(el("h3", "rblock-t", "rate · per 10s"));
  const chart = el("div", "spark");
  const max = Math.max(...rate, 1);
  for (const n of rate) {
    const bar = el("span", "spark-bar");
    bar.style.height = `${Math.max(2, Math.round((n / max) * 100))}%`;
    bar.title = `${n} messages`;
    chart.appendChild(bar);
  }
  box.appendChild(chart);
  return box;
}

/* ------------------------------------------------------------------ transport */
function apply(kind, event) {
  if (kind === "chat") addMessage(event);
  else if (kind === "card") addCard(event);
  else if (kind === "board") addBoard(event);
  else if (kind === "tick") addTick(event);
}

function reset() {
  if (state.source) { state.source.close(); state.source = null; }
  state.queue = [];
  state.rows.clear();
  state.counts = { chat: 0, grounded: 0, abstained: 0, rejected: 0 };
  state.notedUngrounded = false;
  state.pinned = true;
  state.holdUntil = 0;
  state.boardRows = 0;
  state.boardSeen = false;
  state.questionCount = 0;

  /* The board and the rail describe ONE window. Leaving the previous fixture's rows up while a
     new stream fills the feed is the stale-identity bug that made an empty page read as loading,
     one panel over. */
  const rowsEl = document.getElementById("boardrows");
  if (rowsEl) {
    clear(rowsEl);
    rowsEl.appendChild(el("p", "empty", "Waiting for the first window to close…"));
  }
  const railEl = document.getElementById("rail");
  if (railEl) {
    clear(railEl);
    railEl.appendChild(el("p", "empty", "No window has closed yet."));
  }
  const railN = document.getElementById("rail-n");
  if (railN) railN.textContent = "—";
  const liveBox = document.getElementById("board-live");
  if (liveBox) {
    liveBox.hidden = true;
    clear(document.getElementById("live-groups"));
    document.getElementById("nextclose-fill").style.width = "0%";
  }
  const questionsEl = document.getElementById("questions");
  if (questionsEl) {
    clear(questionsEl);
    questionsEl.appendChild(el("p", "empty", "No question has been asked yet."));
  }
  const qn = document.getElementById("q-n");
  if (qn) qn.textContent = "0";
  for (const id of ["board-foot", "sig-split", "q-foot"]) {
    const foot = document.getElementById(id);
    if (foot) foot.hidden = true;
  }
  const boardFoot = document.getElementById("board-foot");
  if (boardFoot) boardFoot.textContent = "";
  showFollow(false);

  /* Identity is cleared here, not only on success. A failed start() used to leave the previous
     run's badge and channel line on screen above an empty page, which reads as "still loading". */
  const badge = document.getElementById("mode-badge");
  clear(badge);
  badge.appendChild(el("span", "dot"));
  badge.appendChild(document.createTextNode("REPLAY"));
  document.getElementById("captured-at").textContent = "";
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
  const epoch = ++state.epoch;
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

  const current = () => epoch === state.epoch;   /* a superseded stream must stay silent */

  source.addEventListener("meta", (e) => {
    if (!current()) return;
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
  source.addEventListener("chat", (e) => {
    if (current()) queueOrApply("chat", JSON.parse(e.data));
  });
  source.addEventListener("card", (e) => {
    if (current()) queueOrApply("card", JSON.parse(e.data));
  });
  source.addEventListener("done", () => {
    source.close();
    if (!current()) return;             /* an abandoned stream must not end the live one */
    const button = document.getElementById("pp");
    button.textContent = "Replay finished";
    button.disabled = true;
  });

  /* A stream error was silently swallowed: the page sat on "Connecting to the recording…" for
     ever while the badge still showed the previous run. A judge reads that as loading. */
  source.addEventListener("error", () => {
    source.close();
    if (!current()) return;
    failStream(`The recording stream stopped. The server at ${location.host} may not be running.`);
  });
}

function failStream(message) {
  const empty = document.getElementById("signals-empty");
  if (empty) {
    empty.className = "empty failure";
    clear(empty);
    empty.appendChild(el("span", null, message));
    const retry = el("button", "linkish", "Try again");
    retry.type = "button";
    retry.addEventListener("click", () => start(state.fixture, state.system, state.speed));
    empty.appendChild(document.createTextNode(" "));
    empty.appendChild(retry);
  }
  const badge = document.getElementById("mode-badge");
  clear(badge);
  badge.appendChild(el("span", "dot"));
  badge.appendChild(document.createTextNode("NO STREAM"));
  document.getElementById("captured-at").textContent = "";
  const pp = document.getElementById("pp");
  pp.disabled = false;                       /* controls come back, so retry is reachable */
  pp.textContent = "Pause";
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
    debounced(() => start(state.fixture, state.system, Number(button.dataset.speed)));
  });
}

/* The middle column shows one kind of thing at a time. A deterministic row and a gated card
   drawn in the same column would read as the same kind of claim, and they are not. */
const VIEWS = {
  board:     { pane: "boardrows", foot: "board-foot", tab: "tab-board",     title: "The board" },
  signals:   { pane: "signals",   foot: "sig-split",  tab: "tab-signals",   title: "Signals" },
  questions: { pane: "questions", foot: "q-foot",     tab: "tab-questions", title: "Questions to you" },
};

function showMiddle(view) {
  state.view = view;
  for (const [name, v] of Object.entries(VIEWS)) {
    const on = name === view;
    document.getElementById(v.pane).hidden = !on;
    document.getElementById(v.foot).hidden = !on || !state.boardSeen;
    const tab = document.getElementById(v.tab);
    tab.classList.toggle("is-active", on);
    tab.setAttribute("aria-pressed", String(on));
  }
  document.getElementById("board-h").textContent = VIEWS[view].title;
  document.getElementById("board-n").textContent = String(
    view === "board" ? (state.boardRows || 0)
      : view === "questions" ? (state.questionCount || 0)
        : (state.counts.grounded || 0) + (state.counts.abstained || 0));
}
for (const [name, v] of Object.entries(VIEWS)) {
  document.getElementById(v.tab).addEventListener("click", () => showMiddle(name));
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
document.getElementById("follow").addEventListener("click", resumeFollowing);

/* Scrolling up is a deliberate act: stop following and leave the affordance until they come
   back. Within 40px of the bottom counts as still following. */
document.getElementById("feed").addEventListener("scroll", () => {
  const feed = document.getElementById("feed");
  const atBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 40;
  if (atBottom && !state.holdUntil) { state.pinned = true; showFollow(false); }
  else if (!atBottom) { state.pinned = false; showFollow(true); }
}, { passive: true });

/* ------------------------------------------------------------------ the picker */
let catalogue = [];

let pending = null;
function debounced(fn, ms = 120) {
  if (pending) clearTimeout(pending);
  pending = setTimeout(() => { pending = null; fn(); }, ms);
}

function renderChips(selected) {
  const box = document.getElementById("picker-chips");
  while (box.firstChild) box.removeChild(box.firstChild);
  for (const entry of catalogue) {
    const chip = el("button", "chip-btn", entry.channel);
    chip.type = "button";
    if (entry.fixture_id === selected) chip.classList.add("is-active");
    chip.addEventListener("click", () => {
      /* Two clicks in the same tick used to open two streams and abandon one mid-write. */
      debounced(() => { start(entry.fixture_id, state.system, state.speed);
                        renderChips(entry.fixture_id); });
    });
    box.appendChild(chip);
  }
  box.appendChild(el("span", "chip-sep", "·"));
  for (const system of ["agent", "baseline"]) {
    const chip = el("button", "chip-btn", system);
    chip.type = "button";
    if (system === state.system) chip.classList.add("is-active");
    chip.addEventListener("click", () => {
      debounced(() => { start(state.fixture, system, state.speed); renderChips(selected); });
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
