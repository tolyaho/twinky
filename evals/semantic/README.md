# Semantic grouping — the evaluation behind the board's topics

**Adopted for the live board in `web/`.** A small sentence-embedding model running in the visitor's
browser now groups messages that say the same thing in different words, on top of a deterministic
fast path for reactions, commands and exact repeats. The word rules the board shipped with are
kept, unchanged, as the baseline (`?topics=off`) and as the fallback when the model cannot run.
The Python pipeline (`src/ts/`), its grouping (`evals/grouping/`) and every committed result
outside this directory are untouched.

**Every number here inherits `reviewed: false`.** The labels were drafted by models, not checked
by a person (`labels/PROVENANCE.md`). The test split is six windows and 686 messages. Read the
results as a measured comparison against one careful labelling, not as ground truth.

## Why this is not "Removed experiment #3" again

`docs/IMPROVEMENT_CHANGELOG.md` records embedding clustering measured and *not* adopted: on two
windows, one threshold scored F1 0.770 on a word game and 0.272 on varied chat, the threshold was
chosen by looking at the labels, and the arm needed a paid provider. Each of those objections is
answered here rather than waved away:

| objection then | here |
|---|---|
| two windows, both already seen | 14 new real windows from 14 channels, captured 2026-10-31, split before labelling |
| threshold chosen on the scored labels | every free parameter chosen on dev by a rule fixed in advance; test scored once |
| the threshold does not transfer | conservative grouping (no chaining), a fast path that keeps reactions and repeats out of the model, and a script gate; the per-window test table below shows where it still fails |
| needs a provider and a key | the model runs in the browser: no key, no request carrying chat, no per-message cost |

The old finding still stands for what it measured. This is a different design, measured on new data.

## The data

| | windows | messages | where |
|---|---:|---:|---|
| dev | 8 live + 2 historical | 1053 | live: sodapoppin, jynxzi, zackrawrr, lirik, bratishkinoff, 5opka, summit1g, ishowspeed; historical: `evals/grouping` stableronaldo w2, yugi w9 |
| test | 6 live | 686 | hasanabi, extraemily, emiru, morphe_ya, insize, xqc |
| contrast | constructed scenes | — | `contrast.json`: never real chat, never in a headline number |

- **Captured** from public Twitch chat with `web/eval/capture.mjs` (anonymous IRC, no key). Authors
  are pseudonymised; known bots are flagged from the login before it is hashed.
- **Selected** by `web/eval/select-windows.ts`, one window per channel: the busiest 60 s, the
  busiest 30 s when 60 s held more than could be labelled carefully, or a deliberately quiet
  stretch for the quiet-chat case. No labels were involved.
- **Split** by the rule in `split.json`: fixed before any window was labelled, one window per
  channel, so no channel appears in both. The two historical windows are dev only, because they
  shaped the original finding.
- **Labelled** under `LABELING.md` by ten independent Claude subagents (`labels/PROVENANCE.md`).
  The six test windows were labelled twice, by Opus and by Sonnet, without access to each other.
- **Frozen**: `labels.sha256` covers the guide, the split, the windows and the labels. They were
  committed in 23f66ec, a commit with no grouping code, before any method was scored, and
  `web/eval/data.ts` refuses to score if any of them has changed.

## The arms

| arm | what it is |
|---|---|
| **A** lexical | what the board shipped: the TypeScript port of `group_chat` plus the two-chatter floor |
| **B** embeddings only | every raw message embedded and clustered; no fast path |
| **C0** fast path, no model | reactions by family, commands and exact repeats; nothing else is grouped |
| **C** hybrid | C0 plus grouping by meaning for messages that carry words |
| labeller agreement | the second labelling scored as if it were a method: the ceiling to expect |

**The hybrid** (`web/src/semantic/`):

1. *Prepare* each message (`prep.ts`): strip invisible characters and the streamer's name, squash
   letter runs, and recognise reactions by family (laughing, hype, shock, confusion, agreeing,
   doubt, awkward, saluting…) from emotes and words. An emote of unknown meaning groups only with
   itself. Bare numbers, one-word replies and commands group only when identical, and only from
   three or more messages.
