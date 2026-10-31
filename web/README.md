# Twinky — live chat clustering demo (`web/`)

A public, zero-config web demo of Twinky's **live chat clustering**. Enter a Twitch channel and
watch its real chat collapse into the few things the audience is actually saying — reactions by
kind, repeated messages, topics said in different words, shared questions — grouped and counted,
updating every ~1.5s.

This is the honest **Tier 0** of the product: real live chat, **no API keys, no paid calls, no
server state**. Topics come from a small sentence-embedding model that runs **in the visitor's
browser** (`src/semantic/`); nothing a chatter writes is sent anywhere. The deterministic word
rules it replaced are kept as the baseline (`?topics=off`) and as the automatic fallback. It does
not attempt causal attribution of chat to stream moments — that is the research pipeline in
`../src/ts`, deliberately kept separate.

## Architecture (why it's this small)

The browser connects **directly** to Twitch's anonymous IRC WebSocket
(`wss://irc-ws.chat.twitch.tv:443`, the `justinfan` read-only login — the same handshake
`../src/ts/ingest/capture.py` uses) and runs the clustering **client-side**. Each visitor's own
browser does the work, so there is no server holding sockets open, no fan-out, and it scales for
free. The clustering is a **byte-faithful TypeScript port** of the untouched Python
(`reduce.py` / `board.py`) — proven by `scripts/gen_parity.py`, which drives the real Python over a
corpus plus a real committed fixture, and `tests/unit/parity.test.ts`, which asserts the port
reproduces it exactly (105 vectors).

```
browser ── anonymous IRC WS ──► Twitch          (real chat, read-only, no credentials)
   │
   ├─ src/twitch/      parse + connection lifecycle (reconnect, keepalive, dedupe, states)
   ├─ src/engine/      rolling window, bounded buffers, pseudonymisation, epoch/cancellation
   ├─ src/cluster/     canonical + group_chat + rail/questions  (faithful port of src/ts)
   ├─ src/semantic/    grouping by meaning: fast path, then a Web Worker running
   │                   all-MiniLM-L6-v2 (Transformers.js, ONNX Runtime WebAssembly)
   └─ src/ui/          landing + three-zone live dashboard (React)

worker ── HTTPS ──► Hugging Face hub (model weights, pinned revision) and jsDelivr (ONNX Runtime
                    WebAssembly): ~30 MB, once, when a channel is first opened; then cached

api/twitch-status.ts   OPTIONAL serverless Helix check (live/offline/not_found). Degrades to the
                       IRC-only states when unconfigured; no visitor ever needs credentials.
```

## Run locally

```bash
cd web
npm install
npm run dev            # http://localhost:5173 — enter a live channel
```

A channel can be linked directly: `/?channel=xqc`. `/?replay` opens the recorded example.

## Test

```bash
npm test               # 266 unit tests: clustering parity, IRC lifecycle, network loss, engine,
                       #   stable ordering, broadcast status, grouping by meaning (prep,
                       #   clustering, the worker, the page side, parity with the evaluation)
npm run e2e            # 47 Playwright flows on a synthetic stream (deterministic chat):
                       #   layout, evidence, keyboard, reduced motion, reconnect without
                       #   duplicates, rapid switching, network loss, deep links, off air /
                       #   on air / stale status replies (mocked endpoint), hidden tab,
                       #   ranking stability, view transition, a calibrated ~400 msg/s burst;
                       #   topics in Chromium and WebKit: loading, ready, fallback, ?topics=off,
                       #   channel switch, a 400 msg/s burst the model falls behind on
LIVE_CHANNEL=xqc npm run e2e:live   # 3 real-network checks: live chat, not-found, no false not-found
PW_BASE_URL=https://… npm run e2e:live   # same, against a deployed URL
npm run typecheck      # frontend + serverless function
npm run gen:parity     # regenerate golden vectors from the untouched Python (needs python3)
```

`npm test`, `typecheck` and `build` need **no network and no keys**. `npm run e2e` needs no keys;
it serves the topic model from `eval/.models/` (downloaded by the evaluation) and ONNX Runtime from
`node_modules` (`tests/e2e/fixtures.ts`), and fetches them from the network only if they are missing.

The evaluation behind the topics — real labelled chat, a dev/test split, every arm, the model
choice, speed, stability and cost — is `../evals/semantic/README.md`.

## Deploy (Vercel)

Framework preset **Vite**, output `dist`, root directory `web/`. The `api/` function is optional.

```bash
vercel          # preview
vercel --prod   # production (only with approval)
```

### Optional environment variables (authoritative status only)

| variable | purpose |
|---|---|
| `TWITCH_CLIENT_ID` | a registered Twitch app's client id (server-side only) |
| `TWITCH_CLIENT_SECRET` | its secret, for the client-credentials grant (server-side only) |

With these set, `/api/twitch-status` returns authoritative `live` / `offline` / `not_found`.
**Without them the demo still works** — it simply uses the IRC-only states (connected / quiet).
Secrets stay server-side; they are never sent to the browser.

