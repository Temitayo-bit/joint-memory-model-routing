# Pilot retrieval v2: snapshot-local IDF lexical scoring

**Decision date:** 2026-09-12  
**Status:** approved direction for repository implementation; remote migration/deploy and baseline reruns remain operator/Codex work

## Decision

Replace the v1 `retrieve_pilot_memory` lexical component—`ts_rank_cd(..., plainto_tsquery('simple', full_question))`—with an explicitly versioned **pilot_hybrid_v2** scorer that gives natural-language questions a non-degenerate lexical contribution.

Keep frozen questions, memory fixtures, scoring anchors, model/generation settings, and recorded **v1** artifacts unchanged. Do not raise retrieval `top-k` to hide a dead lexical term. Memory-enabled text baselines (S1/L1) must be re-run under v2 before any voice baselines that claim the same retrieval condition.

## Problem (observed, not invented)

On the completed v1 text baseline, Q09 failed in both memory-enabled conditions. The correct memory item (“The local experiment harness for this project is written in Python”) ranked fifth while the Edge Function requested four items. With v1 lexical scoring, `lexical_rank` was **0 for every candidate**, so ranking reduced to vector similarity alone.

## Verified claims — checked 2026-09-12

- PostgreSQL `plainto_tsquery` inserts the `&` (AND) operator between surviving words, so the resulting query matches documents containing **all** non-stopword terms. Source: [PostgreSQL 18 text search controls](https://www.postgresql.org/docs/current/textsearch-controls.html) and [text search functions](https://www.postgresql.org/docs/current/functions-textsearch.html) (checked 2026-09-12).
- `websearch_to_tsquery` still ANDs ordinary unquoted terms; it is **not** a drop-in fix for long natural-language questions. Same sources (checked 2026-09-12).
- `ts_rank` / `ts_rank_cd` rank a document against a `tsquery`; they do **not** supply collection-wide IDF over the snapshot. Same sources (checked 2026-09-12).
- This repository’s live path already combines lexical rank with cosine similarity `1 - (embedding <=> query)` inside `SECURITY INVOKER` `retrieve_pilot_memory`, default limit 4 / hard cap 8. Source: `supabase/migrations/20260911000000_pilot_text_baseline.sql` (repository, checked 2026-09-12).
- Snapshot ownership, `pilot_supervised()`, RLS, call-claim RPCs, and JWT `verify_jwt = true` remain the authorization boundary. Source: same migration and `supabase/config.toml` (checked 2026-09-12).

## Component inventory

| Component | Version / pin | Responsibility | Communicates with |
| --- | --- | --- | --- |
| `retrieve_pilot_memory` (SQL) | **pilot_hybrid_v2** via new migration | Owner-scoped hybrid rank: snapshot IDF token overlap + vector similarity; limit 4 (max 8) | `pilot_memory_*` tables, `auth.uid()`, `pilot_supervised()` |
| Local harness retrieval | **pilot_hybrid_v2** lexical mirror | Plumbing validation with the same token/IDF rules (no vectors locally) | Synthetic fixtures only |
| Edge Function `text-baseline-pilot` | Deno modules | Calls RPC unchanged; records retriever version/config in evidence hash payload | PostgREST RPC |
| Frozen fixtures | existing JSON | Unchanged questions, memory, scoring anchors | Harness / operator loaders |
| Operator docs | runbook + README | State that v2 is a new retrieval condition requiring S1/L1 text reruns before voice | Operators / Codex |

## Retrieval v2 scoring (normative)

Tokens: lowercase alphanumeric runs matching `[A-Za-z0-9]+` (PostgreSQL `simple`-style; no stemming).

For a caller-owned supervised snapshot with \(N\) items:

1. Build document token sets and document frequencies \(df(t)\).
2. For each query token \(t\): \(\mathrm{idf}(t) = \ln\frac{N+1}{df(t)+1} + 1\) (missing \(df\) treated as 0).
3. \(\mathrm{lexical\_rank}(d) = \frac{\sum_{t \in Q \cap d} \mathrm{idf}(t)}{\sum_{t \in Q} \mathrm{idf}(t)}\) (0 if the query has no tokens).
4. \(\mathrm{vector\_similarity}(d) = 1 - (d.\mathrm{embedding} \Leftrightarrow q)\) unchanged.
5. \(\mathrm{combined\_score} = \mathrm{lexical\_rank} + \mathrm{vector\_similarity}\).
6. Order by `combined_score` desc, `item_id` asc; `limit least(greatest(p_limit,1), 8)` with default `p_limit = 4`.

Recorded configuration (minimum):

```json
{
  "retriever": "pilot_hybrid_v2",
  "lexical": "snapshot_idf_token_overlap",
  "vector": "cosine_similarity_1_minus_distance",
  "combined": "lexical_rank_plus_vector_similarity",
  "limit": 4,
  "limit_cap": 8,
  "token_pattern": "[A-Za-z0-9]+",
  "idf": "ln((N+1)/(df+1))+1"
}
```

### Alternatives rejected

- **Only increase `top-k`:** conceals zero lexical ranks; forbidden by the task.
- **`websearch_to_tsquery` alone:** still ANDs ordinary terms for NL questions.
- **OR-joined `to_tsquery` / uniform token overlap alone:** restores non-zero ranks but still leaves the Q09 Python harness fact outside top-4 on lexical signal alone in this fixture (common tokens dominate; “harness” is rare). Snapshot IDF is the minimal IR correction that restores discriminative lexical mass without a Q09 hard-code.
- **Editing or deleting v1 result artifacts:** reproducibility requires preserving them as the v1 condition.

## Trust boundaries

See [the retrieval-v2 diagram](../design/diagrams/2026-09-12-retrieval-v2-idf-lexical.svg).

- **Laptop:** fixtures, local IDF mirror, optional embeddings bundle. Transient.
- **Supabase:** durable snapshot rows; ranking runs as the authenticated invoker under RLS/`pilot_supervised()`.
- **Model server:** receives prompt + retrieved content only; never scoring anchors, never Supabase credentials.
- **GitHub:** code, fixtures, specs; no live secrets; v1 aggregates remain as historical condition evidence when present.

## Unverified assumptions

- Live cosine ranks for the twelve questions under the pinned MiniLM revision are not re-measured in this change. Settle when operators re-run S1/L1 after applying the migration and redeploying the function.
- Exact PostgreSQL major version on the free-tier Supabase project is not pinned in-repo. Settle from the project’s reported Postgres version before apply if a function body fails to parse.
- Whether IDF-weighted lexical + vector will change any non-Q09 memory cell answers is unverified until the v2 text rerun. Settle by comparing v2 S1/L1 scores to frozen v1 summaries without overwriting v1 files.
