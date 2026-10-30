# Product thesis

These sections were the opening of `README.md` until the README was restructured around what is
built and measured. The longer write-up, including the March 2026 agent, is in `PRODUCT_v2.md`.

Twinky aims to turn an unreadable live chat into audience signals with inspectable evidence.
The prototype proposes links between chat and stream context. Its deterministic gate checks
citations and timing; it does not prove semantic causality. The live session boundary is
documented in [LIVE_DEMO_INTEGRATION.md](LIVE_DEMO_INTEGRATION.md).

A chat message is not text. It is a response to something. `10` is meaningless; `10` thirty
seconds after *"how would you rate this game?"* is a rating. Chat is only interpretable against
the stimulus that caused it — and the stimulus is in the audio and on the screen, not in the chat.

## 1. The thesis

The idea was there two days into the project, in September 2025, before anything was built:
without context from the video you cannot tell whether a question is aimed at chat or not.
Everything since is that sentence taken seriously: speech and frames are not enrichment, they
are the only thing that makes a chat message mean anything.

Two corollaries followed and were kept: vision repairs speech, because ASR mangles game slang —
*«если она видит картинку кски то может понять что авик»* — and the slang dictionary worth having
is the one chat itself types.

## 2. The loop this serves

The goal is not a feature, it is a flywheel, stated in January 2026:
**readable chat → worth writing in → livelier stream → more views.** The board is the mechanism;
the loop is the point. The streamer's half is that chat becomes easier to read; the viewer's
half is that a message can matter instead of getting lost in the flood — which is why the board
is designed to go **on stream**, visible to viewers, not into a private operator console.

## 3. What the product does — four things

**A · Every message gets a cause.** Take a message, look at what the streamer said just before
it, and work out why it was written — in seconds, which a human moderator cannot do at that
rate. Measured in Jan 2026 at 7 s average and 1 s median per message.

**B · The board — clusters bound to the streamer's own quotes.** Sketched by hand in Jan 2026,
including the requirement that has been in the product from the first drawing: *«только там
иногда кластеры не привязываются ни к чему»* — **abstention is a feature, not a failure.**

**C · An agent you talk to.** Query the stream in natural language. Built and working in March
2026 on top of retrieval over the running transcript; not yet rebuilt on this codebase — see
"What is not built yet" in the README.

**D · Polls read out of chat, not created in it.** Native Twitch polls need affiliate status and
a user access token, so a moderator bot cannot open one. The answer was to stop trying: don't
create a poll, **read the one that already happened** in chat. `src/ts/report/poll.py` drafts
one; nothing posts it.

## 4. Real time, not archive

This is a real-time product. Almost nothing has to be stored, because the point is what is
happening in the moment — the post-stream debrief is a by-product of work already done live,
not the reason the system exists.
