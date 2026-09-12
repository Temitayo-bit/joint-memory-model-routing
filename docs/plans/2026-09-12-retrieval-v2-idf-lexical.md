# Pilot retrieval v2 implementation plan

Date: 2026-09-12  
Status: executable once; do not re-run without a new dated plan or amendment  
Spec: `docs/specs/2026-09-12-retrieval-v2-idf-lexical-design.md`

## Objective

Ship an explicitly versioned **pilot_hybrid_v2** correction so natural-language questions get a meaningful lexical contribution in `retrieve_pilot_memory`, without raising top-k, without overfitting to Q09, and without altering frozen fixtures or recorded v1 artifacts. Do not apply remote migrations, deploy Edge Functions, provision RunPod, or run real experiments.

## File map

- Create: `docs/specs/2026-09-12-retrieval-v2-idf-lexical-design.md`
- Create: `docs/plans/2026-09-12-retrieval-v2-idf-lexical.md` (this file)
- Create: `docs/design/diagrams/2026-09-12-retrieval-v2-idf-lexical.svg`
- Create: `supabase/migrations/20260912180000_retrieve_pilot_memory_v2.sql`
- Modify: `experiments/text_baseline/constants.py`, `retrieval.py`, `run_builder.py`
- Modify: `supabase/functions/text-baseline-pilot/constants.ts`, `evidence.ts`, related Deno tests
- Create/Modify: Python + Deno tests for lexical non-collapse, Q09 evidence, Q01–Q04/Q10 coverage, SQL contract/RLS, leakage
- Modify: `experiments/text_baseline/README.md`, `docs/operations/runpod-session-runbook.md`, `architecture.md`, `docs/README.md`, `scripts/verify-text-baseline.sh` as needed

## Tasks

1. Add the dated design spec, plan, and trust-boundary diagram (after fact-check).
2. Add a new migration that `create or replace`s `retrieve_pilot_memory` with snapshot-local IDF token overlap + unchanged vector term; leave the v1 migration file untouched; comment the function with `pilot_hybrid_v2`.
3. Mirror the same lexical rules in the local harness retrieval module; record retriever version and config on evidence/manifest payloads.
4. Update Edge Function evidence labeling to `pilot_hybrid_v2` + config fields used in the evidence hash payload (RPC signature unchanged).
5. Add tests listed in the ticket/spec acceptance criteria.
6. Update operator docs: v2 is a new retrieval condition; re-run memory-enabled text baselines before voice baselines; do not delete or rewrite v1 results.
7. Run `make test` and `make build`.
8. Subtask-review, commit, push, open a PR (do not merge).

## Constraints

- Branch from updated `main` only; keep `docs/api-first-community-pods` separate.
- No Supabase apply/deploy, no RunPod, no live inference.
- Do not invent experimental results.
- Preserve questions, memory fixture, scoring anchors, and model settings.
- Security posture unchanged: invoker RPC, empty `search_path`, ownership + supervised checks, JWT required, no service_role in migration SQL, anchors never in prompts.