2. *Fast path* (`hybrid.ts`): those groups, with no model.
3. *Embed* the distinct texts that are left: `all-MiniLM-L6-v2`, 8-bit ONNX, mean pooling. Text
   mostly in a non-Latin script is not shown to this English model; it groups only when identical.
4. *Group by meaning* (`cluster.ts`, method `center`): the text with the most similar neighbours
   becomes a centre, and a text joins only if it is at least 0.65 similar **to the centre**, not to
   any member. That is what stops chaining. Two refinement passes; any text may stay ungrouped.
5. *Floors*: a group needs two messages from two different chatters.
6. *Label*: the group's most repeated wording, quoted, trimmed to eight words. A group of single
   words in several spellings ("amethyst", "Amethysts") is shown as a repeat, not a topic; a group
   where at least half the messages are questions is shown as a question.

## The selection rule (fixed before any run)

> Highest pooled dev B-cubed F1 among configurations whose pooled dev share of false merges is at
> most 10 %.

B-cubed rather than pairwise F1, because pairwise F1 is dominated by the one or two biggest
groups in a window. The false-merge cap, because on a public board a confident wrong group is
worse than a missing one. A **false merge** is a shown group whose largest labelled share is under
two-thirds.

**The grid** (`web/eval/run.ts`): method single, average or centre (± centroid merge); threshold
0.30–0.95 in steps of 0.05, plus 0.96–0.98; an optional adaptive quantile; two-message or
three-message floor. English-only models are gated to Latin script; multilingual ones are not.

## Choosing the model (dev only)

Best dev configuration per candidate under the rule, from
`npx tsx web/eval/run.ts --models minilm-l6,para-minilm-l3,bge-small,arctic-xs,mxbai-xsmall,rubert-tiny2,user2-small,para-multi-l12,me5-small`
(dev only, without `--test`):

Each row is that model's best configuration whose dev false merges stay within the 10 % cap.

| model | weights | languages | dev B-cubed F1 |
|---|---:|---|---:|
| **all-MiniLM-L6-v2** (centre, 0.65) | 23 MB | English | **0.801** |
| multilingual-e5-small | 118 MB | multilingual | 0.797 |
| mxbai-embed-xsmall-v1 | 24 MB | English | 0.794 |
| bge-small-en-v1.5 | 34 MB | English | 0.792 |
| paraphrase-MiniLM-L3-v2 | 17 MB | English | 0.786 |
| USER2-small | 35 MB | English + Russian | 0.785 |
| paraphrase-multilingual-MiniLM-L12-v2 | 118 MB | multilingual | 0.783 |
| rubert-tiny2 | 29 MB | English + Russian | 0.776 |
| snowflake-arctic-embed-xs | 23 MB | English | 0.775 |

The top of this table is close; size and speed decided it. MiniLM-L6 is the best on dev and among
the smallest, it runs about twice as fast as USER2 in WebKit (below), and it is Apache-2.0.

Russian is where the choice costs something. `npx tsx web/eval/compare.ts` breaks dev down by
language. With the shipped configuration on the two Russian dev windows (118 messages):

- letting this English model compare Cyrillic text scores B³ F1 0.820, with 4 of 9 shown groups
  false merges;
- the Latin-script gate scores 0.939, with none;
- the fast path alone scores 0.955;
- the multilingual models score 0.962 (USER2, me5).

So Russian chat gets the fast path and exact repeats, not grouping by meaning. On English the gate
changes nothing (0.806 either way). The page's "How grouping works" states the limitation.

Pinned: `Xenova/all-MiniLM-L6-v2` at revision `751bff37182d3f1213fa05d7196b954e230abad9`, every file.

## Results

### Dev (where everything was chosen)

| arm | pair P | pair R | pair F1 | B³ F1 | false merges | covered |
|---|---:|---:|---:|---:|---:|---:|
| A lexical | 0.499 | 0.217 | 0.302 | 0.683 | 27 / 73 (37 %) | 0.55 |
| B embeddings only (single 0.70) | 0.778 | 0.214 | 0.335 | 0.712 | 9 / 98 (9 %) | 0.60 |
| C0 fast path, no model | 0.969 | 0.415 | 0.581 | 0.767 | 2 / 50 (4 %) | 0.50 |
| **C hybrid (shipped)** | **0.872** | **0.515** | **0.647** | **0.801** | 7 / 83 (8 %) | 0.68 |

