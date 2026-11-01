# Follow-up: two defects seen on the live board

`results.json` and `stability.json` are the evaluation as it was run, for the configuration
called `EVALUATED_OPTIONS` in `web/src/semantic/config.ts`. They are unchanged and still reproduce
byte for byte (`npx tsx web/eval/run.ts --test --write`, `npx tsx web/eval/stability.ts --write`,
then `git diff evals/semantic` is empty).

This file is about what happened after: two defects seen on real chat in the live demo, one
candidate rule for each, and the decision for each on the **dev** split.

```
npx tsx web/eval/followup.ts            # dev only
npx tsx web/eval/followup.ts --test     # + the test split, labelled as already seen
npx tsx web/eval/followup.ts --test --write   # writes followup.json
```

## Why the test split cannot judge these

Both defects were found by looking at groups the shipped grouper made, including on the test
windows. A test score after a change motivated by those windows is not a held-out result. The
script prints it, under the heading "already scored before this change", for completeness only.
Decisions use dev.

## The rule (the evaluation's own)

Adopt a change if dev B-cubed F1 does not fall and dev false merges stay within 10 % of the
groups shown. Applied to unrounded scores: rounded to three places, both candidates show 0.801.

## Results, dev (10 windows: 8 real dev windows + the 2 historical ones)

| arm | pair P | pair R | pair F1 | B³ F1 | false merges |
|---|---|---|---|---|---|
| as evaluated | 0.872 | 0.515 | 0.647 | 0.801074 | 7 / 83 (8 %) |
| + one-word groups by stem (`oneWordStems`) | 0.872 | 0.514 | 0.647 | 0.800861 | 7 / 84 (8 %) |
| + no chat / chatter in texts (`vocatives`) | 0.872 | 0.515 | 0.648 | 0.801584 | 7 / 83 (8 %) |

Where the windows differ (B³ F1, evaluated / oneWordStems / vocatives):
`sodapoppin` 0.809 / 0.809 / 0.812, `stableronaldo w2` 0.434 / 0.429 / 0.434. Every other dev
window is identical across the three.

### `oneWordStems` — not adopted

The defect: a group of single words the model joined ("ruby", "sapphire", "emerald" in a word
game) was shown as a *topic*. The rule split such groups into spellings of one word. It lowers
dev B³ F1 (0.801074 → 0.800861), because the labels treat one round's guesses as one group —
so by the evaluation's own rule it is not adopted, and the option stays off.

What changed instead is only how such a group is **named**: the grouping is untouched, and a
group whose texts are all single words is shown as "one-word" (src/semantic/live.ts,
`oneWordEach`), not "topic". The evaluation scores grouping, not names, so this does not move
any number above. `stability.ts` counts the labels of every model-made group; it now counts
"one-word" groups explicitly, so its tally is the same as before the name existed (688/688,
891/891 overall).

### `vocatives` — adopted

The defect: in the `hasanabi` test window, the evaluated configuration shows one 15-message group
whose only common thread is the word "chatter": insults aimed at a chatter, "L chatter", "Come on
chatter", a bare "chatters" — five different labelled groups and unlabelled lines in one false
merge (`npx tsx web/eval/inspect.ts hasanabi minilm-l6 0.65 --report`). The rule leaves "chat",
"chatter" and "chatters" out of what is compared, as the streamer's name already is; with it
(`--current`) that merge is gone. Dev B³ F1 does not fall (0.801074 → 0.801584) and false merges stay at
7 / 83, so it is adopted: `OPTIONS = { ...EVALUATED_OPTIONS, vocatives: true }`.

It touches little. Over the 1,131 messages `stability.ts` replays, it changes what is compared for
two; `npx tsx web/eval/stability.ts --current` prints a table identical to the evaluated one.

### Test, already seen (not a fresh result)

| arm | pair P | pair F1 | B³ F1 | false merges |
|---|---|---|---|---|
| as evaluated | 0.798 | 0.449 | 0.781 | 7 / 45 (16 %) |
| + oneWordStems | 0.798 | 0.449 | 0.781 | 7 / 45 (16 %) |
| + vocatives | 0.872 | 0.461 | 0.791 | 5 / 44 (11 %) |

The test gain for `vocatives` is on the window the defect was found in. It is evidence the fix does
what it was meant to on that window, not an estimate of how it does on chat it has not seen.

## Also in this follow-up, outside the scored path

- **Twitch's own emote tags.** The live client now reads the IRC `emotes` tag and treats those
  words as emotes ("Kappa" alone groups only with "Kappa"; "NOWAYING this is insane" is compared
  as "this is insane" when Twitch marked NOWAYING). The evaluation windows were captured without
  the tag, so nothing here measures it. Third-party emotes (7TV, BTTV, FFZ) are not in the tag and
  still read as words unless their shape gives them away (RISKS.md).
- **Labels.** Nothing in `labels/` changed; `labels.sha256` still verifies.
