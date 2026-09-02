# Reset — from a hackathon submission back to ts

Read this whole file before deleting anything. **This is a reframe, not a purge.** Most of what
was built in those three days is the product; only the scaffolding around it is competition-shaped.

Work from `PRODUCT_v2.md` — it is the product definition this repo should now serve.

---

## 0 · Two things to do BEFORE deleting a single file

**0a · Find `agent_rag`.** `photo_55` shows it running: `tolya@MacBook-Pro-Dang twitch_agent %
PYTHONPATH=src python3 -m agent_rag.run_chat`. **It is not in this repository.** It is in the
`twitch_agent` repo — LangChain + LangGraph + Chroma, an ingest process beside the chat parser,
top-k retrieval per query, and a working 30-minute memory window. That is the most valuable
missing code in the project and the whole point of the next phase.

Locate it, copy it in under `reference/agent_rag/`, and record in `DECISIONS.md` what state it is
in. **Do not start the cleanup until this is done or confirmed lost.**

**0b · Tag the submission.** It is public and it was judged; do not rewrite that history.

```bash
git tag -a micro1-submission -m "micro1 Frontier Engineering Challenge, 31 Aug 2026"
git push origin micro1-submission
```

Everything after this is a normal commit on `main`, not a rewrite.

---

## 1 · `legacy/` is not legacy any more — rename it to `reference/`

Look at what is in there against `photo_56`:

| `legacy/src/parsers/…` | what it is in the diagram |
|---|---|
| `chat_summaries/` (builder, llm, prompts) | **memory** — the rolling-summary hierarchy |
| `context/` (parser + 3 prompts) | **stream context** |
| `image_annotations/` (parser, workers) | **image annotations** |
| `message_reasons/prompts/general.txt` | **the reason taxonomy `photo_51` validated by hand** |
| `models/` (chat, audio, context, image_annotations, chat_summaries) | the Database boxes, one for one |

This is the reference implementation of half the target architecture. `git mv legacy reference`,
rewrite its README to say what it is *for* — not "pre-existing work, do not touch" — and delete
the `NIGHT_LOOP` rule that forbade reading it.

---

## 2 · Delete — competition scaffolding, nothing else

In the repo root:

```
SUBMISSION.md
docs/PRE_EXISTING.md          # the pre/post 28-Aug split exists only for judging
video/                        # SHOTLIST.md, HOOK.md, VIDEO_BRIEF.md, clips/, press/
scripts/preflight.py          # submission checklist
run-night.sh
COST_LEDGER.md                # → see §3, it becomes a real budget file
```

In `micro1/` above the repo — all of it. These were briefs written for the loop and they are
obsolete:

```
README.md (the challenge guide)   LOOP_PROMPT.md   NIGHT_LOOP.md   night/   collect/
FIX_GROUNDING_AND_UI.md   LIVE_AND_PHILOSOPHY.md   WHAT_WE_SHOW.md   DASHBOARD.md
WINDOWS.md   LOOP_FINAL.md   FEATURES_V2.md   GROUNDING.md   AGENT_FIX.md
RECORD_THEN_FIX.md   RENAME.md   DESCRIPTION.md   description.html
notes/05-AUDIENCE_NOTES.md   notes/06-VIDEO.md   notes/07-SITE.md   notes/08-SUBMISSION.md
```

**Keep `PRODUCT_v2.md`** — it moves into the repo as the product definition.
**Keep `notes/01-PRODUCT.md` … `04-CODE_AUDIT.md`** for now; they get rewritten in §4.

Then move the project out from under the competition's name:

```bash
git mv <repo>/ts  ~/Desktop/personal/twinky      # or wherever it should live
```

The python package stays `ts`. Renaming it touches every import and every documented command and
buys nothing; the repo is already `twinky`.

## 3 · Rewrite, do not delete

