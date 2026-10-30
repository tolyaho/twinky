# Twinky — what the project actually is, and what is left to build

Written after re-reading the project's full working record from September 2025 to April 2026:
the chat log, sketches and screenshots. The hackathon framing is set aside; this is the project
as it was defined before the rebuild.

---

## 1. The thesis, on day two

Two days into the project, in September 2025, before anything was built, the whole product fit
in one line: without context from the video you cannot tell whether a question is aimed at chat
or not. Everything since — Deepgram, frame captions, the `message_reason` work — is that sentence
being taken seriously.

The corollary followed a day later: *«если она видит картинку кски то может понять что авик»* —
vision repairing speech, because ASR mangles game slang. And the slang dictionary worth building
is the one chat itself types.

## 2. The goal

Stated in January 2026: make chat more accessible, so it becomes more interesting to write in, so
the stream becomes livelier and more worth watching, so it gets more views. The streamer's half
is that chat becomes easier to read; the viewer's half is that a message can matter instead of
disappearing in the flood. That is why the board is meant to go **on stream**, visible to viewers
— even as a scoreboard where clusters of the audience compete with each other.

This is a loop, not a feature: readable chat → worth writing in → livelier stream → more views.
The dashboard is the mechanism; the loop is the point.

## 3. Four things the product does

**A. Every message gets a cause.** Take a message in chat, look at what the streamer said just
before it, and work out why it was written: someone types "10" shortly after the streamer asked
"how would you rate the game?". Done within a second of the message arriving, which no human
moderator can do at that rate.

Measured then: **7 s average, 1 s median**, ≈$0.05 per 5 minutes on an active chat, ≈$40/month
for a top streamer, optimisable 4–10×.

**B. Табло — clusters bound to the streamer's own quotes.** The layout was drawn by hand in
January 2026, with one requirement written next to it: *«только там иногда кластеры не
привязываются ни к чему, это тож учти»* — **abstention was a product requirement from the first
sketch.**

**C. The agent you talk to.** The direction was set in autumn 2025: an assistant inside the
stream that you can ask things, first recognising requests to the bot, then answering general
questions, triggered by an explicit wake word. My plan at the time was a separate tab for the
agent.

**D. Polls without affiliate status.** Native Twitch polls need affiliate/partner status plus a
user access token, so a bot with mod rights cannot create one. The answer: don't create a poll,
parse the answers out of chat (YES / NO) — **read the one that already happened.**

---

## 4. The agent was built, and it worked

A screenshot from **13 March 2026** shows a real terminal session, `python3 -m agent_rag.run_chat`,
with three exchanges:

- Asked *what is happening on stream right now*, it described the streamer's webcam, what was on
  the main screen, the topic of the chat discussion, the follower goal and that the stream had
  just come back from a commercial break.
- Asked for the last messages in chat, it quoted them.
- Asked whether a named person would show up soon, it answered that it saw no mention of them in
  **the last 30 minutes of the stream memory**.

That last answer is a **correct abstention**, made against a **30-minute memory window**. Vision,
chat, transcript and memory were all live in one conversation.

How I built it: LangChain + LangGraph, Chroma as the vector store, an ingest process running
alongside the chat parser, top-k retrieval per query. Honest about the state at the time:
*«пока есть задержка (в основном эмбеддинги долго делаются) и архитектура совсем никакая, но это
только начало»*, and the laptop was not powerful enough to run it comfortably. The next step was
the orchestrator diagram — the intended second version.

**So the conversational agent is not an idea we skipped. It is a thing that ran, and the diagram
is its intended second version.**

## 5. The finding that matters most

A hand-check of `message_reason` output from **4 Jan 2026** marks this case as correct: a
laughing message labelled *"Agreeing with another viewer's laughter"*, with the other viewer's
message quoted as the cause.

In the original taxonomy, **reacting to another viewer is a valid, correctly-labelled reason.**
The cause of a chat message is allowed to be another chat message.

