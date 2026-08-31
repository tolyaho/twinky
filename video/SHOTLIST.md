# Video shot list — capture order, exact commands, and what each shot proves

Max 5:00. Storyboard and generative-footage rules: `../notes/06-VIDEO.md`.

**Every number below was re-measured against the built product on 2026-08-30**, and shot 9's
figures again on 2026-08-31 when the diagram gained the step-budget line, after the board,
the rail, the questions panel, Tier 0 live chat and the generated agent graph landed. The previous
version of this file described a two-column page that no longer exists and quoted a test count
that had moved by a hundred. If you are reading it from a print-out, throw the print-out away.

**Capture the real interface first, then generate the hook.** Generating before the cut exists is
how the budget goes on footage that does not fit.

**Rule that outranks the storyboard:** generated shots may never be cut so they appear to be the
product working. Product proof is screen recording, always.

---

## Before you record — one-time setup

```bash
cd ~/Desktop/personal/micro1/ts
make setup PYTHON=python3.12          # or: uv venv .venv && uv pip install -r requirements.txt -e .
make test                             # 723 passed — this is also shot 14
```

Nothing below needs an API key or a network connection **except shot 10**, which is live chat and
says so on camera. Every other command reads the committed cache. To prove that on film, run them
with `env -i PATH=/usr/bin:/bin HOME=/tmp make …`.

`make replay`, `make baseline` and `make demo` now default to the recorded `stableronaldo`
fixture, so you can type them bare. **Set the terminal to a large font before recording** — half
these shots are numbers in a table and they must be legible at 1080p.

---

## Act 1 — the problem (0:00–0:35)

### Shot 1 — hook (generated, 15–25 s)
Per `../notes/06-VIDEO.md`: silhouette, chat reflections, flood, freeze on one unreadable message,
collapse into rows, macro transition into the real interface. **No product claim in generated
footage.**

### Shot 2 — the raw material, unreadable
```bash
python3 -c "
import json, re
for line in open('evals/fixtures/stableronaldo_2026-08-30T0723/chat.jsonl'):
    d = json.loads(line)
    if 1788074707878 <= d['ts_ms'] < 1788074767878 and re.fullmatch(r\"[A-Za-z']{3,20}\", d['text'].strip()):
        print(d['text'])
"
```
**Capture:** the bare list scrolling past — *armament, American, Americans, amendment, americna,
amemetrn, amitturure, amenities…*
**Say:** *"Nothing in this list means anything."*

> **Why this filters to single words, and say so if asked.** The window holds 79 messages, of
> which **69 are one-word guesses** — that is the shot. It is not sanitising: the unfiltered feed
> is on screen throughout shot 4, raw and complete. But message **2 of 79** is `@wetnutsock12
> yeah you're retarded`, and the unfiltered command puts a slur aimed at a named viewer second on
> screen in the first product shot of the submission. Found by running the command rather than
> reading it. If you prefer the unfiltered version, start the capture a few lines in — do not put
> that frame in the cut.

### Shot 3 — the screen that makes it mean something
```bash
grep 1788074707878 evals/fixtures/stableronaldo_2026-08-30T0723/frames.jsonl
```
> **Correction, 2026-08-31.** This note used to say frames "are not in the repo or the archive".
> `raw/` is gitignored, but **four real frames from this capture do ship**, inside
> `video/twinky-image-bank.zip` under `bank/01-real/stream-frames/` — including the hero frame
> `09-30_wordgame_para_.jpg`. The committed caption is still what the system actually reads and is
> still the reproducible shot; the JPEG is now reproducible too.
>
> ⚠ **BLUR THE USERNAME COLUMN BEFORE THIS GOES ON CAMERA.** Those frames have **real Twitch
> logins burned into the overlay**. Every chatter in every fixture is pseudonymised and
> `README.md`, `evals/DATA.md` and each `meta.json` say so — so putting an unblurred frame on
> screen shows exactly what the pipeline is documented as not storing. The warning was written in
> the bank's own `MANIFEST.md`, inside the zip, where nobody reads it at four in the morning. It
> is here now. See `RISKS.md` #52, which is also where the decision about whether that zip should
> ship at all belongs.

