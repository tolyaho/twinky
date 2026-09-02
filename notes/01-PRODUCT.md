# Product definition — do not drift

## The thesis, from the team's own record

**20 Sept 2025**, two days after the group was created, before anything was built:

> «Ну контекст из видео не помешал бы / Чтобы понять, когда вопрос к чату, а когда нет»

That is the whole product in one line. Everything since — Deepgram, frame captions, the
`message_reason` work — is that sentence taken seriously.

Two corollaries from the next day, both kept: vision repairs speech, because ASR mangles game
slang (*«если она видит картинку кски то может понять что авик»*), and the slang dictionary worth
having is the one chat itself types.

Stated plainly:

> A chat message is not text. It is a response to something.
> `10` is meaningless. `10` thirty seconds after *"how would you rate this game?"* is a rating.
> Chat is only interpretable against the stimulus that caused it — and the stimulus is in the
> audio and on the screen, not in the chat.

This is why the system is multimodal. Not sophistication for its own sake: it is the minimum
required for chat to mean anything at all.

## The goal — a loop, not a feature

**16 Jan 2026**, unprompted, on why any of it matters:

> «Вот мы сделаем как бы чат более доступным / В чат будет интереснее писать / Значит стрим
> интереснее будет смотреть / Он будет более живым / Тогда и просмотров больше должно быть»

**Readable chat → worth writing in → livelier stream → more views.**

The streamer's half: *«стримеру легче чат читать … Обычно же ты пишешь / И твоё сообщение просто
пропадает»*. The viewer's half: *«зрители будут видеть, что их сообщение может быть ценным, и не
потеряться относительно флуда»*. And the board is meant to go **on stream**, visible to viewers —
*«любой стример захочет показывать как там разные группы из кластеризации соревнуются с друг
другом по активу»*.

The dashboard is the mechanism; the loop is the point.

## Invariant

> Twinky turns an unreadable live chat into a small number of verified audience
> signals: it links each cluster of answers, reactions, questions and warnings to the exact
> stream moment that caused it, and shows the evidence.

If a change does not strengthen
`multimodal stream context -> grounded audience signal -> evidence -> streamer action`,
it is out of scope.

## The four things the product does

**A · Every message gets a cause.** *«чел написал сообщение, а мы уже через секунду поняли и
объяснили к чему это сообщение, что значит. Это же очень круто, человек или модер так не
сможет.»* Measured Jan 2026: 7 s average, 1 s median.

**B · The board — clusters bound to the streamer's own quotes.** Drawn by hand in the team chat,
Jan 2026, including the requirement that has been there since the first sketch: *«только там
иногда кластеры не привязываются ни к чему, это тож учти»* — **abstention was a product
requirement before it was a metric.**

**C · An agent you talk to.** *«agentic RAG … сначала сделаю хотя бы распознавание запросов для
бота. Потом уже надо будет на general вопросы научиться отвечать»*. Built and running in March
2026; not rebuilt on this codebase.

**D · Polls read out of chat.** Native Twitch polls need affiliate status and a user access
token, so a moderator bot cannot open one. The answer was to stop trying: *«А почему бы просто из
чата опрос не парсить тогда? Ну ответы брать из чата. ДА / НЕТ»* — read the poll that already
happened.

## Real-time, not an archive

*«Как круто, что нам почти ничего хранить не надо … Мы же делаем упор на то, что в моменте
происходит»* (L859–861). The post-stream debrief is a by-product of work already done live, not
the reason the system exists. Any framing that makes storage the point contradicts this.

## Intended user (be this specific in the README)

A mid-to-large streamer or their operator: thousands of concurrent viewers, tens of chat
messages per second, a handful of volunteer moderators, reading perhaps a low single-digit
percentage of chat during a broadcast.

## The unit: a signal card

```json
{
  "signal_id": "sig_0142",
  "type": "audience_answer",
  "title": "Chat says go left",
  "distribution": {"left": 312, "right": 188},
  "trigger": {"kind": "speech", "event_id": "tr_881",
              "quote": "куда идти - в лес или на базу?", "ts_ms": 1724951203000},
  "evidence": ["msg_9912", "msg_9915", "msg_9931"],
  "confidence": 0.86,
  "status": "verified",
  "action": {"kind": "draft_poll", "state": "pending_approval"},
  "trace_id": "trc_a91f"
}
```

