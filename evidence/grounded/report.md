# Evaluation report

> **NOT THE SHIPPED RESULT.** This report was written to `grounded/`, not to `evidence/`, so it is an experimental arm rather than the published comparison. The shipped numbers are in `evidence/report.md`, and `docs/IMPROVEMENT_CHANGELOG.md` states which arms were rolled back and why.

| system | cases | cards | trigger accuracy | unmatched | unsupported | recall |
|---|---:|---:|---:|---:|---:|---:|
| ablation_chat_only | 11 | 25 | 1.000 | 0.960 | 0.280 | 0.091 |
| agent | 11 | 23 | 0.500 | 0.913 | 0.739 | 0.182 |
| agent_grounded | 11 | 17 | 0.000 | 0.882 | 0.882 | 0.182 |
| baseline | 11 | 21 | 0.000 | 0.952 | 0.619 | 0.091 |

## Fixtures behind these numbers

| fixture | kind | channel | cases | provenance |
|---|---|---|---|---|
| `marlon_2026-08-30T0701` | capture | marlon | 2 | Captured from a public Twitch broadcast. Chatter logins pseudonymised at capture time with a local salt that is not distributed. Raw audio is not committed; only the derived transcript is. |
| `marlon_2026-08-30T0715` | capture | marlon | 4 | Captured from a public Twitch broadcast. Chatter logins pseudonymised at capture time with a local salt that is not distributed. Raw audio is not committed; only the derived transcript is. |
| `stableronaldo_2026-08-30T0723` | capture | stableronaldo | 3 | Captured from a public Twitch broadcast. Chatter logins pseudonymised at capture time with a local salt that is not distributed. Raw audio is not committed; only the derived transcript is. |
| `yugi_2026-08-30T0723` | capture | yugi | 2 | Captured from a public Twitch broadcast. Chatter logins pseudonymised at capture time with a local salt that is not distributed. Raw audio is not committed; only the derived transcript is. |

Trigger accuracy counts only cards that matched a gold signal, so it cannot be
lowered by emitting noise. Read it next to `unmatched`, which is the fraction of
emitted cards matching no gold signal at all.

Both systems are scored on every card they emit, verified and rejected alike.
Latency and cost are deliberately absent: a replay run reads cached responses, so
timing it would measure disk, not the model. Cost is tracked in `COST_LEDGER.md`.

Every number above is reproduced by `make eval` from the committed
model-response cache, with no API keys and zero cost.
