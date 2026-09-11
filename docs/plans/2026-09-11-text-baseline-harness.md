# Text-baseline harness implementation plan

Date: 2026-09-11  
Status: executable once; do not re-run without a new dated plan or amendment

## Objective

Implement the local 48-cell text-baseline harness and the undeployed supervised one-request live path specified in `docs/specs/2026-09-11-text-baseline-harness-design.md`. Do not design a controller. Do not add voice. Do not provision GPU or apply remote Supabase changes.

## File map

- Create: `experiments/text_baseline/` Python package (fixtures, retrieval plumbing, schedule, mock/export/import, costs, CLI, tests)
- Create: `supabase/migrations/20260911000000_pilot_text_baseline.sql`
- Create: `supabase/functions/text-baseline-pilot/` Deno modules and tests
- Create: `supabase/config.toml` (function name + `verify_jwt = true` only)
- Modify: `Makefile`, `scripts/verify-foundation.sh`, `.github/workflows/ci.yml`, `architecture.md`, `README.md`, `docs/research/evaluation-protocol.md`, `.gitignore`

## Tasks

1. Add synthetic fixtures (12 questions, separate memory and scoring files) and canonical hashing helpers.
2. Implement lexical fixture retrieval labeled as plumbing; enforce S0/L0 bypass and S1/L1 identical evidence.
3. Implement schedule (48 cells, bounded repeats, seeded shuffle) and prompt assembly that cannot see scoring anchors.
4. Implement mock, export-requests, import-responses, overwrite protection, and three separate cost fields that stay null unless supplied/computable.
5. Add Python unit tests listed in the spec (coverage, reproducibility, isolation, evidence equality, leakage, malformed measurements, duplicate/missing/failed/tampered, overwrite, costs).
6. Add the owner-scoped immutable snapshot migration with invoker RPCs and RLS.
7. Add the Edge Function handler and pure validation modules (JWT/allowlist, payload, embeddings, generation settings, redirect/size, duplicate/throttle, pending write).
8. Add Deno tests with `--check` covering the live-path cases in the ticket.
9. Pin CI SHAs, run Python + Deno in `make test`/`make build`, add a local SQL contract check, and attempt `supabase db lint` only if a local database exists.
10. Subtask-review the branch, remove caches/secrets/generated artifacts, commit, push, open a **draft** PR. Do not merge.

## Constraints (copied from the spec)

- Python 3.9+; standard library where practical.
- Mock runs leave latency, tokens, quality, and all three cost fields null.
- Do not invent measurements or claim mock output as research results.
- Small/large are aliases. Do not claim live Qwen verification.
- No RunPod, no remote migrations, no Edge deploy, no live inference, no spend.