`trigger` may be `unknown`. A card that says *"chat is warning you about something and I cannot
prove what caused it"* is correct behaviour, not a failure.

## Five card types

Maps onto the seven categories in `reference/src/parsers/message_reasons/prompts/general.txt`,
so this is continuity with the taxonomy that was hand-validated in Jan 2026 rather than a
redesign. **Reacting to another viewer is a valid reason in that taxonomy** — the gate's
reaction-trigger exception exists because of it.

| Card | Category in the original taxonomy | Note |
|---|---|---|
| **Audience Answer** | `DIRECT_ANSWER` | Strongest feature. A poll on any question asked aloud — no `!vote`, no widget, **no Affiliate/Partner status required**. |
| **Reaction** | `REACTION_OR_COMMENTARY` | Wave of reaction bound to the quote or frame that triggered it. |
| **Unanswered Question** | `DIRECT_QUESTION` | "Answered or not" needs the transcript — a chat-only system structurally cannot produce this card. |
| **Warning** | `STREAM_TECH_FEEDBACK`, `HELPFUL_GUIDANCE` | Often has no provable cause. This is where abstention is exercised. |
| **Nothing** | — | Explicit "no signal in this window". `SOCIAL_OR_COMMUNITY` and `OFF_TOPIC_OR_MISC` collapse into noise and never surface. |

## Features

**Capture** — time-synchronized multimodal ingestion: chat (IRC), speech (Deepgram, diarized),
screen (frame captions). One normalized event stream. Replay and live.

**Reduce** — deterministic collapse of duplicates and emote floods, preserving counts and source
ids. Not an LLM job. This is the January cost finding turned into a component.

**Ground** — rolling stream context from speech + frames; group chat by *what caused it* rather
than lexical similarity. The `message_reason` breakthrough generalised from per-message to
per-event.

**Verify** — deterministic provenance gate. Do the cited message ids exist and fall inside the
claimed window? Does the quoted trigger appear verbatim in the transcript? Reject otherwise.

**Remember** — the 1m/5m/30m/2h summary hierarchy, so a six-hour stream need not fit one context.

**Deliver** — two surfaces from one run:
- *Live rail*: cards as the stream happens, with evidence drawer, confidence, trace id.
- *Post-stream debrief*: when the run ends, cards roll up into a document — unanswered
  questions, reaction waves with timestamps, clip candidates, recurring themes. This is the
  self-contained artifact a live dashboard can never produce, because it never *finishes*.

**Act** — exactly one human-approved action: approve → draft poll. Nothing posts automatically.

## Why each component exists (put this table in the README)

| Component | Observed failure it fixes |
|---|---|
| Speech + frame context | `10`, `left`, `БОТ` are meaningless as text (Sept 2025 – Jan 2026) |
| Event-centric grouping | Embedding clustering gave unstable clusters (Oct 2025; Mar 2026: ~100 clusters, poor quality) |
| Deterministic reducer | Per-message inference: ~$40/mo/large channel, ~30s tail latency, provider rate limits (Jan, Mar 2026) |
| Provenance gate + abstention | Cards attaching to nothing — noted verbatim in the team chat, 4 Jan 2026 |
| Summary hierarchy | A long stream does not fit one context window |
| Replay + response cache | Live streams are not reproducible; a claim nobody can re-run for free stops being checkable |

## The honest objection, and the answer

The team's own doubt (21 Oct 2025): *"top streamers probably don't need this."* Do not hide it —
answer it. The pitch is not "read your chat for you". It is **"recover what you are structurally
unable to see, while it is still happening."** A streamer who ignores chat live still wants the
unanswered-question list at the end of the hour.

## Not this product

Generic chatbot; autonomous chatter that fills silence; viewer-facing Q&A bot; social network or
streamer map; giveaway fulfilment; web research agent; vanity-metric dashboard; moderation
replacement.
