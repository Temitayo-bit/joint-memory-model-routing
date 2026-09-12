# Pilot retrieval v2.1 implementation plan

Date: 2026-09-12  
Status: executable once; do not re-run without a new dated plan or amendment  
Spec: `docs/specs/2026-09-12-retrieval-v2-1-stopwords-design.md`

## Objective

Ship an explicitly versioned **pilot_hybrid_v2_1** condition that keeps the v2 IDF/cosine/top-k contract while applying the fixed PostgreSQL 17 English Snowball stopword list before token-set and document-frequency calculation. Restore Q09’s Python harness fact to top-4 under the pinned MiniLM similarities without raising top-k, without editing the applied v2 migration, and without altering frozen fixtures or recorded v1/v2 artifacts. Do not apply remote migrations, deploy Edge Functions, provision RunPod, or run real experiments.

## File map

- Create: `docs/specs/2026-09-12-retrieval-v2-1-stopwords-design.md`
- Create: `docs/plans/2026-09-12-retrieval-v2-1-stopwords.md` (this file)
- Create: `docs/design/diagrams/2026-09-12-retrieval-v2-1-stopwords.svg`
- Create: `supabase/migrations/20260912210000_retrieve_pilot_memory_v2_1.sql`
- Create: `experiments/text_baseline/data/q09_minilm_similarities.json` (pinned measured similarities from the existing v2 embeddings bundle)
- Create/Modify: `experiments/text_baseline/constants.py`, `retrieval.py`, tests
- Modify: `supabase/functions/text-baseline-pilot/constants.ts`, Deno evidence-hash test
- Modify: SQL contract tests and `scripts/verify-text-baseline.sh`
- Modify: operator/docs references (`architecture.md`, READMEs, runbook, evaluation protocol)

## Tasks

1. Add the dated design spec, plan, and trust-boundary diagram (after fact-check of the PostgreSQL 17 English stopword list).
2. Add a new migration that `create or replace`s `retrieve_pilot_memory` with the v2.1 stopword filter; leave the v2 migration file untouched; comment the function with `pilot_hybrid_v2_1` and stopword identity.
3. Mirror the same stopword + IDF rules in the local harness retrieval module; record retriever version, stopword identity/source/count, and config on evidence/manifest payloads.
4. Update Edge Function evidence labeling to `pilot_hybrid_v2_1` + stopword fields used in the evidence hash payload (RPC signature unchanged).
5. Add regression coverage: pinned MiniLM Q09 hybrid ranks `M05` in top-4; Q01–Q04 and Q10–Q12 retain required evidence; SQL contract/RLS static checks; stopword count 127.
6. Update operator docs: v2.1 is a new retrieval condition; after remote migration and Edge deploy, produce fresh S1/L1 exports/runs; S0/L0 and v1 artifacts remain unchanged; preserve the existing v2 preflight export.
7. Run `make test` and `make build`.
8. Subtask-review when requested; do not push, open a PR, merge, deploy, or apply migrations in this Cursor pass.

## Constraints

- Stay on `fix/retrieval-v2-idf-lexical`; do not switch branches or overwrite unrelated work.
- No Supabase apply/deploy, no RunPod, no live inference.
- Do not invent experimental results.
- Preserve questions, memory fixture, scoring anchors, model settings, v1 artifacts, and the v2 preflight export.
- Scoring anchors never enter prompts.
- Security posture unchanged: invoker RPC, empty `search_path`, ownership + supervised checks, JWT required, no service_role in migration SQL.
