# Text benchmark v2: held-out memory and model-routing evaluation

**Decision date:** 2026-09-13  
**Status:** approved direction; implementation and live evaluation have not started

## Decision

Keep the recorded 12-question `synthetic-northriver-pilot-v1` benchmark unchanged as a setup/debugging pilot. Add a separate synthetic **text benchmark v2** with two non-overlapping splits:

| Split | Purpose | Questions | Live-use rule |
| --- | --- | ---: | --- |
| `benchmark-v2-dev` | Development/calibration | 16 | May inform implementation checks and later controller design; never report it as the final result. |
| `benchmark-v2-eval` | Held-out evaluation | 48 | Freeze before any model call; use for fixed-baseline and later controller reporting. |

The 48 held-out questions are balanced across four twelve-question strata:

| Stratum | Long-term memory needed? | Reasoning demand | Intended diagnostic |
| --- | --- | --- | --- |
| A | No | direct / low | A small model should handle the request without memory. |
| B | No | compositional / high | Is a stronger model useful when the answer follows only from the supplied request but requires multi-step reasoning? |
| C | Yes | direct / low | Does retrieval supply an otherwise unavailable synthetic fact? |
| D | Yes | compositional / high | Can the model combine retrieved evidence, respect updates/conflicts, or appropriately abstain? |

This is a benchmark redesign, not a retrieval redesign. Memory-enabled v2 runs use the deployed `pilot_hybrid_v2_1` retriever unchanged. The existing v1 and retrieval-v2.1 artifacts remain separate historical conditions.

## Why the pilot is insufficient for model routing

The completed 12-question pilot scored S0 `6/12`, S1 `12/12`, L0 `6/12`, and L1 `12/12` after retrieval v2.1. It establishes that retrieval mattered on that pilot, but it does not establish a quality difference between Qwen3-4B-AWQ and Qwen3-14B-AWQ. A controller that always chose the small model after making the right retrieval decision would tie the large-model result on those questions.

