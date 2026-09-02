# Twinky — what the project actually is, and what is left to build

Written after re-reading all 1811 lines of the team chat and the images inside it. Every claim
below has a line number or a photo behind it. The hackathon framing is set aside; this is the
project as the three of you described it between September 2025 and April 2026.

---

## 1. The thesis was Kamil's, on day two

**20 Sept 2025, L254–255**, two days after the group was created:

> «Ну контекст из видео не помешал бы / Чтобы понять, когда вопрос к чату, а когда нет»

That is the whole product in one line, and it was said before anything was built. Everything
since — Deepgram, frame captions, the `message_reason` work — is that sentence being taken
seriously.

Tolya's version, **21 Sept, L319**: *«если она видит картинку кски то может понять что авик»* —
vision repairing speech, because ASR mangles game slang.
Karim's addition, **L324**: a slang dictionary built from what chat itself types.

## 2. The goal

**16 Jan 2026, L1590–1596** — Kamil, unprompted, states why any of it matters:

> «Вот мы сделаем как бы чат более доступным / В чат будет интереснее писать / Значит стрим
> интереснее будет смотреть / Он будет более живым / Тогда и просмотров больше должно быть»

and **L1607–1610**:

> «стримеру легче чат читать … Обычно же ты пишешь / И твоё сообщение просто пропадает»

Karim, **L1617**: *«зрители будут видеть, что их сообщение может быть ценным, и не потеряться
относительно флуда»*, and **L1625**: *«любой стример захочет показывать как там разные группы из
кластеризации соревнуются с друг другом по активу»* — the board is meant to go **on stream**,
visible to viewers.

This is a loop, not a feature: readable chat → worth writing in → livelier stream → more views.
The dashboard is the mechanism; the loop is the point.

## 3. Four things the product does — all four are in the chat

**A. Every message gets a cause.** Kamil, **4 Jan, L1336–1355**:

> «Я вот беру сообщение в чате. Смотрю на то, что стример сказал до этого. И пытаюсь выяснить
> причину этого сообщения. … чел написал "10". А стример спросила недавно "Как оцените игру?"»
>
> «чел написал сообщение, а мы уже через секунду поняли и объяснили к чему это сообщение, что
> значит. Это же очень круто, **человек или модер так не сможет**.»

Measured then: **7 s average, 1 s median**, ≈$0.05 per 5 minutes on an active chat, ≈$40/month
for a top streamer, optimisable 4–10×.

**B. Табло — clusters bound to the streamer's own quotes.** **L1422–1443**, the layout drawn by
hand in the chat. Tolya, **L1453**: *«только там иногда кластеры не привязываются ни к чему, это
тож учти»* — **abstention was a product requirement from the first sketch.**

**C. The agent you talk to.** Karim, **3 Oct, L741–743**: *«мы там потом будем среди него искать
команды для помощника»*. Karim again, **24 Nov, L1272–1274**: *«agentic RAG … сначала сделаю хотя
бы распознавание запросов для бота. Потом уже надо будет на general вопросы научиться отвечать»*.
Kamil, **L1275**: *«Давай попробуем просто по слову Ассистент»*. Tolya, **L1184**: *«я буду делать
отдельную вкладку для агента»*.

**D. Polls without affiliate status.** Karim's writeup, **26 Nov, L1285–1302**: native Twitch
polls need affiliate/partner plus a user access token, so a bot with mod rights cannot create
one. Kamil's answer, **L1304–1307**: *«А почему бы просто из чата опрос не парсить тогда? Ну
ответы брать из чата. ДА / НЕТ»* — don't create a poll, **read the one that already happened.**

---

## 4. The agent was built, and it worked

`photo_55`, **13 March 2026** — a real terminal session, `python3 -m agent_rag.run_chat`:

```
you> what is happening on stream right now
agent> Right now on Silky's stream, he is visible in the bottom-left webcam wearing a
       backward cap and headset… The main screen shows a browser with a kanban-style
       dashboard app, Discord on the side… The chat is active with discussions about
       boxing/MMA fighters… The follower goal is at 4181/5000. The stream recently
       resumed from a commercial break…

you> what are some last messages in chat
agent> shumu69: "wht chat gets if u win" / aa1boy: "u just read chat stfu" /
       sr01274: "should read to chat then" / 1drae: "fuck the chat then"

you> do you think my boy Kamilka will crack someone soon
agent> I don't see any recent mentions or discussions about your boy Kamilka … in the
       last 30 minutes of the stream memory.
```