| file | what changes |
|---|---|
| `README.md` | drop the rubric framing, the judge instructions, the reproduce-for-scoring pitch. Lead with the thesis and the flywheel from `PRODUCT_v2.md` §1–2 |
| `docs/IMPROVEMENT_CHANGELOG.md` | keep every measurement. Drop "iteration N of the competition"; it becomes an engineering log |
| `docs/REPRODUCTION.md` | keep entirely — running from a committed cache with no keys is a *good property of the project*, not a competition trick |
| `docs/ARCHITECTURE.md` | rewrite against `photo_56`, marking each node built / partial / missing |
| `CLAUDE.md` | drop the deadline, the rubric, the "never add a second agent" rule — that rule expires with the competition |
| `RISKS.md` | keep the security and privacy entries (**#53, real logins in message text, is still open**), delete the submission-gate ones |
| `COST_LEDGER.md` | keep the format, drop the $5 hackathon cap. Real numbers now: Kamil measured ≈$40/month per top streamer at 7s/message, optimisable 4–10× |
| `PROGRESS.md`, `DECISIONS.md` | **archive, do not delete** — `docs/archive/`. 100 KB of real reasoning, including why embeddings were dropped and why the injected-candidates arm failed |

## 4 · Rewrite the notes from the chat, not from the rubric

`notes/01-PRODUCT.md` currently leads with "the invariant" and a second thesis about Twitch
deleting VODs. Replace with `PRODUCT_v2.md` §1–3: the thesis is Kamil's from **20 Sept, L254**,
the goal is the flywheel from **16 Jan, L1590**, and the product is four things — message reason,
the board, the agent you talk to, and the poll read out of chat.

Delete the VOD-expiry thesis. It was invented for the submission and it contradicts **L859–861**:
*«Как круто, что нам почти ничего хранить не надо … Мы же делаем упор на то, что в моменте
происходит»*.

`notes/03-EVAL_DESIGN.md` stays. The 11 frozen cases and the scorer are the most valuable thing
that came out of those three days, and they are how you will know whether any of the next changes
help.

## 5 · Keep, and know why

Do not touch any of this:

- **`evals/fixtures/`** — irreplaceable. Real captures that cannot be re-recorded.
- **`cache/llm/`** — paid for, and the reason anything replays for free.
- **`evals/` + `evidence/`** — the frozen cases, the scorer, and the measured baseline. Every
  future change is judged against `evidence/report.md`.
- **`src/ts/ingest/`** — keyless capture, Deepgram, vision. This *is* the product's front door.
- **`src/ts/workflow/reduce.py`** — the prefix + token grouper. It beats the embedding clustering
  that was measured and abandoned on 5 March (**L1646–1656**, ~100 clusters, poor accuracy).
- **`src/ts/report/`** — the board, the questions panel, the rail. Kamil's табло from **L1422**,
  finally on screen.
- **`src/ts/provenance.py`** — the gate, minus one rule; see §6.
- **`tests/`** — 729 of them. They are why the next refactor is survivable.
- **`trajectories/`** — as a debugging tool now, not a deliverable.

## 6 · The one behaviour change to make while you are in here

`E_CIRCULAR_EVIDENCE` forbids a chat message from being the cause of a chat message. It is **~78%
of all gate rejections** and the main reason the agent scores 0.500 against a trivial ablation's
1.000.

The product never had that rule. `photo_51` item 9 — Kamil hand-checking output on 4 Jan:

> `"100% ахаахахаха"` → *"Agreeing with another viewer's laughter"* + Quote `"хуй не взял"` —
> **Корректно**

Reacting to another viewer is a valid reason in the original taxonomy, and
`reference/src/parsers/message_reasons/prompts/general.txt` is where that taxonomy is written
down. Read it before changing the gate.

Allow a chat trigger **for reaction-type cards only**, keep every other check — ids exist, inside
the window, quote verbatim, no card citing itself — and re-run `make eval`. Record the before and
after. This is a product decision being corrected, so it belongs in `DECISIONS.md` with the photo
reference, not as a quiet threshold change.

## 7 · Done when

- `make test` green, `make eval` still reproduces `evidence/report.md` byte-identically **before**
  the §6 change, and a new recorded number after it.
- No file in the tree mentions micro1, HackerEarth, the rubric or the deadline, except
  `docs/archive/` and the `micro1-submission` tag.
- `README.md` opens with the thesis and the flywheel.
- `docs/ARCHITECTURE.md` shows `photo_56` with each node marked built / partial / missing.
- `reference/agent_rag/` exists, or `DECISIONS.md` records that it could not be recovered.
