# Creative brief — Twinky submission video

You are the creative director for a 5-minute video. Everything you need is below; assume no
other context. Read the constraints before proposing anything — several obvious ideas are ruled
out for reasons that are not negotiable.

---

## 1. The product

**Twinky** turns an unreadable live Twitch chat into a small number of verified audience signals.
It links each cluster of answers, reactions, questions and warnings to the exact stream moment
that caused it, and shows the evidence.

**The thesis, and the line the whole video exists to land:**

> A chat message is not text. It is a response to something. `10` is meaningless. `10` thirty
> seconds after *"how would you rate this game?"* is a rating. Chat is only interpretable against
> the stimulus that caused it — and the stimulus is in the audio and on the screen, not in the
> chat.

That is why the system is multimodal: not sophistication for its own sake, but the minimum
required for chat to mean anything at all. It ingests three streams simultaneously — chat (via
anonymous IRC), the streamer's speech (Deepgram `nova-3`), and the screen (one captioned frame
every 30 seconds) — and reasons over 60-second windows.

**The unit of output** is a row: *what you said, or what was on screen* → *what the room said
back, grouped by meaning, with counts and the actual messages attached.* Four kinds: an
**answer** (a poll you never created), a **reaction** (timestamped, so it's a clip), an
**unanswered question**, and a **warning**.

**The part that matters most:** a deterministic provenance gate checks every card before it is
shown. Do the cited message ids exist? Do they fall inside the claimed window? Does the quoted
trigger appear verbatim in the transcript? Is the named cause a *chat message*, which would mean
chat explaining chat? Eight failure codes. A card that fails is rejected and counted, not
displayed. **The system refuses to show a cause it cannot prove.** That refusal is the product,
not a limitation of it.

**Who it's for:** a streamer at any real size reads maybe one message in a hundred. They ask
something out loud, five hundred people answer, and they see none of it. Target user is a
just-chatting streamer at home — a normal bedroom, one monitor — not an esports studio.

---

## 2. The honest state of it, which the video must not hide

The pipeline works. The agent on top of it does not, yet:

- **Zero grounded cards** across all three recorded fixtures.
- **~78%** of the agent's cards are rejected by the gate, almost all `E_CIRCULAR_EVIDENCE` —
  the model naming a chat message as the cause of chat.
- On the frozen 11-case evaluation the agent scores **0.500** trigger accuracy against **1.000**
  for a trivial chat-only ablation.

And the best finding in the project came from a failed fix. Feeding the model the window's
speech and frame candidates with their ids made it name a real on-screen event for the first time
ever — 4 frame-grounded triggers where the shipped agent had 0, correctly identifying an
on-screen word game. **It still scored worse**, because abstention collapsed from 5 to 0: handed
a list of candidates it always picked one, and picking one is how a card becomes scoreable and
therefore wrong.

> *"The ablation won by knowing less and saying nothing; this arm lost by knowing more and
> always committing."*

That sentence is the intellectual centre of the submission. A video that shows a product working
perfectly would be worth less than one that shows this.

---

## 3. Real footage that exists and is extraordinary

All of this is genuine captured data, not staged:

- **The word game.** A 3:23 am stream where three people are asleep on camera. There is **zero
  audio in the entire 12-minute capture** — Deepgram returned nothing. An automated overlay shows
  `GUESS THE WORD!` and a partial word `para_`. Chat is brute-forcing it: **38 messages** —
  *parab, parac, parad, paraf, parag, paral, parallel*. A chat-only system sees 38 nonsense
  strings. The frame is the only possible explanation. This is the thesis with no argument
  required, and it is real.
- **`violet × 27`** — 27 people typing the same name within a minute while the streamer is
  mid-sentence asking *"what the fuck is going on?"* Chat is telling him who just walked on
  screen. He cannot see it.
- **The unanswered question.** Streamer says *"don't ever get into drama, it's not worth it."*
  Chat asks *"i thought u loved drama?"* Never answered. Deciding it went unanswered requires the
  transcript, which is why a chat-only system structurally cannot produce this.
- **Reproducibility.** Every published number replays from a committed response cache with **no
  API keys and zero cost**. Total spend on the entire project to date: **$0.43**.

---

## 4. The competition

micro1 Frontier Engineering Challenge. Video **max 5:00**. Scored on: Problem & User Value 15 ·
Agent Solution & Engineering 30 · End-to-End Quality 20 · Measured Improvement 15 ·
Reproducibility 15 · Hot Take 5. Judges sell agent evaluation for a living — they will scrutinise
the evaluation design, the failure analysis and the honesty of the numbers harder than the demo.

---

## 5. Visual language

Light, warm, editorial — deliberately not the dark purple every streaming tool uses.

Canvas `#f5f5f5`, ink `#0c0a09`, hairlines `#e7e5e4`. Display type at **weight 300 only**, never
heavier. Hairline borders instead of shadows. **No saturated accent colour anywhere** — the
primary button is a near-black pill. Pastel orbs (mint, peach, lavender, sky, rose) as blurred
atmosphere behind everything, never behind text. Pill geometry on every badge.

---

## 6. Production constraints — read these before proposing

**Tool:** Dreamina Seedance 2.5. 16:9, 720P, clips of 5–30 seconds, optional "Omni reference"
image for character consistency. Budget is not the limit; time is — the deadline is hours away.

**Four things already failed. Do not propose them again:**

1. **Shot-by-shot with a reference image locked.** The model reproduces the reference and adds
   motion; a *performance arc* across 5 seconds does not happen. Two consecutive shots meant to
   show "relaxed" then "alarmed" came out identical.
2. **"Unreadable text" on a screen.** Produces what looks like a Word document or a terminal.
   Chat has a *shape* — a narrow vertical column of short coloured lines stacking at the right
   edge beside a bright game image. Describe the shape, never "text".
3. **The word "streamer" without constraints.** Produces an esports studio: acoustic wall panels,
   three monitors, a stream deck, a wall-mounted TV. The target user is a bedroom.
4. **Internal states.** "He can't keep up" is not filmable. Physical, external actions are:
   leans in, pulls one headphone off, drags a hand down his face, sits back.

**What did work:** a single unbroken camera move — dolly through the room, arc around the
shoulder, push into the screen. Continuous camera motion is this model's strength. Use it.

**Two hard rules that override any creative idea:**

- **No real person's likeness.** Not IShowSpeed, not any named streamer. The project's fixtures
  are captured from real public broadcasts with chatters pseudonymised — synthesising a
  recognisable streamer would poison the integrity the whole submission rests on, and would
  likely breach the generator's terms.
- **Generated footage may never be cut so it appears to be the product working.** Product proof
  is screen recording, always. Generated material is atmosphere and metaphor only.

---

## 7. What to deliver

1. **A 5-minute structure** — beat by beat with durations, saying for each beat whether it is
   generated footage, screen recording, or a title card, and what it proves.
2. **A hook**, roughly 20–30 seconds: streamer at home, calm → chat floods → he's lost in it →
   cut. It must read as a *story*, not a mood. The current attempt has a beautiful camera move
   and no narrative, which is the exact problem to solve.
3. **Generation prompts** for each generated beat, written for Seedance 2.5, with an explicit
   negative prompt, respecting every constraint in §6.
4. **Narration script** for the whole video. Tight — under 700 words for 5 minutes.
5. **Where the honest failure goes.** The `E_CIRCULAR_EVIDENCE` story and the "knowing less and
   saying nothing" line have to land somewhere, and burying them at the end is a waste.

Ask questions if any of this is ambiguous before writing the prompts.
