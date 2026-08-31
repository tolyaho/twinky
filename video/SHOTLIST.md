# Video shot list — capture order, exact commands, and what each shot proves

Max 5:00. Storyboard and generative-footage rules: `../notes/06-VIDEO.md`.

**Capture the real interface first, then generate the hook.** Generating before the cut exists is
how the budget goes on footage that does not fit.

**Rule that outranks the storyboard:** generated shots may never be cut so they appear to be the
product working. Product proof is screen recording, always.

---

## Before you record — one-time setup

```bash
cd ~/Desktop/personal/micro1/ts
make setup PYTHON=python3.12          # or: uv venv .venv && uv pip install -r requirements.txt -e .
make test                             # 433 passed — this is also shot 12
```

Nothing below needs an API key or a network connection. Every command reads the committed cache.
If you want to prove that on camera, run them with `env -i PATH=/usr/bin:/bin HOME=/tmp make …`.

**Set the terminal to a large font before recording.** Numbers in a table are the point of half
these shots and they must be legible at 1080p.

---

## Act 1 — the problem and the baseline (0:00–0:40)

### Shot 1 — hook (generated, 15–30 s total)
Per `../notes/06-VIDEO.md`: silhouette, chat reflections, flood, freeze on one unreadable message,
collapse into three cards, macro transition into the real interface. **No product claim in
generated footage.**

### Shot 2 — the raw material, unreadable
```bash
python3 -c "
import json
for i, line in enumerate(open('evals/fixtures/stableronaldo_2026-08-30T0723/chat.jsonl')):
    d = json.loads(line)
    if 1788074707878 <= d['ts_ms'] < 1788074767878: print(d['text'])
"
```
**Capture:** the bare list scrolling past — *amethyst, American, amendment, amethysts, driven…*
**Proves:** as text these are noise. Say the line: *"Nothing in this list means anything."*

### Shot 3 — the screen that makes it mean something
```bash
open evals/fixtures/stableronaldo_2026-08-30T0723/raw/frames/1788074707878.jpg
```
> Only available in the author's working tree — `raw/` is gitignored, so raw frames and audio are
> not in the repository or the archive. Committed instead is the derived caption, which is what
> the system actually reads. If you prefer a shot a judge could reproduce, use that:
> `grep 1788074707878 evals/fixtures/stableronaldo_2026-08-30T0723/frames.jsonl`

**Capture:** the frame — three people asleep at 3:25 am, overlay reading `GUESS THE WORD!` and
`ame_______`.
**Proves:** the entire thesis in one cut. The cause is on screen or it is nowhere. Nobody is
speaking; there is **no audio to transcribe in this whole 12-minute capture**, and Deepgram
correctly returned zero utterances.

### Shot 4 — the fair baseline, stated not implied
Show `README.md` §3 on screen, highlighting *"the same raw events … same output schema and the
same card cap."*
**Proves:** the comparison is not rigged. The chat-only run is a separate diagnostic, never the
headline.

---

## Act 2 — one realistic execution, start to finish (0:40–2:20)

### Shot 5 — the deterministic reducer
```bash
make inspect FIXTURE=evals/fixtures/stableronaldo_2026-08-30T0723
```
**Capture:** the JSON output, holding on `compression_ratio`.
**Proves:** understanding the event once and aggregating reactions to it, rather than paying for
inference per message. This is the January 2026 cost finding turned into a component.

### Shot 6 — the agent run, no keys, no network
```bash
make replay FIXTURE=evals/fixtures/stableronaldo_2026-08-30T0723
```
**Capture:** the final line — `"cache": {"hits": 29, "misses": 0}`.
**Proves:** reproducible with zero API calls. Say it out loud: *"That ran with no API key."*

### Shot 7 — the dashboard
```bash
make demo FIXTURE=evals/fixtures/stableronaldo_2026-08-30T0723
# then open http://127.0.0.1:8000
```
**Capture, in this order:**
1. The card rail — 13 windows, **5 verified**, **19 rejected**.
2. Open the evidence drawer on a verified card: the actual chat messages it cites.
3. Open a card whose trigger is `unknown` — the honest abstention, labelled as such.
4. Scroll to the **rejected block** and open one. Show the violation code, e.g.
   `E_CIRCULAR_EVIDENCE`.

**Proves:** every claim is inspectable, and the gate is visibly throwing work away.

**Say this on camera, do not skip it:** *"Most of what the agent produced did not survive its own
provenance gate. That is the system working, and it is also the result — I will come back to it."*
Showing 19 rejections and narrating it as success would be the dishonest cut.

