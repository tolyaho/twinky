# Hook — Scene 1, generated shots

Four clips, ~18 s cut. Paste each prompt into Dreamina / Seedance 2.5 as its own generation.

## Read this before generating

**Never ask the model for readable text.** Seedance will render chat, usernames and counters as
garbage glyphs, and a hook full of fake letters is the one thing that makes a submission look
cheap. Every prompt below deliberately says *unreadable*. The real chat flood and the viewer
counter get **composited from your own screen recording** — which is better, because it is real
data, and it keeps the shotlist's own rule: generated footage may never be cut so it looks like
the product working.

**Lock the character.** Generate shot 1A first, then use its last frame as the reference/first
frame for 1B–1D, or paste the identical subject sentence verbatim into all four. Without that
you get four different people.

**Draft small, upscale one.** Render each at the lowest quality first, pick the keeper, then
re-render that one at full resolution. Four beats at draft quality costs almost nothing against
€800; twenty iterations at full quality is how it disappears.

16:9, ~5 s per clip unless noted. Negative prompt on all four:
`text, letters, words, subtitles, captions, watermark, on-screen interface, distorted hands`

---

## 1A — calm (5 s)

> Medium shot of a young man streaming from a small bedroom at night. Headphones resting around
> his neck, a microphone on a boom arm in the near foreground, slightly out of focus. He is lit
> by a warm desk lamp on one side and the steady pale glow of an off-screen monitor on the other.
> He leans back in his chair, relaxed, half-smiling, talking easily to someone he cannot see.
> Very slow push in. Warm, calm, intimate. Shallow depth of field, 35 mm, soft natural film
> grain, cinematic.

## 1B — the turn (5 s)

> The same young man in the same bedroom. He stops mid-sentence and sits forward, eyebrows
> lifting, his eyes flicking sideways toward the off-screen monitor. The pale light on his face
> begins to pulse and shift, faster than before. One small handheld camera bump. Tension entering
> a calm room. Same warm lamp, same shallow depth of field, cinematic.

## 1C — overwhelm (5 s)

> Close-up on the same young man's face, lit almost entirely by the flickering light of an
> off-screen monitor. The flicker accelerates into rapid blue-white strobing. His eyes dart left
> and right, faster and faster, scanning something he cannot keep up with. Faint, blurred,
> completely unreadable streaks of reflected light stream upward across his eyes. Slow dolly in
> with a subtle dutch tilt. Claustrophobic, overwhelming, cinematic.

## 1D — the cut (3 s)

> The same young man, mid-motion. Everything stops at once. The flickering monitor light snaps
> off, leaving only the warm desk lamp. He sits completely still in the sudden quiet, half-lit,
> staring at nothing. Camera locked off, no movement at all. Cinematic, silent, high contrast.

---

## What gets composited, not generated

- **The chat flood** — screen-record your own `stableronaldo` capture, the `drac…` run. It is 74
  messages across the window boundary. Overlay it as a soft, mostly-illegible reflection over 1C.
  Real data, real motion, no fake glyphs.
- **The viewer counter climbing** — the unique-chatters number in the new rail, screen-recorded.
- **Audio** does the escalation more than the picture will: a room tone that gets a keyboard, then
  ten keyboards, then a wall of notification ticks, cut dead on 1D. Silence after 1D is the beat.

## Then the title card — build it, do not generate it

Make it in your own design system, not in Dreamina: canvas `#f5f5f5`, ink `#0c0a09`, the display
face at **weight 300 only**, one pastel orb drifting behind, no saturated colour. A title card
that matches the site exactly is worth more than a rendered one, and it takes ten minutes in
HTML you already have.

**The naming check is closed — resolved 2026-08-30 in favour of Twinky.** This note used to warn
that the card said *"introducing… Twinky"* while the repo, README, UI and submission all said
*Twitch Agent*, and that a judge who reads one name and hears another counts two projects. The
rename has been done: all three pages, the README, the submission and the invariant now read
**Twinky**, with a tagline wherever the bare name would otherwise stand alone. Say "Twinky" in
the video.

It was safe to do this late because the product name appears in **no prompt string** — verified
against the agent's `SYSTEM`, `CARD_CONTRACT`, `INTRO`, `TOOLS_DOC`, the baseline prompt and the
vision module before a single file was touched. So it could not move a cache key, and `make eval`
still reports 48 hits / 0 misses with `evidence/` byte-identical.

---

## Sequencing

Your own shot list says *"capture the real interface first, then generate the hook"* — and it is
right about why: generated footage that does not fit the cut is how the budget goes. But
generations render server-side and take minutes, so start these four now and **screen-record the
product while they render.** That is parallel, not out of order.

The discipline that matters: **one pass of four clips, then stop.** Do not iterate on the hook
until the product footage exists and you know how long the hook can actually be. A beautiful
18-second opening on a submission with no demo scores nothing.
