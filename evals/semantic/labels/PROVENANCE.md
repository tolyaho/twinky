# Provenance of these labels

**Model-drafted, not human-reviewed (`reviewed: false` for every file here).**

- Written on 2026-10-31 by ten independent Claude subagents, each given only `../LABELING.md`
  and the numbered text views of its windows (`../windows/*.txt`). None saw the grouping code,
  the other labellers' files, or any result. None ran code.
- `<window>.opus.json` — Claude Opus 5.5, every window. These are the primary labels.
- `<window>.sonnet.json` — Claude Sonnet 5.5, the six test windows only, written without access
  to the Opus files. The agreement between the two is reported as the ceiling a method can be
  expected to reach on these windows.
- Every message number is labelled in every file (checked mechanically; nothing was edited).
- Some files carry a `"reviewed": false` field and some do not; the field was not in the
  guide's schema. This manifest is the authority: none of these labels has been reviewed by a
  person.
- Frozen in `../labels.sha256` (together with the windows, the split and the guide) before any
  grouping method was scored or tuned against them. `web/eval/data.ts` refuses to score if any
  frozen file has changed.

Labellers noted their own close calls in their hand-back reports. They are summarised in
`../README.md`, "Where the labels are uncertain".