### Test (held out, scored once, after the choice)

| arm | pair P | pair R | pair F1 | B³ F1 | false merges | covered |
|---|---:|---:|---:|---:|---:|---:|
| A lexical | 0.426 | 0.240 | 0.307 | 0.703 | 15 / 48 (31 %) | 0.64 |
| B embeddings only | 0.538 | 0.320 | 0.401 | 0.751 | 13 / 57 (23 %) | 0.67 |
| C0 fast path, no model | 0.968 | 0.241 | 0.386 | 0.762 | 1 / 36 (3 %) | 0.44 |
| **C hybrid (shipped)** | **0.798** | **0.313** | **0.449** | **0.781** | 7 / 45 (16 %) | 0.58 |
| labeller agreement (Sonnet vs Opus) | 0.806 | 0.651 | 0.721 | 0.877 | 9 / 67 (13 %) | 0.87 |

Only on the messages the fast path hands to the model (the text-only subset), test B³ F1 is
A 0.713, C0 0.751, C 0.778.

**Adopted, because it is meaningfully better than what shipped**, on held-out data:

- pair precision 0.426 → 0.798: four in ten proposed pairs were right, now eight;
- false merges 31 % → 16 % of shown groups;
- B³ F1 0.703 → 0.781, higher than A in all six test windows.

**What it does not do:**

- *Recall stays low.* Test pair recall is 0.313 against the labellers' 0.651. The grouping is
  conservative on purpose, and much of what people label as one cluster is too varied for it.
- *False merges exceed the dev cap on test.* 16 % against the 10 % allowed on dev; dev and test
  disagree, as they should be allowed to.
- *Most of the gain is the fast path.* C0, with no model at all, already takes test B³ F1 from 0.703
  to 0.762. The model adds 0.019 on top, and its contribution is recall, at some cost in precision.

Per test window, B³ F1, C against A:

| window | language | A | C |
|---|---|---:|---:|
| hasanabi | en | 0.550 | 0.628 |
| extraemily | en | 0.734 | 0.782 |
| emiru | en | 0.921 | 0.973 |
| morphe_ya | ru | 0.808 | 0.946 |
| insize | ru | 0.522 | 0.587 |
| xqc | en | 0.845 | 0.982 |

### Where the hybrid is better (test, quoted from `inspect.ts --report`)

- **Same claim, different words.** *"hasan wouldn't say that shit. that's crazy"*, *"AT NO POINT WAS
  HASAN SAYING IS WAS THE SAME HELLO!!!"* and two more: all four labelled messages in one group.
  The word rules split them by whichever word happened to repeat.
- **Variants of one remark.** *"nat looking different today"*, *"Nat looks different"* and *"nat
  looks different"* ×2: one group, exactly as labelled.
- **A meme in several spellings.** *"AINTNOWAY 43 MONTHS"*, *"43 months!!!!!!!!!"*, *"Classic 43
  months"* and *"43 months ???"*: eight messages in one group.
- **Kinds of reaction kept apart.** Laughing, confusion, agreeing (*"mhm"* ×6) and greetings are
  separate rows rather than one "reaction wave".

### Where it is worse, or still wrong

- **A shared noun is not a shared meaning.** In hasanabi a 15-message group, labelled *"Dumbass
  chatter"*, holds *"Come on chatter"*, *"L chatter"*, *"weird chatter"* and *"what a piece of shit
  chatter"*: five labelled clusters (insults, exasperation, "took an L") joined by the word
  "chatter". It is the hybrid's largest false merge.
- **Unknown emotes read as words.** *"agahi"* (an emote) became a topic joining a plain greeting
  with greetings to a named person. *"Stare"* (extraemily) and *"Skateparkge"* (hasanabi) each made
  a two-message false merge in the same way.
- **Fragmentation.** Labelled "ban the chatter" (19 messages) came out as *"ban"* (10) and *"just
  perma"* (4), with five unplaced.
- **Long, varied paraphrase is mostly missed.** Of 13 messages labelled "the point was clear", one
  was grouped.

## Stability, and whether labels say what chat said

`npx tsx web/eval/stability.ts` → `stability.json`. The page's own groupers over real chat at its
own timestamps: a 60 s window recounted every 1.5 s, as on the board, over the replay and the six
captures longer than two minutes (1,439 recounts). The worker is replaced by one that answers
at once, so this measures the steady state, not loading.

