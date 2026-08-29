# Improvement changelog

Baseline → iterations → final. Every row carries evidence and a kept/revised/removed decision.
Update as work happens.

## Pre-existing research (Sept 2025 – Mar 2026) — NOT competition work

Context for why the competition baseline is shaped the way it is. Not counted as measured
hackathon improvement.

| Period | What was learned | How it shapes the competition entry |
|---|---|---|
| Sept 2025 | Local CPU STT accumulated lag; Deepgram was accurate and ~$0.6/hr | Hosted streaming STT, capture-then-replay |
| Oct 2025 | Lexical embedding clustering gave unstable clusters; context conditioning raised cosine similarity from 0.784 to 0.935 on a probe pair | Motivates event-centric grounding over similarity clustering |
| Jan 2026 | Per-message reason extraction worked but cost ~$0.05 / 5 min on an active chat and had a long latency tail (median ~1s, mean ~7s, ~30s under load) | Motivates the deterministic reducer and event-centric batching |
| Jan 2026 | Observed failure: generated clusters sometimes attached to no real cause | Motivates the provenance gate and abstention — and metric B |
| Mar 2026 | `gpt-4.1-mini` 10–30s vs `gpt-4.1-nano` 1–3s | Latency-first model selection |
| Mar 2026 | Multi-agent/RAG sketch produced a working prototype but no measured benefit | Scoped out; candidate removed experiment |

## Competition iterations (28–31 Aug 2026)

<!-- TODO: one row per measured iteration. No row without evidence in evidence/. -->

| Stage | What was tried and why | Evidence / result | Decision / learning |
|---|---|---|---|
| Baseline | Single prompt over the same raw multimodal events | `evidence/raw-results/baseline_*.json` | *pending* |
| Ablation | Chat-only input, to isolate the contribution of speech and frames | *pending* | Diagnostic only |
| Iteration 1 | Deterministic dedup / burst reduction | *pending* | *pending* |
| Iteration 2 | Bounded context tools | *pending* | *pending* |
| Iteration 3 | Provenance gate + abstention | *pending* | *pending* |
| Iteration 4 | Separate LLM verifier | *pending* | Keep only if it lowers the unsupported rate enough to justify latency and cost |
| Final | Combination of what measurably helped | *pending* | *pending* |

## Main failure mode

*pending — must be a real observed one, with a case id.*

## Hot take

> The hard part of live-chat intelligence is not summarization. It is proving which stream event
> caused which audience signal — and knowing when the evidence is insufficient.

*Expand with the concrete failure that produced it and what it changes for the next build.*
