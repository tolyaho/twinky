# Video shot list — capture order, exact commands, and what each shot proves

Max 5:00. Storyboard and generative-footage rules: `../notes/06-VIDEO.md`.

**Every number below was re-measured against the built product on 2026-08-30**, after the board,
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
make test                             # 669 passed — this is also shot 14
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
import json
for line in open('evals/fixtures/stableronaldo_2026-08-30T0723/chat.jsonl'):
    d = json.loads(line)
    if 1788074707878 <= d['ts_ms'] < 1788074767878: print(d['text'])
"
```
**Capture:** the bare list scrolling past — *amethyst, American, amendment, amethysts…*
**Say:** *"Nothing in this list means anything."*

### Shot 3 — the screen that makes it mean something
```bash
grep 1788074707878 evals/fixtures/stableronaldo_2026-08-30T0723/frames.jsonl
```
> The raw JPEG is in the author's tree only — `raw/` is gitignored, so frames and audio are not in
> the repo or the archive. The committed caption is what the system actually reads, and it is the
> reproducible shot. Use `open evals/fixtures/…/raw/frames/1788074707878.jpg` only if you want the
> image on screen and can accept that a judge cannot re-run it.

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

### Shot 7 — Questions, the thing a chat-only system cannot build
Click the **Questions** tab. Switch to the **yugi** fixture.

**Capture:** the flagship row — ***"Yugi how do u feel abt Redify switching u for…"* asked 6
times**, marked answered, with the line the streamer actually said underneath: *"how do you feel
that Reddify switching you for XQC?"*. Then scroll to the unanswered list.

**Say:** *"Whether a question was answered is decided by reading the transcript after it was
asked. A tool that only reads chat has the question and no way to know."*

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

**Point at `get_frame_captions: 2`.** That is the grounding failure as a number, and it sets up
Act 5.

### Shot 10 — live, and it costs nothing (**needs network**)
Switch the toolbar control to **Live**, type a channel that is broadcasting, press **Watch chat**.

**Capture:** the badge flipping to **`LIVE · TIER 0 · $0.00`**, real messages arriving, groups
forming with counts climbing.
**Say:** *"Anonymous IRC, no key, no model call, no cost. And no cause — this tier has no audio
and no screen, so every row is unattributed, and it says so."*

Measured on `#jynxzi`: **168 messages and 6 refreshes in 14 seconds**, 50 unique chatters, groups
forming live. Authors are pseudonymised before they reach the screen, deliberately, because this
is going in a video.

> The badge text comes from the server's own `mode`, never from what the tab thinks. If the
> channel is offline the page says so rather than sitting blank.

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
responses, so timing it measures disk, not the model. Cost is real and small — **$0.43 total**,
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
make test        # 669 passed
```
**Proves:** with `make eval`, a judge reproduces every number in the submission from the committed
cache with no keys. Verified from a clean clone in `/tmp` with `.env` deleted.

---

## Act 5 — what was tried, what failed, the hot take (3:40–4:45)

### Shot 15 — the fix, applied and measured, and it lost
Show `docs/IMPROVEMENT_CHANGELOG.md`, **Removed experiment #2**.

```bash
TS_LLM_MODE=replay python -m evals.run_eval --ablation --grounded --out evidence/grounded
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

## Cut order if you run long

Shot 8 (rail) → shot 12 (trajectory) → shot 2 (raw list). **Never cut shots 4, 5, 11, 15 or 17** —
they are the product, the argument, the measurement, the honest failure, and the take.