| | lexical | hybrid |
|---|---:|---:|
| grouped messages that move to another group at the next recount | 0.3 % | 0.3 % |
| ... that fall out of every group | 1.1 % | 0.6 % |
| groups whose label changes from one recount to the next | 0.0 % | 0.7 % |
| topic labels that are the start of one of the topic's own messages | — | 891 / 891 |

Labels are faithful by construction: they quote a message in the group. What a quote cannot
promise is that one chatter's wording summarises everyone's. The label changes only when its
wording leaves the group or another wording has at least 1.5× its messages.

## Speed, size and memory in the browser

`npx tsx web/eval/browser-bench.ts minilm-l6,user2-small,me5-small chromium,webkit` drives the real
worker in Playwright's Chromium and WebKit on 400 distinct dev texts. Measured on an Apple M1
(2026-10-31). Phones are slower, and **real Safari on a phone has not been measured**.

| | Chromium, cross-origin isolated | Chromium, not isolated | WebKit (headless) |
|---|---:|---:|---:|
| MiniLM, first load (download + compile) | 9.3 s, 29.9 MB transferred | — | — |
| MiniLM, load from browser cache | ~1.0 s | — | re-downloads (Playwright WebKit keeps no cache) |
| MiniLM, time per text | 3.7–4.6 ms | 7.9–8.4 ms | 14.7 ms |
| longest frame gap on the page while embedding | — | 18 ms | 170–361 ms (idle: 23–32 ms) |
| ... with the worker capped at half its time (`DUTY = 0.5`, shipped) | — | — | 147–158 ms, ~55 fps |
| USER2-small, time per text | 6.8 ms | — | 31.7 ms, gaps up to 1089 ms |
| multilingual-e5-small, first load | 18.4 s, 142 MB | — | — |

- **Cross-origin isolation** (`web/vercel.json`: COOP `same-origin`, COEP `credentialless`) lets
  ONNX Runtime use threads in Chromium, about twice as fast. Safari ignores `credentialless` and
  runs single-threaded, correctly but slower.
- **Memory** was not measured reliably. `measureUserAgentSpecificMemory` needs COEP `require-corp`,
  and process RSS deltas accumulated across runs. The design bounds are: q8 weights 23 MB; at most
  6,000 cached vectors (384 floats each, about 9 MB, least recently used evicted); at most 400 texts
  per request.
- **The 400 msg/s burst** (`tests/e2e/semantic.spec.ts`, 300 distinct texts for 5 s): the page
  showed *"N new messages not read yet"* while the model was behind, and nothing was presented as
  complete. Longest frame gap 17 ms in Chromium; 177 ms alone and 237 ms under a parallel run in
  WebKit. Chromium caught up as the burst ended, WebKit 3.9–4.0 s later.

## Real time: how the model is kept off the hot path

- **One worker per page**, shared by every channel. A channel switch is a new *epoch*, not a new
  download, and any answer for an older epoch is dropped (tested: a switch in the middle of a burst).
- **Newest request wins.** The page sends the window when it changes, most repeated texts first,
  then the newest, at most 400. The worker drops any request overtaken before it starts, so a
  backlog is never queued.
- **Never waits.** Each 1.5 s recount uses the worker's latest answer. Reactions, commands and exact
  repeats are grouped at once; text the model has not read is counted as unread and shown as such.
- **Bounded work.** Batches of 48, run in length-sorted sub-batches of 16; at most half the wall
  time (`DUTY`); progress posted at most every 700 ms.
- **Fallback.** If the model fails to load or crashes, the board switches to the word rules and
  says *"Topics unavailable — grouped by shared words"*. `?topics=off`, a Save-Data request, or a
  browser without Workers or WebAssembly gets the word rules without downloading anything.

## Cost

**Inference costs the project nothing.** The model runs on the visitor's machine. There is no
embedding endpoint, no key, and no request that carries chat.