The hackathon build forbids exactly that. `E_CIRCULAR_EVIDENCE` — "chat explaining chat" — is
**~78% of all gate rejections** and the single largest reason the agent scores 0.500 against a
trivial ablation's 1.000.

That rule is not a bug in the model. It is a rule we added that the product never had, and it is
throwing away the category the original system handled correctly. Fixing this is the highest-value
change available, and it costs nothing but a decision.

## 6. Decisions from the first version that should be kept

| decision | keep? |
|---|---|
| Real-time, purge freely — the point is what happens in the moment | **yes** — the debrief is a by-product, not the point |
| Frames yes, video no — too much memory | yes |
| `nano` over `mini`: 1–3 s vs 10–30 s | yes — latency, not cost, was the reason |
| Deepgram, diarize the streamer, others as person 1/2 | partly — diarisation is enabled and returns one speaker |
| Fixed clusters: emotions, then call-to-action | **untried** — worth testing |
| Merge consecutive similar messages into blocks | shipped, as the deterministic reducer |
| Embedding clustering | **measured and failed** — ~100 clusters, poor accuracy |

## 7. What exists today, against the diagram

The March 2026 orchestrator diagram, node by node:

| node in the diagram | today |
|---|---|
| **user → query** | **missing** — no input channel of any kind |
| **orchestrator** | **missing** — one agent, four tools, no router |
| **data pulling agent** | **exists** — `workflow/tools.py`: `get_chat_window`, `get_transcript_window`, `get_frame_captions`, `group_repeated` |
| **Database → chat messages** | exists (`chat.jsonl`) |
| **→ chat summary** | exists (`report/debrief.py`) |
| **→ stream context** | exists (`transcript.jsonl`) |
| **→ image annotations** | exists (`frames.jsonl`) |
| **→ audio transcriptions** | exists |
| **→ streamer instructions** | **missing** |
| **→ memory** | **missing** — the March build had it, this one does not |
| **save memory agent** | **missing** |
| **scheduling agent** | **missing** |
| **web search agent** | not built |
| **actual stream tools** | half — `report/poll.py` drafts a poll, nothing posts |

Also present now and **not** in the March build: a deterministic grouper that beats the embedding
clustering on the recorded fixtures (`violet ×27`, `para… ×38`, 39–54% of messages folded), a
provenance gate, a frozen 11-case eval, keyless replay from a committed cache, and the board
rendered as a working page.

---

## 8. What I would build next, in order

**0 · Delete the rule the product never had.** Allow a chat message as a trigger when the card
type is a reaction to another viewer, exactly as the 4 Jan hand-check does. Keep the gate for
everything else — the ids must still exist, still fall in the window, quotes still verbatim. One
change, re-run the eval, and the agent's headline number stops being an artefact of our own rule.
**Half a day.**

**1 · Bring memory back.** The March agent answered *"in the last 30 minutes of the stream
memory"*. Rolling summaries at 1m/5m/30m over what the pipeline already writes — no new data
source, and it is the prerequisite for every conversational feature. **Two days.**

**2 · The input channel — «Twinky, …».** Wake-word on the live transcript, which already streams.
The routing target already exists: *"what is chat saying about X"* is `get_chat_window` +
`group_repeated`. The original staging holds: request recognition first, general questions
second. The naming problem is known: when the streamer addresses the bot, it needs a more
explicit word — an Alexa/Alisa-shaped name. "Twinky" may be the product and not the wake word.
**Three days.**

**3 · The orchestrator.** Only once there are two or more real routes. Today one agent with four
tools is honestly enough, and the diagram's shape earns its keep at step 2, not before.

**4 · Streamer instructions.** The box in the diagram nobody has touched, and the one that turns
a dashboard into something a streamer configures: *what to watch for tonight*. It is also what
makes the board personal rather than generic.

**5 · Read the poll out of chat.** It sidesteps the affiliate problem entirely. The card type
already exists — `audience_answer` with a distribution — and the UI already has a slot for it.

Deliberately not next: the web-search agent, the scheduler, giveaways, the streamer social
network, the streamer rating. None are on the path from
`stream → grounded signal → streamer acts`.