**Capture:** the caption naming the on-screen word game.
**Proves:** the thesis in one cut. The cause is on screen or it is nowhere. Nobody is speaking —
there is **no audio to transcribe in this entire 12-minute capture** and Deepgram correctly
returned zero utterances.

---

## Act 2 — the product, running (0:35–2:05)

### Shot 4 — the board, which is the whole product in one frame
```bash
make demo                              # defaults to the recorded stableronaldo fixture
# then open http://127.0.0.1:8000
```
Playback defaults to **4×** because a window is 60 seconds and at 1× the first row is a minute
away.

The middle column carries a one-line answer to *what is a row here* that follows the active tab —
*"what was said or shown → what the room said back, grouped, with the messages behind it"*. Let it
be readable in the frame before anything moves; it is the fastest orientation the page gives.

**Capture, in this order:**
1. **The live counts appearing within seconds** — the dashed *"this minute so far · counting · no
   cause assigned yet"* block, with counts ticking up as chat arrives. Grouping calls no model, so
   it runs every two seconds. **Measured: the first row appears at 2.0 s on marlon and 10.0 s on
   stableronaldo**, against a 60-second window close.
2. **A row landing with its cause.** On stableronaldo window 0 the top row is `screen · names it`
   over the caption that contains the guessed word `ranger`, with **`rang… × 20`** under it.
3. **Click the row.** The messages behind it light up in the chat feed on the left. That is the
   gesture the product rests on — do not narrate over it, let it land.
4. The footer: **`163 messages · 2 rows · 75 singletons not shown`**.

**Say:** *"Two rows out of a hundred and sixty-three messages, and it tells you what it threw
away."*

> **How long you can let the feed run.** The chat panel is genuinely unfiltered — that is the
> point of the left column — so it will eventually show what live chat shows. Measured across the
> fixtures: `marlon_2026-08-30T0715` is **clean over all 1535 messages**, `yugi` has 2 in 625, and
> `stableronaldo` has 6 in 1288. On stableronaldo, **window 0 is clean and the first one arrives
> at +102 s** (windows 1, 2, 7 and 11). So shot 4 is safe for its first hundred seconds, which is
> comfortably past the first board row at ~56 s. **Shot 5's fixture is clean throughout**, so
> dwell there as long as you like.

### Shot 5 — the row that is the argument
Switch the channel chip to **marlon**, window 6.

**Capture:** the top row — speech, *"Hey, man. They're coming for you, bro… What the fuck is going
on?"* → **`violet × 27`**, with three verbatim messages under it: *"violet murders?"*,
*"VIOLET MYERS"*, *"VIOLET."* Footer: **`237 messages · 4 rows · 123 singletons`**.

**Say:** *"He is mid-sentence asking what is going on. Twenty-seven people already answered, a
minute ago, and he cannot see it."*

Under each group is a **one-line meaning** — the only model call anywhere in the reporting layer,
one batched call per window, recorded and replayed for nothing. Say once, over it: *"That line is
cosmetic. The count, the messages and the ids under it are what the row stands on, and the gate
never reads the caption."* If a window has no recorded label the row shows the token instead and
nothing breaks — that is deliberate.

**Note the honest label on camera if you have the second:** that row says `just before`, not
`names it` — the link is adjacency, not proof. The board distinguishes the two and so should you.

### Shot 6 — Signals, and the gate throwing work away
Click the **Signals** tab in the middle column.

**Capture:** the finding line at the top — *"No card in this run names a cause the gate could
stand behind. N rejected; E_CIRCULAR_EVIDENCE accounts for M; K abstained"* — then a card, its
**cited messages shown verbatim**, and the cause line reading `speech · 04:12` rather than a uuid.

**Say this, do not skip it:** *"Most of what the agent produced did not survive its own provenance
gate. That is the system working, and it is also the result — I will come back to it."*

**Then click the offer in that line** — *"see the baseline on this window"* — and let it land. It
is not an empty gesture: the agent grounds **nothing** on any recorded fixture and the baseline
grounds something on all three. Measured from the recorded runs:

| fixture | agent | baseline |
|---|---:|---:|
| stableronaldo | 0 grounded · 5 abstained · 19 rejected | **2 grounded** · 13 · 8 |
| marlon 0715 | 0 grounded · 3 abstained · 20 rejected | **1 grounded** · 3 · 20 |
| yugi | 0 grounded · 0 abstained · 21 rejected | **6 grounded** · 3 · 26 |

One click turns the honest failure into the honest comparison, on screen, with no editing.

### Shot 7 — Questions, the thing a chat-only system cannot build
Click the **Questions** tab. Switch to the **yugi** fixture.

**Capture:** the flagship row — ***"Yugi how do u feel abt Redify switching u for…"* asked 6
times**, marked answered, with the line the streamer actually said underneath: *"how do you feel
that Reddify switching you for XQC?"*. Then scroll to the unanswered list.

**Say:** *"Whether a question was answered is decided by reading the transcript after it was
asked. A tool that only reads chat has the question and no way to know."*

Every row carries its timestamps: when it was asked, and — if answered — when you answered it.
On yugi, *"why violet myers at the party"* is **asked at 0:56 and answered at 1:04**, eight
seconds later, which a viewer can go and check. On the unanswered list the asked time is the
actionable half: a point to go back to.

Measured on yugi: **38 questions, 45 asked, 2 answered.** On marlon the top unanswered question is
`violet murders?`, **asked 14 times and never picked up**.

### Shot 8 — the right rail
**Capture:** the rail while playback runs — rate sparkline, unique chatters, **top-10% share**,
composition, and the **gate ledger by code**.

**Say:** *"Whether five hundred messages is five people or five hundred is a completely different
fact, and the raw count hides it."*

On stableronaldo the rail reads **`silent window`** — zero speech segments. That is a finding
about the stream, not a hole in the data, and the rail says so.

---

## Act 3 — how it works (2:05–2:45)

### Shot 9 — the agent graph
Open `http://127.0.0.1:8000/method` and scroll to **02 — how it works**.

**Capture:** the diagram, holding on the tool call counts.
**Say:** *"Two dashed boxes. Those are the only places a model is involved. Everything else is
arithmetic you can re-run. And this picture is generated from the code — the tool list, the
controller's bounds, the gate's eight card checks and two abstention checks, and the call counts
from a hundred and eighteen recorded runs. A test fails if it stops matching."*

**Point at `get_frame_captions: 2`,** then at the line under the tool column: **`51 of 59 runs
spent 1 of their 4 steps` / `and the one step was chat`.**

**Say:** *"Fifty-nine of those runs could call a tool at all — the rest are baselines with no
tools. Fifty-one of them used one step out of four, and spent it on chat. That is the failure in
Act 5, before it happens: the agent doesn't look."*

The two numbers do different work. `get_frame_captions: 2` says it never read the screen; the
line beneath says that wasn't a budget problem — it had three steps left every time.

### Shot 10 — live, and it costs nothing (**needs network**)
Switch the toolbar control to **Live**, type a channel that is broadcasting, press **Watch chat**.

**Capture:** the badge flipping to **`LIVE · TIER 0 · $0.00`**, real messages arriving, groups
forming with counts climbing.
**Say:** *"Anonymous IRC, no key, no model call, no cost. And no cause — this tier has no audio
and no screen, so every row is unattributed, and it says so."*

Measured on `#jynxzi`: **168 messages and 6 refreshes in 14 seconds**, 50 unique chatters, groups
forming live. Authors are pseudonymised before they reach the screen, deliberately, because this
is going in a video.

> The badge text comes from the server's own `mode`, never from what the tab thinks.
>
> **Pick a channel that is actually broadcasting.** Tier 0 joins anonymous IRC either way, so an
> offline channel connects and then says nothing. After 12 seconds the page states that outright
> — *"connected to #x, and it has sent nothing in 12 seconds; the channel is probably offline"* —
> which is a fine thing to have on screen but not the shot. Verified on the day: `jynxzi` was
> offline and returned 0 messages in 9 seconds while `caseoh_` returned 30.

---

## Act 4 — the measured comparison (2:45–3:40)

### Shot 11 — reproduce the results table on camera
```bash
make eval
cat evidence/report.md
```
**Capture:** the run finishing on `cache: {'hits': 48, 'misses': 0}`, then the table.

