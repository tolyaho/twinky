# Labelling guide — semantic audience groups

These are the instructions every window in `windows/` is labelled under. They were written before
any window was labelled and before any semantic grouping method was tuned, and they do not change
afterwards without the labels being redone.

## The question a label answers

> If a streamer glanced at this group, would they get **one clear, specific message** from it?

"Six people say the audio is broken." "Nine people are laughing." "Four people ask what game this
is." "Five people answer *Hogwarts* to the guess." Those are groups. "Several messages contain the
word *points*" is not.

## For every message, assign exactly one of

| label | when |
|---|---|
| a cluster id you invent (`snake_case`, e.g. `wants_different_game`) | the message means the same specific thing as at least one **other** message in this window **from a different author** |
| `x` | it shares no specific meaning with another message here — most messages in varied chat |
| `unsure` | you genuinely cannot tell what it means (a reply fragment with no context). Use sparingly |

Every cluster id gets a one-line description of the shared meaning.

## Same meaning

- Can use completely different words, spelling, slang or language: *"his mic is muted"*, *"we can't
  hear him"*, *"звук пропал"* are one group.
- Must be the same **stance and intent**: *"he's cheating"* and *"he's not cheating"* are two groups;
  a question about the game and a complaint about the game are two groups.
- Be specific. *"Positive comments"* is too broad if the messages praise different things; prefer
  the most specific meaning a streamer could act on. If a broad group has two clear sub-meanings,
  split it.

## Not the same meaning

- Sharing a word: *points*, *gamble*, *game*, a number, an emote name used in different sentences.
- Mentioning the streamer's name or `@user`. *"jynxzi"* on its own says nothing specific; *"jynxzi
  is the goat"* and *"jynxzi you're trash"* are different groups.
- Being short. Short messages are not similar to each other just because they are short.

## Reactions and emotes

- **Laughter** is one meaning: `laughing` (LUL, KEKW, OMEGALUL, lol, lmao, xd, haha, ахаха, 😂…).
- Other reactions are grouped **by what they express**: hype (Pog, PogChamp, W, LETSGO), sad or
  sympathy (Sadge, F, rip), shock (monkaS, WutFace, D:), confusion (?, ???, huh), love (<3) — each
  its own group. Do not merge different reactions into one "reaction" group.
- An emote whose meaning you do not know: group only **identical** uses of it (`emote_catjam`).

## Special cases

- **Copypasta**: identical (or near-identical) long messages → one group.
- **Bare numbers and one-word replies**: group only when they clearly answer the same prompt (many
  typing `1` for a vote; the same guess in a guessing game). A lone `100` is `x`.
- **Bots, commands (`!xyz`), links**: `x`, unless several viewers send the same command (then
  `cmd_<name>`). Messages marked `"bot": true` are always `x`.
- `@user` is a masked username (authors and mentions were pseudonymised at capture). Treat it as
  "someone".

## Process

Read the whole window in order first, then label. Do not run any code, search, or grouping tool:
this is a judgement from reading. Each window is given as a numbered text view
(`n | seconds | author | text`); labels are keyed by that number `n`, and **every** number gets a
label. Output:

```json
{
  "window": "<window name>",
  "labeller": "<model or person>",
  "labels": { "0": "<cluster id | x | unsure>", "1": "…" },
  "clusters": { "<cluster id>": "<one-line description of the shared meaning>" },
  "phenomena": ["<which of the ten below occur in this window>"]
}
```

`phenomena` records which of these the window actually contains, so coverage of the evaluation
set can be reported: `same_meaning_different_words`, `same_word_different_meanings`,
`streamer_name_spam`, `generic_numbers`, `reaction_variations`, `copypasta`, `unrelated_singles`,
`simultaneous_topics`, `ambiguous_short`, `topic_transition`.

## How labels are read when scoring

Fixed with this guide, before any window was labelled: a cluster id that ends up on messages from
fewer than two distinct authors does not meet the definition above and is scored as `x`. Label
files are never edited after they are written; this rule is applied by the loader
(`web/eval/data.ts`), and the files are frozen with `labels.sha256` before any method is tuned.

## What these labels are

Drafted by language models working independently of the system being evaluated, and marked
`"reviewed": false` until a person confirms them. The test windows are labelled twice, by two
different models, and the agreement between the two is reported as the ceiling any method can be
expected to reach. Numbers computed against these labels inherit those caveats.
