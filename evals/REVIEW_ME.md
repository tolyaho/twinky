# Gold labels awaiting review

**These labels were drafted with model assistance from the captured fixtures. No human has
confirmed them yet.** Every gold file carries `"reviewed": false` until you change it.

You are the only person who can turn this into ground truth. Budget ten minutes. For each case
below: read the three sentences, decide **agree / disagree**, and if you disagree say what the
right answer is. You should not need to open a single JSON file.

To confirm a case, do not hand-edit JSON — a stray comma at three in the morning is a broken
eval. Use:

```bash
make review                                                    # what is confirmed, what is not
python scripts/confirm_gold.py --confirm c05_warning_no_cause --by "your name"
python scripts/confirm_gold.py --disagree c11_sarcasm_mockery --by "your name" \
                               --note "the cause is the clip at 4:12"
```

It sets the flag, records who and refuses an anonymous confirmation, and touches no other field.
**There is deliberately no `--all`** — eleven labels behind one keystroke is how a review becomes
a rubber stamp. Disagreeing is recorded too, because a label a reviewer rejected is information,
and leaving it `false` would look identical to a label nobody read.

Whatever is still `false` at submission gets said out loud in README §6 — that is the deal, and
it is better than claiming a review that did not happen.

**What "correct" means here.** The label is not "what is chat feeling". It is: *which stream
event caused this cluster, and is there enough evidence in the window to prove it?* When nothing
in the window proves a cause, `unknown` is the right answer, not a cop-out. Four of the eleven
cases are deliberately `unknown`.

Timestamps below are milliseconds since epoch; the clock times are the streamer's local overlay
where a frame showed one.

---

## The three that decide the submission

### `c05_warning_no_cause` — warning, trigger **unknown**
`marlon_2026-08-30T0701`, window `1788073323294 – 1788073383294`

Three viewers say the co-streamer's microphone is not working: *"Marlon should have a mic"*,
*"give them the mic"*, *"JET GET THE AUDIO"*. There are **zero transcript segments** in this
window and both frames show a video game rooftop, so nothing available to the system explains
the complaint.

**Correct answer:** a `warning` card citing those three messages, with `trigger_event_id:
"unknown"`. Naming any cause here is a hallucination — the audio problem is not observable in
the captured evidence, only its effect on chat is. **Caveat worth your attention:** this window
is dominated by an unrelated `AURA` ×24 / `JUMP` ×14 flood, so the warning is a minority signal
that has to be found in noise. That is realistic, and it is also the hardest thing in the set.

### `c11_sarcasm_mockery` — reaction, trigger **unknown**
`marlon_2026-08-30T0715`, window `1788074296000 – 1788074356000`

Chat is mocking the streamer for not doing the thing he keeps promising ("slams"):
*"you owe like 100 slams"*, *"we 0/87 on slams rn"*, *"0/1000 SLAM"*, *"0 slams btw"*,
*"You almost slammed him mar I saw that Kappa"*, and *"good job marlon, that tree near the
sidewalk was secured for last 10 minutes"*.

**Correct answer:** a `reaction` card labelled as mockery/derision, not praise, with
`trigger_event_id: "unknown"`. Read literally, *"good job"* and *"You almost slammed him"* are
compliments; they are not. `Kappa` is the Twitch sarcasm emote and is doing exactly that work.
The cause is a promise made before this window, so no event inside it proves the trigger.
**Confidence should not be high.**

### `c12_no_signal_abstain` — abstain, no signals at all
`yugi_2026-08-30T0723`, window `1788074603171 – 1788074663171`

Nineteen messages, nineteen distinct bursts. Viewers reply to each other (`@diddyjr12344 mmmm`,
`@NBA_H1 he can still get in`), post a link, run `!join`, and ask the streamer unrelated
one-off questions. Nothing is shared, nothing repeats, no wave.

**Correct answer:** one `none` card. There is stream context — the streamer is talking through
all sixteen transcript segments — but there is no *audience* signal, because the unit of this
product is a cluster, not a message. **The judgement call to check:** two individual questions
to the streamer go unanswered here. I ruled that a single unanswered message is not an audience
signal. If you disagree, this becomes an `unanswered_question` case instead.

---

## Frame-grounded answers — the thesis cases

`stableronaldo_2026-08-30T0723` is a **sleep stream**: three people asleep at 3:23 am with an
automated word-guessing overlay running. Deepgram returned zero utterances for the whole
714-second file, and that is correct — nobody is speaking. Chat plays the puzzle on screen.

These three cases exist because chat here is *provably* uninterpretable without the frame. A
chat-only system sees people typing unrelated dictionary words.

### `c01_word_puzzle_amethyst` — audience_answer, trigger `frm_b78f94d5a1`
Window `1788074707878 – 1788074767878`. The frame at the window's first millisecond shows
`GUESS THE WORD!` with `ame_______`. Chat answers `amethyst` ×7, `American`, `amendment`,
`amethysts`. The next frame shows `ameth_____`, confirming the answer.