Read that last answer again. It **abstained correctly**, and it did it against a **30-minute
memory window**. Vision, chat, transcript and memory were all live in one conversation.

Tolya's own description, **L1684–1689**: LangChain + LangGraph, Chroma as the vector store, an
ingest process running alongside the chat parser, top-k retrieval per query. Honest about the
state: *«пока есть задержка (в основном эмбеддинги долго делаются) и архитектура совсем никакая,
но это только начало»*, and *«мощностей мака не хватает, он прям горит»*. Then: **«планирую я вот
так»** — and that is `photo_56`, the orchestrator diagram.

**So the conversational agent is not an idea we skipped. It is a thing that ran, five months
ago, and the diagram is its intended second version.**

## 5. The finding that matters most

`photo_51`, **4 Jan** — Kamil hand-checking `message_reason` output. Item 9:

> `"100% ахаахахаха"` → *"Agreeing with another viewer's laughter"* + Quote: `"хуй не взял"`
> — **Корректно**

In the original taxonomy, **reacting to another viewer is a valid, correctly-labelled reason.**
The cause of a chat message is allowed to be another chat message.

The hackathon build forbids exactly that. `E_CIRCULAR_EVIDENCE` — "chat explaining chat" — is
**~78% of all gate rejections** and the single largest reason the agent scores 0.500 against a
trivial ablation's 1.000.

That rule is not a bug in the model. It is a rule we added that the product never had, and it is
throwing away the category the original system handled correctly. Fixing this is the highest-value
change available, and it costs nothing but a decision.

## 6. Decisions the team made that should be kept

| decision | where | keep? |
|---|---|---|
| Real-time, purge freely — *«упор на то, что в моменте происходит»* | L859–861 | **yes** — the debrief is a by-product, not the point |
| Frames yes, video no — too much memory | L1222–1227 | yes |
| `nano` over `mini`: 1–3 s vs 10–30 s | L1675–1678 | yes — latency, not cost, was the reason |
| Deepgram, diarize the streamer, others as person 1/2 | L322–323 | partly — diarisation is enabled and returns one speaker |
| Fixed clusters: emotions, then call-to-action | L1162–1165 | **untried** — worth testing |
| Merge consecutive similar messages into blocks | L1382 | shipped, as the deterministic reducer |
| Embedding clustering | L1646–1656 | **measured and failed** — ~100 clusters, *«с не очень крутой точностью»* |
| No investors — *«а нахуя бабки нам»* | L355–362 | yours to keep |

## 7. What exists today, against the diagram

`photo_56` node by node:

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
clustering on your own fixtures (`violet ×27`, `para… ×38`, 39–54% of messages folded), a
provenance gate, a frozen 11-case eval, keyless replay from a committed cache, and the board
rendered as a working page.

---

## 8. What I would build next, in order

**0 · Delete the rule the product never had.** Allow a chat message as a trigger when the card
type is a reaction to another viewer, exactly as `photo_51` item 9 does. Keep the gate for
everything else — the ids must still exist, still fall in the window, quotes still verbatim. One
change, re-run the eval, and the agent's headline number stops being an artefact of our own rule.
**Half a day.**

**1 · Bring memory back.** The March agent answered *"in the last 30 minutes of the stream
memory"*. Rolling summaries at 1m/5m/30m over what the pipeline already writes — no new data
source, and it is the prerequisite for every conversational feature. **Two days.**

**2 · The input channel — «Twinky, …».** Wake-word on the live transcript, which already streams.
The routing target already exists: *"what is chat saying about X"* is `get_chat_window` +
`group_repeated`. Karim's own staging holds: request recognition first, general questions second.
Note the naming problem you already identified — Tolya, **L1256–1258**: *«когда стример обращается
надо более явное слово»*; Karim, **L1259**: it wants to be an Alexa/Alisa-shaped name. "Twinky"
may be the product and not the wake word. **Three days.**

**3 · The orchestrator.** Only once there are two or more real routes. Today one agent with four
tools is honestly enough, and the diagram's shape earns its keep at step 2, not before.

**4 · Streamer instructions.** The box in the diagram nobody has touched, and the one that turns
a dashboard into something a streamer configures: *what to watch for tonight*. It is also what
makes the board personal rather than generic.

**5 · Read the poll out of chat.** Kamil's L1304 answer, which sidesteps the affiliate problem
entirely. The card type already exists — `audience_answer` with a distribution — and the UI
already has a slot for it.

Deliberately not next: the web-search agent, the scheduler, giveaways, the streamer social
network, the streamer rating. All are in the chat; none are on the path from
`stream → grounded signal → streamer acts`.