| | quiet (summit1g) | moderate (jynxzi) | very active (hasanabi) |
|---|---:|---:|---:|
| measured chat rate | 0.11 msg/s | 2.76 msg/s | 10.3 msg/s |
| distinct texts the model reads | 0.10 /s | 2.16 /s | 9.60 /s |
| visitor CPU at 4 ms/text (Chromium) | ~0.04 % of a core | ~0.9 % | ~4 % |
| visitor CPU at 14.7 ms/text (WebKit) | ~0.15 % | ~3 % | ~14 % |
| a hosted embedding API instead, per channel-hour¹ | ≈ $0.00005 | ≈ $0.0008 | ≈ $0.006 |

¹ Estimate: tokens ≈ characters ÷ 4 (measured 27.3, 16.0 and 31.6 characters per message), at
$0.02 per million tokens for `text-embedding-3-small` as listed on OpenAI's model page on
2026-11-01. Multiply by the number of visitors if each browser called it.

A hosted API would be cheap in money. It was not chosen because the cost that matters is
elsewhere. The key would sit behind a public endpoint that accepts arbitrary text; that needs abuse
protection and a spending cap before it can exist, and the spec forbids it otherwise. Chat would
leave the browser. Every recount would wait on the network. And no provider key is configured:
the repository has no `.env`, and `web/.env.local` holds only Vercel's OIDC token.

**What a visitor pays:** about 30 MB downloaded once, the first time they open a channel (MiniLM
weights from the Hugging Face hub, the ONNX Runtime WebAssembly from jsDelivr), then cached. The
landing page loads neither, so a crawler opening the homepage costs nothing beyond the static page.
The worker script is 166 KB gzip, served by Vercel. Server cost does not grow with visitors.

## Where the labels are uncertain

From the labellers' own hand-back reports. These are the calls they said a second labeller might
make differently, and every score above inherits them:

- **Splitting near-synonyms**: "erm/umm" apart from "?/HUH" (sodapoppin); "there it is", "called it"
  and "classic" as three groups (zackrawrr); "ban" apart from "timeout" (hasanabi, both labellers);
  "Jynxzi is cracked" apart from "pulling his weight" (jynxzi).
- **Merging**: OKBRO with SUREMAN as disbelief (lirik); "43 months" disbelief with "classic
  long-time sub" (hasanabi); "эм", "хм" and "Hm" as one doubt (bratishkinoff); "bingo" with "yep"
  (zackrawrr).
- **Emotes of unknown meaning**: "ddx" and "GAGAGA" read as laughter by Opus, "ddx" as an unknown
  emote by Sonnet (insize); "ANGOLA" left as `x` (xqc).
- **Russian ")" and "))))"**: laughter to Opus, smiley punctuation to Sonnet (insize, morphe_ya).
- **Unmarked bots**: game bots in emiru and bratishkinoff were labelled `x` by reading, because the
  capture had not flagged them.

The two labellers agree at B³ F1 0.877. A method at 0.781 is still well short of that ceiling.

## Limitations

- **Labels are model-drafted.** No person has reviewed them; a human-reviewed holdout is the next
  step that would change what these numbers mean.
- **Small test set.** Six windows, 686 messages, one evening of chat (2026-10-31). Per-window
  results vary widely (B³ F1 0.587–0.982).
- **English only for meaning.** Russian is measured and gets the fast path plus exact repeats; other
  languages and scripts are not measured.
- **Chat only.** A topic says what chat is saying, never why; nothing here links a group to the
  stream moment that caused it.
- **Safari on phones** is unmeasured; headless WebKit on an M1 shows 150–240 ms frame gaps while
  the model catches up.
- **Two third-party CDNs**: the Hugging Face hub and jsDelivr. If either fails, the board falls
  back to the word rules and says so (tested by `semantic.spec.ts`).

## Reproduce

No keys. The model downloads once into `web/eval/.models/` (gitignored), and vectors are cached in
`web/eval/.cache/`.

```
cd web
npx tsx eval/run.ts                       # dev: every arm and configuration, the rule's choice
npx tsx eval/run.ts --test --write        # + the held-out test split; writes results.json
npx tsx eval/inspect.ts hasanabi minilm-l6 0.65 --report   # one window, group by group
npx tsx eval/stability.ts --write         # stability.json
npx tsx eval/browser-bench.ts minilm-l6 chromium,webkit
npm test && npm run e2e                   # 266 unit tests, 47 browser tests
```

`results.json` was written by the one scored run, and a second run on 2026-11-01 printed
byte-identical output.