| system | cards | trigger accuracy | unmatched | unsupported | recall |
|---|---:|---:|---:|---:|---:|
| agent | 23 | **0.500** | 0.913 | 0.739 | **0.182** |
| baseline | 21 | 0.000 | 0.952 | **0.619** | 0.091 |
| ablation (chat only) | 25 | 1.000 | 0.960 | **0.280** | 0.091 |

**Say both halves:** *"The agent doubles the baseline's recall and is the only system that names a
correct cause. It also has the worst unsupported-card rate of the three. I am reporting both."*

**Do not put latency on screen.** It is deliberately not measured: a replay run reads cached
responses, so timing it measures disk, not the model. Cost is real and small — **$0.44 total**,
itemised in `COST_LEDGER.md`.

### Shot 12 — the trajectory
```bash
open trajectories/product-agent/c01_word_puzzle_amethyst_trc_13ffd83b.json
```
**Capture:** the steps — instructions, tool call, tool result, gate decision.
**Proves:** **118 trajectories**, written as the run happens rather than reconstructed. Trace ids
derive from `(agent, case_id)`, so they are stable across re-runs — a deliberate fix, not luck.

### Shot 13 — the diagnosis, from the cache itself
**Say:** *"The contract tells the model a trigger must be a speech or screen id, and that it may
only cite ids it actually saw. I went and counted what it was shown. All fifty-seven of the
agent's own opening turns contain zero event ids. Across seventy recorded conversations, chat
appears in seventy and frame captions in two. In ninety-seven percent of them the only ids the
model had ever seen were chat ids — so naming a chat message was the only move available. That is
not a disobedient model. That is a missing input."*

### Shot 14 — reproducibility, the pre-scoring gate
```bash
make test        # 723 passed
```
**Proves:** with `make eval`, a judge reproduces every number in the submission from the committed
cache with no keys. Verified from a clean clone in `/tmp` with `.env` deleted.

---

## Act 5 — what was tried, what failed, the hot take (3:40–4:45)

### Shot 15 — the fix, applied and measured, and it lost
Show `docs/IMPROVEMENT_CHANGELOG.md`, **Removed experiment #2**.

```bash
TS_LLM_MODE=replay .venv/bin/python -m evals.run_eval --ablation --grounded --out evidence/grounded
```
**Capture:** `70 hits, 0 misses` — the negative result reproduces with no keys — then the table.

**Say:** *"So I supplied the candidates. Same schema, same gate, same scorer, as a second recorded
arm so nothing published moved. It named four frame captions where the agent had named zero — the
failure I just showed you, fixed. And it lost: same recall, worse unsupported rate. Handed a list
of candidates it stopped abstaining entirely — zero abstentions against the agent's five — and
picking one is how a card becomes scoreable and therefore wrong. That cost twelve-tenths of a
cent and it is in the changelog as a removed experiment with a measured result."*

This is the strongest 40 seconds in the video. It is a diagnosis, a fix, a measurement, and a
refusal to adopt something that did not work.

### Shot 16 — biggest contributor
Show the competition-iterations table.
**Say:** *"The largest single contributor was not a clever feature. The baseline had been handed
the agent's tool-calling prompt, so it replied with a tool call, the parser turned that into an
empty list, and it scored zero cards across eleven cases. Fixing that is what made a comparison
exist at all."*

### Shot 17 — hot take
**Say:** *"The chat-only ablation — the system with the least information — won the headline
metric. It won by abstaining: with no transcript and no captions it had no cause to name, so it
said `unknown` eighteen times out of twenty-five, and an abstention is always gate-clean. An
unsupported-card rate is minimised by saying nothing. That is not a broken metric, it is the shape
of the problem. Grounding is not summarization with a better prompt; it is retrieval and proof,
where the honest answer is often 'I cannot show you the cause.'"*

---

## Act 6 — close (4:45–5:00)

### Shot 18 — the reproduction command, held on screen
```bash
git clone <repo> && cd ts
make setup PYTHON=python3.12
make test && make eval
```
**Say:** *"No API keys. Three commands. Every number in the submission."*