The new benchmark therefore tests a different, necessary question: whether the larger model provides a measurable marginal quality benefit for a pre-specified class of requests. This follows the quality-versus-cost model-selection problem studied by [RouteLLM](https://arxiv.org/abs/2406.18665) (checked 2026-09-13); it does not adopt RouteLLM's training method or claim its results.

The memory-focused question families draw only on the publicly described ability categories in [LongMemEval](https://arxiv.org/abs/2410.10813) (checked 2026-09-13): extraction, multi-session reasoning, temporal reasoning, knowledge updates, and abstention. Benchmark v2 uses newly authored Northriver synthetic fixtures; it does not copy LongMemEval data or claim to reproduce that benchmark.

## Dataset and fixture contract

### Legacy preservation

- Leave `experiments/text_baseline/data/` and its twelve questions, memory items, anchors, hashes, request exports, imports, and analysis untouched.
- The legacy default remains usable for reproduction of the recorded pilot.
- Benchmark v2 uses separate dataset directories and artifact paths. No v2 run may reuse a legacy request ID, response file, manifest, score file, or snapshot.

### New fixtures

Each new split contains its own synthetic memory, questions, and scoring anchors. A dataset manifest identifies the dataset name, version, split, expected question count, stratum counts, and permitted generation seeds.

The evaluation split contains 48 newly authored questions and a synthetic Northriver evidence set with dated facts, supporting passages, and distractors. Each memory-dependent scoring anchor identifies the required evidence IDs; no question requires more than two evidence items for its correct answer, keeping a top-four retrieval limit meaningful. The evidence identifiers and anchors must never enter a model prompt.

Question text may require a concise explanation when reasoning is part of the task. Scoring remains deterministic and anchor-based:

1. correct conclusion or correct abstention;
2. all required facts/constraints satisfied;
3. no contradicted or superseded fact asserted.

The primary score is binary per response. Diagnostic fields record conclusion correctness, reasoning/support correctness when requested, abstention correctness, and required-evidence recall at four retrieved items. Diagnostics do not replace the pre-registered primary score.

### Required question families

The four strata are the balancing contract, not the only labels. Every question also receives one or more of the following non-prompt tags in its scoring data:

- direct extraction;
- multi-record composition;
- temporal update;
- conflict resolution;
- constraint or arithmetic reasoning;
- distractor resistance;
- unsupported-information abstention.

The high-reasoning strata use self-contained, auditable constraints and synthetic evidence rather than obscure world facts. The goal is to measure reasoning and evidence use, not whether either model memorized a fact during pretraining.

## Development and held-out discipline

All 64 questions, their split membership, required evidence, scoring anchors, and generation-seed protocol are committed before either model receives a benchmark-v2 question. The development split may support harness validation and later controller-threshold design, but it is excluded from the reported fixed-baseline and controller comparison. The evaluation split is never edited in response to development or evaluation model outputs.

Benchmark v2 must not be tuned until the 14B model wins. A valid outcome is that the models still have no material difference on the held-out set; that result would narrow the project's justified controller claim toward memory routing rather than fabricate a model-routing benefit.

## Generation, schedule, and measurement

Benchmark v2 uses three pre-registered generation seeds: `42`, `43`, and `44`. The schedule-order seed remains a separate reproducibility control. Each request records both values so a generation seed cannot be confused with the schedule shuffle seed.

The held-out text baseline therefore has 576 scored cells:

```text
48 evaluation questions × 4 fixed conditions × 3 generation seeds = 576
```

The sixteen development questions use the same fixture and scoring safeguards, but their results are explicitly labeled development-only. No live evaluation begins until the new fixture hashes, embeddings, request exports, and import validation pass locally.

For a direct model-latency comparison, run both models on the same Secure Cloud GPU class, server image, server version, and request configuration. The exact GPU class, availability, hourly rate, and model readiness must be checked immediately before the session; they are not asserted here. The production-like deployment cost of separate model resources may be recorded separately, but it must not be used to attribute a latency difference to model size alone.

Record, per run and per stratum:

- complete-response rate and primary quality score;
- diagnostic quality dimensions and correct-abstention rate;
- retrieval recall at four for memory-dependent questions;
- model-generation, retrieval, and end-to-end latency, including percentiles;
- input/output tokens;
- market-priced generation estimate, allocated processing cost, and actual rental/service spending as distinct fields;
- model revision, quantization, server image/version, GPU, retriever version, fixture hashes, schedule seed, and generation seed.

## Component inventory

| Component | Version / identity | Responsibility | Communicates with |
| --- | --- | --- | --- |
| Legacy pilot dataset | `synthetic-northriver-pilot-v1` | Preserved setup/debugging benchmark | Existing local harness and recorded artifacts |
| Benchmark-v2 dataset manifests | New repository JSON | Declare split, counts, seed set, and fixture identity | Local harness and tests |
| Text-baseline harness | Existing Python package | Build schedules/requests, preserve hashes, import measured evidence | Local dataset files; supervised live path |
| Scoring anchors | New repository JSON, non-prompt | Define pre-registered quality/evidence checks | Local scoring and analysis only |
| Supabase Edge Function | Existing `text-baseline-pilot` | Owner-scoped retrieval and one supervised model call | Supabase RPC and active model server |
| Hybrid retriever | `pilot_hybrid_v2_1` | Top-four evidence retrieval for S1/L1 | Supabase snapshot data |
| Qwen model servers | Existing pinned 4B/14B AWQ candidates | Fixed-generation inference only | Edge Function or supervised direct client |
| RunPod Secure Cloud | Selected at live-session time | Temporary matched-hardware inference | Model server only |

No new service, credential, data-flow boundary, or durable store is introduced. The existing trust-boundary diagram remains accurate, so this fixture-only design does not require a new diagram.

## Implementation boundaries

- Add named-dataset support rather than replacing the legacy fixture directory.
- Make question count and stratum validation dataset-manifest driven; retain exact twelve-question validation for the legacy dataset.
- Add a separate request-level generation-seed field and allow-list only the three benchmark-v2 seeds.
- Preserve the existing fixed generation parameters except for the explicitly recorded benchmark-v2 seed value.
- Keep scoring anchors, evidence requirements, and diagnostic tags inaccessible to prompt construction.
- Add test coverage for split disjointness, fixture hashes, stratum balance, seed/cardinality calculation, no-anchor leakage, and legacy-pilot compatibility.
- Do not create a controller, alter the retrieval formula, apply a migration, deploy an Edge Function, provision a RunPod pod, or make any live request in the implementation pull request.

## Unverified assumptions

- Whether any benchmark-v2 stratum yields a material 14B-over-4B quality advantage is unverified. Only completed held-out live runs can settle it.
- Whether the current 14B AWQ server configuration and the 4B configuration can be run on the same available Secure Cloud GPU class is unverified. Settle it with current availability, a non-scored readiness check, and recorded server configuration before the live session.
- Current RunPod stock, rate, provider line items, and the full cost of the 576-cell held-out run are unverified and must be checked live before spending.
- Whether three generation seeds expose meaningful variation for the selected server is unverified. The seeds are pre-registered for reproducibility and must be reported even if outputs coincide.
- Voice conditions are out of scope for this fixture change. The later voice protocol must preserve this held-out split and separately define ASR/TTS/turn-taking measures.
