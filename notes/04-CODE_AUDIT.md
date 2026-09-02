# Audit of the first implementation (`reference/`)

Everything below was verified by reading the archive, not assumed.

## Confirmed defects

1. **Lexicographic cursor over UUIDs.** `save_reasons` advances with
   `Message.message_id > last_message_id` and `max(last_message_id, ...)`. `message_id` is an
   opaque Twitch UUID, so this is string comparison — it silently skips and reorders work.
   Replace with an ordered offset on `(ts_ms, event_id)`.

2. **Schema/parser mismatch.** `chat/parser.py` passes `message_reply_id` into
   `Message.create()`, but the `Message` model declares no such field. Peewee accepts it as a
   stray attribute and drops it. Reply threading is documented in the docstring and never persisted.

3. **Prompt/data mismatch.** `message_reasons/prompts/general.txt` tells the model chat lines are
   `[time_ms] username: message`. `format_chat_messages` emits `1. username: text` — no timestamp.

4. **Interim transcripts leak into summaries.** `chat_summaries/builder.py :: load_audio_transcriptions`
   has no `is_final` filter, so partial and final phrases both enter context and duplicate content.

5. **Unbounded fan-out.** Every 3-message batch is launched as a detached
   `asyncio.create_task(handle_messages(...))` with no global semaphore or backpressure.

6. **Weak screen-context selection.** `get_screen_description` takes only the most recent
   `StreamContext` row and can select one created *after* the messages being explained.

7. **Mutable default arguments.** `save_images` / `_save_images_once` default
   `frame_q: asyncio.Queue = asyncio.Queue(maxsize=50)` — evaluated once at import, shared state.

8. **Local-compute dependency.** Frame annotation posts to `http://127.0.0.1:8080`
   (SmolVLM-1.7B). Incompatible with the API-only constraint and undocumented in the README —
   a clean run silently yields `summary_error` for every frame.

9. **README drift.** Documents MySQL env vars and `TWITCH_OAUTH`; the code uses SQLite and
   anonymous IRC. Documents three broadcasters; `main.py` hardcodes one.

10. **Retired model alias.** Code defaults to `deepseek-chat`, retired 2026-07-24.
    Current: `deepseek-v4-flash` (2026-07-31), `deepseek-v4-pro` (2026-08-13),
    `deepseek-v4-flash-vision-exp` (2026-08-21). **V4-Flash is text-only** — frame captioning
    needs the vision-exp model or another hosted VLM.

11. **The frontend is entirely fake.** `messageGenerator.js`, `chat-simulator.js` and
    `ChatSummary.js` fabricate names, emotes, summaries, cluster values. Zero fetch calls.
    Shipping it as though it were live data is an integrity-gate failure.

12. **No git history in the archive.** There is no `.git` directory. Any commit SHA quoted in a
    document is unverifiable — one earlier planning doc invented
    `0577fa9404193880187291dfe12ccf8987f3a8dd`, which appears in no file. **Do not put it in the
    README.**

## Determinism landmines — these break replay specifically

- `utils.now_ms()` drives every query window. On a recording from yesterday they all return empty.
- `save_reasons` flushes on `oldest_age_ms >= 1000` while polling every 0.5 s → batch composition
  varies with machine speed → prompts vary → **model cache misses**. Batch on `(ts_ms, event_id)`.
- `_q_put_drop_oldest` drops frames at queue depth 50; a slower machine drops different frames.
  Unbounded queue in replay.
- Frame ids derive from `now_ms()` at rename time, and `ImageAnnotation` has a unique index on
  `(broadcaster, time_ms)`. Derive both from fixture time.
- `random` in retry jitter and the `justinfan#####` nick — seed or bypass in replay.
- `temperature=0.2` in summaries — set 0 for anything evaluated.
- `asyncio.gather` over six tasks gives non-deterministic insertion order. Order every
  prompt-feeding query explicitly by `(ts_ms, id)`.

## What to port, and what to leave

**Port** — the IRC tag parser, the streamlink→ffmpeg audio and frame extraction, the Deepgram
wiring, the seven-category taxonomy and the reason prompt (as the starting point for the agent
prompt), the summary-window hierarchy.

**Leave** — the mock frontend logic, the `langgraph_test` notebook (a two-node tutorial, not a
product agent), the SQLite-as-primary-store assumption, and anything reading `now_ms()` directly.