---

## Continuity checklist before you cut

- [ ] Every number spoken matches `evidence/report.md`. Re-run `make eval` if in doubt.
- [ ] No generated footage is adjacent to a product claim without a visible cut.
- [ ] The rejected cards are shown and explained, not cropped out.
- [ ] Both halves of the result are stated: the agent wins recall, loses unsupported rate.
- [ ] The grounded arm is described as **tried, measured and not adopted** — never as shipped.
- [ ] A board row labelled `just before` is not narrated as a proven cause.
- [ ] Tier 0 is described as having no cause to give, not as a reduced version of the real thing.
- [ ] Latency does not appear anywhere.
- [ ] The poll-draft beat is either cut or named as a gap — never staged. See RISKS #42.
- [ ] Gold labels are described as model-drafted and unconfirmed if labels are mentioned at all.
- [ ] Runtime ≤ 5:00.

## The image bank, and the one still you must not cut

`video/twinky-image-bank.zip` holds 30 assets in four folders with a `MANIFEST.md` explaining
each. Two things about it belong out here rather than inside the archive:

1. **`01-real/stream-frames/` are real captured frames with real logins visible.** Blur before
   use. See shot 3 and `RISKS.md` #52.
2. **`02-product-stills/11_reproducibility.png` is stale.** It reads *"48 hits / 0 misses · 530
   tests · $0.43"*. The suite is at **723** and the ledger at **$0.4364**, so cutting that still
   puts a number on screen that shot 14 contradicts thirty seconds later with `make test` running
   live. The manifest says to re-render rather than retouch — but its generator, `build_bank.py`,
   **is not committed**, so re-rendering is only possible if the author still has it. If not:
   **do not cut that still.** Every other figure in the bank was checked against the fixtures
   when it was built and no other still carries a test count or a total.

The manifest's own usage rule is worth repeating because it is the one a judge would most easily
catch you breaking: `02-product-stills/` and `03-titles/` are **renderings you authored**, not
screen recordings. Cut them as graphics. When the video says *"here is the product running"*,
that footage must be an actual recording of `make demo`.

## If you are short on HOURS, not minutes

The cut order below is for a video that runs long. This section is for the other problem: not
enough time to shoot eighteen setups. Written at T-8h with nothing filmed.

**There are only two takes here, not eighteen.**

| take | shots | surface | notes |
|---|---|---|---|
| **A — one browser session** | 4, 5, 6, 7, 8, 9 | `make demo`, then `/method` | Start the server **once** and never restart it. Every one of these is a click inside the same page: channel chips, the Board/Signals/Questions tabs, then the Method page. Switching fixtures mid-playback once killed the server (P0 1.2); it is fixed and tested, but a single unbroken session is still the safest recording |
| **B — one terminal** | 11, 12, 13, 14, 15, 18 | a large-font terminal | All of them read the committed cache. Nothing here needs a key or a network |

Everything else is optional in the sense that matters — a judge scoring the required deliverable
will not miss it:

1. **Shot 1, the generated hook.** Costs the most wall-clock of anything in this file, because
   generating footage means iterating on it. Open on shot 4 instead, or a plain title card.
   **Drop this first.**
2. **Shot 10, live Tier 0.** The only shot that needs a network *and* a channel that happens to
   be broadcasting when you press record. It can simply fail on the day. Its claim — keyless,
   free, and honest about having no cause to give — is already in `README.md` and on the page.
   **Drop this second.**
3. **Shots 16 and 17** are talking to camera and need no setup, so they cost only their runtime.

**The floor.** If everything goes wrong, shots **4, 5, 11, 15, 17** and a close still make a
complete submission: the product working, the row that is the argument, the measurement
reproduced on camera, the fix that was tried and lost, and the take. That is takes A and B with
most of each thrown away, and it is well under five minutes.

**Do not spend the saved time on polish.** A rough five-minute video that exists scores; a
beautiful one that does not exist scores nothing.

## Cut order if you run long

Shot 8 (rail) → shot 12 (trajectory) → shot 2 (raw list). **Never cut shots 4, 5, 11, 15 or 17** —
they are the product, the argument, the measurement, the honest failure, and the take.