How the endpoint behaves:

| situation | answer | caching | the page |
|---|---|---|---|
| no credentials | `unknown`, `reason: "unconfigured"` | 30 s | no broadcast pill; asked once, never polled |
| Helix: user has a stream | `live` + `startedAt` | 30 s (`s-maxage`, then stale-while-revalidate 30 s) | "On air · 1h 12m"; rechecked every 60 s |
| Helix: user, no stream | `offline` | 30 s | "Off air"; a silent chat gets the off-air screen |
| Helix: no such user | `not_found` | 30 s | "No such channel" at once, without the 8 s IRC wait |
| timeout (4 s), 5xx, bad body, token failure | `unknown`, `reason: "twitch_unavailable"` | `no-store` | keeps the last real answer for up to 3 min, then shows none |

A 401 is retried once with a fresh app token. Nothing is ever inferred from chat silence.

## Privacy

Chatter logins are **pseudonymised in the browser** with a per-session salt that is never stored
or transmitted (mirrors `live_chat.py::_live_salt`). Nothing is persisted and nothing is sent to
any Twinky server. The page connects to Twitch, and when a channel is opened it downloads the topic
model (Hugging Face hub) and its runtime (jsDelivr); chat text never leaves the browser. Message **text** is shown verbatim
(it is public chat and may itself contain names); the UI says so.

## Honesty invariants

- A green "Live chat" badge appears only while messages are actually arriving. Anonymous IRC
  cannot tell a live channel from an offline one, so the UI says **Connected / Quiet**, never
  "the stream is live", unless the optional Helix check confirms it.
- **Not found needs no credentials.** With the `twitch.tv/commands` capability Twitch answers a
  JOIN to an existing channel (live or offline) with `ROOMSTATE`; an invented name gets no answer,
  so after 8 s the page says *Not found* instead of spinning forever.
- If a very busy chat outruns the 20,000-message buffer while the 5-minute window is selected,
  the board says the window is **sampled** rather than presenting a partial count as whole.
- **One chatter is not the room.** A group is shown only if at least two different chatters wrote
  it; a single account's repeats stay ungrouped and the footer counts them. This is applied after
  the ported `group_chat`, which itself stays byte-identical to the Python.
- **Rates divide by time actually observed.** For the first minute after connecting the window is
  partly time nobody was listening; msgs/min uses the observed span, "new chatters" is withheld
  until the session predates the window, and the sparkline does not draw that time as zero.
- **Network loss is said plainly** ("No network"), and the page reconnects the moment the browser
  is back online — it never reads a dropped network as a missing channel.
- **Off air is Twitch's word, never a guess.** The broadcast pill and the off-air screen appear
  only when Helix says so. Off air with an active chat keeps showing that chat, under a note.
  A status reply for a previous channel is discarded, however late it arrives.
- **Rows move only on a clear overtake** (two messages, or 10% of a big group), so near-ties do
  not swap every recount. Counts are never held back: the number on a row is its current count.
- **Motion never shows an unmeasured value.** Counts roll from one real value to the next rather
  than tweening through numbers nobody counted. With reduced motion requested, nothing slides,
  rolls or pulses, including the script-driven motion the CSS rule cannot reach. In a hidden tab
  nothing renders; counting continues.
- **Replay** (a recorded, pseudonymised capture replaying faster than real time) is always labelled
  REPLAY and is never a silent fallback for a failed live connection — the visitor chooses it.
- Counts are real: every cluster's count equals its underlying messages; a message joins exactly
  one group, so nothing is double-counted (enforced by the parity tests). Opening a group lists
  those messages, newest first.
- **The model never holds the board up.** Reactions, commands and exact repeats are grouped at
  once; topics follow when the model has read the messages. Until then the board says *Finding
  topics…* or *N new messages not read yet*, and unread messages are in no topic. If the model
  cannot load, the board says *Topics unavailable — grouped by shared words* and uses the word rules.
- **A topic label is a quote**, the group's most repeated wording, never a generated summary or
  a cause. Chat alone cannot say why.

## Limitations

- Arbitrary-channel chat and *not found* work without configuration; telling **live from
  offline** needs the optional Twitch app credentials above. The deployed project has none, so
  on the public URL the off-air states are never shown — they are tested against a mocked
  endpoint (`tests/e2e/polish.spec.ts`).
- Chat liveness depends on who is broadcasting right now; a quiet or offline channel shows the
  honest quiet/empty states rather than inventing activity.
- This Tier-0 demo does **not** do speech/vision/causal attribution (the research pipeline does,
  separately, and is not wired in here).
- Topics read **English**. Text mostly in another script groups only when identical. On held-out
  chat, four in five of the message pairs it groups are pairs the labels group too (pair
  precision 0.80), and it finds under a third of the pairs the labels group (recall 0.31). See `../evals/semantic/README.md`.
- The first channel a visitor opens downloads ~30 MB. Save-Data and `?topics=off` skip it.
  Safari on phones has not been measured.
