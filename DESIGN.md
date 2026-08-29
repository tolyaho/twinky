# DESIGN.md — the design system for this project

Read before writing any UI. Derived from the ElevenLabs `DESIGN.md` in
VoltAgent/awesome-design-md. Tokens are authoritative; do not improvise colours.

## The decision

Do **not** build a separate marketing site. The operator dashboard with a strong hero state *is*
the premium product page. Same artifact, half the work, and it feeds End-to-End Quality instead
of competing with it for hours.

Source for the tokens below: `DESIGN.md` for ElevenLabs from
<https://github.com/VoltAgent/awesome-design-md/tree/main/design-md/elevenlabs>
(mirrors: designmd.co/d/elevenlabs, getdesign.md/elevenlabs/design-md, designmd.app).

---

## Read this before using the tokens

**ElevenLabs is a LIGHT, warm, editorial system.** Canvas `#f5f5f5`, ink `#0c0a09`, no saturated
brand accent at all — the primary CTA is a near-black pill. Every streaming tool on earth is dark
purple. Two consequences:

1. **A light editorial page frame is a differentiator.** A judge who opens a warm off-white,
   Times-adjacent editorial page for a Twitch product does not think "hackathon project".
2. **Correction to earlier guidance:** the earlier note said "one accent derived from Twitch
   purple". That breaks this system, which has no accent colour. Drop it. Purple may appear
   *inside data* (chat rendering, a chart series) but never as a UI accent or CTA.

The system already contains dark surfaces — `#0c0a09` and `#1c1917` — used for featured cards.
So the coherent split is:

- **Light editorial** for the page frame: hero, how-it-works, results, changelog, footer.
- **Dark product canvas** for the live rail and the replay viewport, using the system's own dark
  surface tokens.

That is how ElevenLabs itself handles contrast. It is a system decision, not a compromise.

---

## Tokens

```css
:root {
  /* ink / primary */
  --primary:            #292524;   /* warm near-black — ALL primary CTAs */
  --primary-active:     #0c0a09;

  /* surfaces */
  --canvas:             #f5f5f5;
  --canvas-soft:        #fafafa;
  --surface-card:       #ffffff;
  --surface-strong:     #f0efed;
  --surface-dark:       #0c0a09;   /* product canvas */
  --surface-dark-elev:  #1c1917;   /* cards on the dark canvas */

  /* text */
  --ink:                #0c0a09;
  --body:               #4e4e4e;
  --body-strong:        #292524;
  --muted:              #777169;
  --muted-soft:         #a8a29e;

  /* hairlines — the system uses borders, not shadows */
  --hairline:           #e7e5e4;
  --hairline-soft:      #f0efed;
  --hairline-strong:    #d6d3d1;

  /* atmospheric gradients — DECORATION ONLY. never a fill, never text. */
  --mint:               #a7e5d3;
  --peach:              #f4c5a8;
  --lavender:           #c8b8e0;
  --sky:                #a8c8e8;
  --rose:               #e8b8c4;

  --success:            #16a34a;
  --error:              #dc2626;

  /* spacing, base 4px */
  --xxs: 4px;  --xs: 8px;   --sm: 12px;  --base: 16px;
  --md: 20px;  --lg: 24px;  --xl: 32px;  --xxl: 48px;  --section: 96px;

  /* radii */
  --r-xs: 4px; --r-sm: 6px; --r-md: 8px; --r-lg: 12px;
  --r-xl: 16px;              /* cards */
  --r-xxl: 24px;             /* orb cards */
  --r-pill: 9999px;          /* every button and badge */

  --shadow-hover: 0 4px 16px rgba(0,0,0,.04);   /* the ONLY shadow tier */
}
```

## Typography

Display face is **Waldenburg**, proprietary to ElevenLabs — you cannot use it. Substitute and
keep the metrics, which carry most of the effect:

- Display: `Inter` (or `Inter Tight`) at **weight 300** with the negative tracking below.
  If a serif reading is wanted instead, `Newsreader` or `Instrument Serif` at 300.
- Body/UI: `Inter`.

**Display scale — weight 300 only. Never heavier. This is the editorial voice.**

| Size | Weight | Line height | Tracking | Use |
|---|---|---|---|---|
| 64px | 300 | 1.05 | −1.92px | Hero |
| 48px | 300 | 1.08 | −0.96px | Large display |
| 36px | 300 | 1.17 | −0.36px | Section heads |
| 32px | 300 | 1.13 | −0.32px | Subsection |
| 24px | 300 | 1.20 | 0 | Card titles |

**Inter scale**

| Size | Weight | Line height | Tracking | Use |
|---|---|---|---|---|
| 20px | 500 | 1.35 | 0 | Title |
| 18px | 500 | 1.44 | +0.18px | Labels |
| 16px | 400 | 1.50 | +0.16px | Body |
| 16px | 500 | 1.50 | +0.16px | Body strong |
| 15px | 400 | 1.47 | +0.15px | Small body |
| 14px | 400 | 1.50 | 0 | Captions |
| 12px | 600 | 1.40 | +0.96px | Uppercase badges |
| 15px | 500 | 1.00 | 0 | Buttons |

Positive body tracking (+0.15–0.18px) is what makes it read editorial rather than SaaS. Do not
skip it.

## Components

- **Button primary** — bg `--primary`, white text, pill, padding 10/20, height 40
- **Button outline** — transparent, ink text, 1px border, pill
- **Card** — white, radius 16, padding 24, 1px `--hairline` border, `--shadow-hover` on hover only
- **Input** — white, radius 8, padding 12/16, height 44, 1px border
- **Featured panel** — `--surface-dark`, radius 16, padding 32
- **Top nav** — `--canvas`, height 64, ink text

## Layout

Max width ~1200px · 12-column editorial grid · **96px section padding** · 2-up hero splits ·
3-up benefit grids · 5-column footer.

## Principles, enforced

1. Display type never exceeds weight 300.
2. Gradient orbs are atmosphere only — never a fill behind text, never a text colour.
3. Primary CTA is the ink pill. **No saturated accent anywhere.**
4. Hairlines instead of shadows. One shadow tier exists and it is nearly invisible.
5. Pill geometry on every button and badge.

---

## Page sequence

1. **Hero — noise becomes signal.** Real replay data, not a fake loop. Raw chat accelerates, then
   collapses into three verified cards bound to one streamer quote. 64px/300 headline.
2. **Live canvas** (dark). Current stream event, top signals, evidence drawer, confidence,
   action draft.
3. **How it works.** chat + speech + frames → context → grouping → verification → approved action.
4. **Evidence, not magic.** Click a card: exact quote, frame timestamp, representative messages,
   verifier status.
5. **Measured improvement.** Baseline vs final on the frozen set, linked to raw results.
6. **Built through iteration.** Compact changelog including the removed experiment.
7. **Replay it.** CTA runs the included deterministic scenario. No signup wall.

## Mandatory UI elements (these are scored)

`Replay | Live` badge · signal type · count/share · confidence · trigger quote **or explicit
`unknown`** · representative messages · evidence drawer · `verified / uncertain / abstained` ·
trace id · latency and cost debug panel for judges.

## Delete from the current shell

The Spline blob, the glass-liquid effects as primary identity, the purple gradient bars, and
every random data generator. They read as template — the opposite of the intended impression, and
the generators are an integrity-gate risk.