### Shot 8 — the post-stream artifact
```bash
make debrief FIXTURE=evals/fixtures/stableronaldo_2026-08-30T0723
open evidence/raw-results/stableronaldo_2026-08-30T0723.debrief.md
```
**Capture:** the rendered document, holding on the reaction-wave section.
**Proves:** the second half of the product — the record survives after Twitch deletes the VOD.
No model call is made here; it reorganises cards that already passed the gate.

> **⚠ The storyboard's "approve → draft poll" beat cannot be filmed.** The action is implemented
> (`src/ts/report/poll.py`), unit-tested, and wired into the dashboard, but **no card in any
> recorded run carries a `distribution`**, so `build_draft` correctly returns `None` and no draft
> is attached. Either cut the beat, or show it as a named gap. **Do not hand-write a card to make
> the button appear** — see RISKS #42.

---

## Act 3 — architecture, only as it maps to what was shown (2:20–3:00)

### Shot 9 — the diagram
Show `docs/ARCHITECTURE.md`.
**Proves:** every ticked node has a file behind it, and the one unbuilt node — the 1m/5m/30m/2h
summary hierarchy — is **marked as a gap**, not quietly omitted. A test enforces that.

### Shot 10 — one trajectory
```bash
ls trajectories/product-agent/ | head
open trajectories/product-agent/c01_word_puzzle_amethyst_trc_13ffd83b.json   # audience_signal_agent
```
> Three files share that case id, one per system. `trc_13ffd83b` is the agent; `trc_13e23152` is
> the single-prompt baseline and `trc_6d7054b6` the chat-only ablation. Trace ids are derived from
> `(agent, case_id)`, so they are stable across re-runs — that was a deliberate fix, not luck.
**Capture:** scroll through the steps — instructions, tool call, tool result, gate decision.
**Proves:** 33 real trajectories, 11 cases × 3 systems, written as the run happens rather than
reconstructed afterwards.

---

## Act 4 — the measured comparison (3:00–3:50)

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
responses, so timing it measures disk, not the model. Cost is real and small — **$0.42 total**,
itemised in `COST_LEDGER.md`.

### Shot 12 — reproducibility, the pre-scoring gate
```bash
make test        # 433 passed
```
**Proves:** with `make eval` above, a judge reproduces every number in the submission from the
committed cache with no keys. Verified from a clean clone in `/tmp` with `.env` deleted.

---

## Act 5 — changelog, failure, hot take (3:50–4:45)

### Shot 13 — biggest contributor
Show `docs/IMPROVEMENT_CHANGELOG.md`, the competition-iterations table.
**Say:** *"The largest single contributor was not a clever feature. The baseline had been handed
the agent's tool-calling prompt, so it replied with a tool call, the parser turned that into an
empty list, and it scored zero cards across eleven cases. Fixing that is what made a comparison
exist at all. Every other number is downstream of it."*

### Shot 14 — the removed experiment, with its measured result
Show the removed-experiments table.
**Say:** *"We suspected the sleep-stream audio was too quiet to transcribe, so we amplified it by
28 dB and re-ran. Zero additional transcript segments — exactly as before. That turned a suspected
pipeline bug into a verified property of the fixture, and it is why that capture became the
strongest case in the set."*

### Shot 15 — main failure mode, with the receipt
```bash
open trajectories/product-agent/c01_word_puzzle_amethyst_trc_13ffd83b.json
```
**Capture:** the agent's tool calls — `group_repeated`, then `get_transcript_window` — and then
its answer.
**Say:** *"On the very case I opened with, the agent found no speech and returned 'no clear speech
or on-screen content detected' — without ever calling `get_frame_captions`. It declared the screen
empty without looking at it. The obvious fix is one line of prompt, and I did not apply it,
because changing a prompt after seeing the score invalidates the comparison."*

### Shot 16 — hot take
**Say:** *"The chat-only ablation — the system with the least information — won the headline
metric. It won by abstaining: with no transcript and no captions it had no cause to name, so it
said `unknown` eighteen times out of twenty-five, and an abstention is always gate-clean. So an
unsupported-card rate is minimised by saying nothing. That is not a broken metric, it is the shape
of the problem. Grounding is not summarization with a better prompt; it is retrieval and proof,
where the honest answer is often 'I cannot show you the cause.'"*

---

## Act 6 — close (4:45–5:00)

### Shot 17 — the reproduction command, held on screen
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
- [ ] The 19 rejected cards are shown and explained, not cropped out.
- [ ] Both halves of the result are stated: the agent wins recall, loses unsupported rate.
- [ ] Latency does not appear anywhere.
- [ ] The poll-draft beat is either cut or named as a gap — never staged.
- [ ] Gold labels are described as model-drafted and unconfirmed if labels are mentioned at all.
- [ ] Runtime ≤ 5:00.
