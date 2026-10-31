# Twinky — live chat clustering demo (`web/`)

A public, zero-config web demo of Twinky's **deterministic live chat clustering**. Enter a Twitch
channel and watch its real chat collapse into the few things the audience is actually saying —
reaction waves, repeated words, audience questions — grouped and counted, updating every ~1.5s.

This is the honest **Tier 0** of the product: real live chat, deterministic grouping, **no model
calls, no API keys, no cost, no server state**. It does not attempt causal attribution of chat to
stream moments — that is the research pipeline in `../src/ts`, deliberately kept separate.

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
   └─ src/ui/          landing + three-zone live dashboard (React)

api/twitch-status.ts   OPTIONAL serverless Helix check (live/offline/not_found). Degrades to the
                       IRC-only states when unconfigured; no visitor ever needs credentials.
```

## Run locally

```bash
cd web
npm install
npm run dev            # http://localhost:5173 — enter a live channel
```

## Test

```bash
npm test               # 169 unit tests: clustering parity, IRC lifecycle, engine, parsing
npm run e2e            # 8 Playwright flows on a synthetic stream (deterministic, no network)
LIVE_CHANNEL=xqc npm run e2e:live   # 3 real-network checks: live chat, not-found, no false not-found
PW_BASE_URL=https://… npm run e2e:live   # same, against a deployed URL
npm run typecheck      # frontend + serverless function
npm run gen:parity     # regenerate golden vectors from the untouched Python (needs python3)
```

`npm test`, `npm run e2e`, `typecheck` and `build` need **no network and no keys**.

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

## Privacy

Chatter logins are **pseudonymised in the browser** with a per-session salt that is never stored
or transmitted (mirrors `live_chat.py::_live_salt`). Nothing is persisted and nothing is sent to
any Twinky server — the only outbound connection is to Twitch. Message **text** is shown verbatim
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
- **Replay** (a recorded, pseudonymised capture replaying faster than real time) is always labelled
  REPLAY and is never a silent fallback for a failed live connection — the visitor chooses it.
- Counts are real: every cluster's count equals its underlying messages; a message joins exactly
  one group, so nothing is double-counted (enforced by the parity tests).

## Limitations

- Arbitrary-channel chat and *not found* work without configuration; telling **live from
  offline** needs the optional Twitch app credentials above.
- Chat liveness depends on who is broadcasting right now; a quiet or offline channel shows the
  honest quiet/empty states rather than inventing activity.
- This Tier-0 demo does **not** do speech/vision/causal attribution (the research pipeline does,
  separately, and is not wired in here).