**Correct answer:** `audience_answer`, trigger is the frame caption showing the prompt, with a
distribution over the guesses. Check that a *frame* is an acceptable trigger to you — it is the
whole argument for multimodality.

### `c02_word_puzzle_herald` — audience_answer, trigger `frm_1c9aa32f6e`
Window `1788074917878 – 1788074977878`. Prompt `he____`; chat offers `herald` ×6, `heaven`,
`heater`, `heather`, `heroes`; the next frame confirms `herald`.

**Correct answer:** as above. This one is included specifically because the losing guesses are
numerous — the distribution should show the spread, not just the winner.

### `c07_frame_only_dracorex` — audience_answer, trigger `frm_8cfb061b83`
Window `1788074767878 – 1788074827878`. Prompt `dra_____`. Chat converges through `draconian`
×11, `dracula` ×7, `dragons` ×5, `draconic`, `dramatic`; two frames later the answer is
`dracorex`.

**Correct answer:** as above. Note that the crowd is *wrong* — the popular guess `draconian` is
not the answer. The card should report what the audience said, not what was correct.

---

## The rest

### `c03_failure_laughter` — reaction, trigger `tr_3515c2c347`
`marlon_2026-08-30T0715`, window `1788074254219 – 1788074314219`. The streamer says
*"Your shoes are ugly."* and chat laughs: `lol` ×24 plus variants.

**Correct answer:** `reaction` triggered by that spoken segment. **Check this one properly** —
it is the weakest trigger attribution in the set. Ten transcript segments sit in this window and
several are plausible causes; I picked the insult because the laughter follows it. If you think
a different segment caused it, say which.

### `c06_two_speakers_laughter` — reaction, trigger `tr_ceef73e969`
`yugi_2026-08-30T0723`, window `1788075083171 – 1788075143171`. Two diarized speakers alternate.
Chat laughs (`LOL`, `LMFAO`, `LMAO`) after `spk_1` says *"Shut the front door, dude. You're 45?
No. That's my boy, style 45…"*.

**Correct answer:** `reaction` attributed to that segment, not to whichever speaker happens to
dominate the window. This case exists to catch speaker misattribution, so if the diarization
looks wrong to you, that *is* the finding.

### `c08_pool_jump_reaction` — reaction, trigger `frm_d88784255a`
`marlon_2026-08-30T0701`, window `1788073366308 – 1788073426308`. The frame shows a crowd around
a pool at night with someone crouched on the roof above it. Chat: `GG` ×17, `geeg` ×7, `eww` ×7.

**Correct answer:** `reaction` triggered by the frame. The two transcript segments here are
about something else entirely, which is the point — a speech-only system attributes this wrongly.

### `c09_two_topics` — two separate reactions, both trigger **unknown**
`marlon_2026-08-30T0715`, window `1788074514681 – 1788074574681`. Two unrelated things run at
once: chat reacts to a named guest (`VIOLET` ×8) while a copypasta about grabbing the camera is
spammed ×4.

**Correct answer:** **two** cards, not one merged card. Both triggers `unknown` — neither the
guest's arrival nor the copypasta's origin is provable inside this window. This is the only case
with two gold signals, and it tests separation.

### `c10_spam_collapse` — reaction, trigger **unknown**
`marlon_2026-08-30T0715`, window `1788074574681 – 1788074634681`. The same copypasta, *"grab the
camera for an edit by eris"*, posted six times, half of them with a trailing full stop.

**Correct answer:** one `reaction` card. The specific thing under test is the deterministic
reducer: `"…eris"` and `"…eris."` must collapse into **one** burst with a count of 6, not two
bursts of 3. Trigger `unknown` — it is a viewer campaign, not a response to a stream event.

---

## What is not in this set, and why

I built cases from what the four captures actually contain, not from a wish list. Absent:

- **No numeric-rating case.** I searched all four fixtures for bare-number replies (`8`, `9/10`)
  and found **zero**. These are IRL/podcast streams, not gaming streams where "rate this out of
  ten" happens. Writing one would have meant fabricating the phenomenon.
- **No binary-choice case.** The one real candidate — *"is there any type of water sitting there
  or do y'all drink straight alcohol?"* in `marlon_0715` — lands 8 seconds before the fixture
  ends, so there is no room for chat to answer inside a 60-second window.
- **No prompt-injection case.** No chat message in any fixture attempts it.
- **Eleven cases, not twelve.** A twelfth (`AURA` meme flood) was cut because its window sat 72%
  inside `c05`'s on a 120-second fixture; two cases sharing most of their events are not two
  independent measurements. Worst remaining overlap between any two cases is 30%.

**Balance, for your sanity check:** 4 frame triggers, 2 speech triggers, 5 `unknown` triggers
across 12 gold signals, 1 abstention. Four fixtures. Two of the eleven cases have no speech at
all in the window.
