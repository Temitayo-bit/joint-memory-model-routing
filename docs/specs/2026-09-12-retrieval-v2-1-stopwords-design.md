# Pilot retrieval v2.1: English Snowball stopword IDF lexical scoring

**Decision date:** 2026-09-12  
**Status:** approved direction for repository implementation; remote migration/deploy and baseline reruns remain operator/Codex work

## Decision

Add an explicitly versioned **pilot_hybrid_v2_1** retriever that keeps the v2 snapshot-local IDF formula, cosine similarity, equal lexical-plus-vector combined score, top-k 4, and limit cap 8, while applying a fixed **127-word** English stopword set before query/document token sets and document frequencies.

Keep frozen questions, memory fixtures, scoring anchors, model/generation settings, recorded **v1** artifacts, and the existing **v2** preflight export unchanged. Do not edit the already-applied v2 migration. Do not raise retrieval `top-k` to hide ranking failures. Memory-enabled text baselines (S1/L1) must be re-exported/re-run under v2.1 after remote migration and Edge redeploy; S0/L0 and all v1 artifacts remain unchanged.

## Problem (observed, not invented)

Deployed **pilot_hybrid_v2** ranks Q09’s required Python harness fact (`M05`) fifth of eight under the pinned MiniLM vectors (combined ≈ 0.3660115583) while the fourth item scores ≈ 0.3802433219, so top-k 4 omits the fact despite passing the prior lexical unit tests. Root cause: the v2 IDF tokenizer still counts common English function words, giving irrelevant Northriver-related passages lexical credit.

With the PostgreSQL 17 English Snowball stopword list and the same pinned local vectors, `M05` ranks **2** at combined ≈ 0.367627325. Expected top five IDs: `M07`, `M05`, `M06`, `P03`, `P04`.

## Verified claims — checked 2026-09-12

- PostgreSQL 17 ships a built-in Snowball `english_stem` dictionary configured with `StopWords = english`. Source: [PostgreSQL 17 text search dictionaries](https://www.postgresql.org/docs/17/textsearch-dictionaries.html) (checked 2026-09-12).
- The English stopword file in the PostgreSQL 17 source tree contains **127** words (one per line). Source: [REL_17_STABLE `english.stop`](https://raw.githubusercontent.com/postgres/postgres/REL_17_STABLE/src/backend/snowball/stopwords/english.stop) (checked 2026-09-12; count verified locally from that file).
- Stopwords are part of the dictionary configuration (Snowball `StopWords` option), not a general SQL API that returns the built-in English list as rows. Same dictionaries documentation (checked 2026-09-12).
- This repository’s v2 path already combines snapshot IDF token overlap with cosine similarity `1 - (embedding <=> query)` inside `SECURITY INVOKER` `retrieve_pilot_memory`, default limit 4 / hard cap 8. Source: `supabase/migrations/20260912180000_retrieve_pilot_memory_v2.sql` (repository, checked 2026-09-12).
- Snapshot ownership, `pilot_supervised()`, RLS, call-claim RPCs, and JWT `verify_jwt = true` remain the authorization boundary. Source: `20260911000000_pilot_text_baseline.sql` and `supabase/config.toml` (checked 2026-09-12).

## Component inventory

| Component | Version / pin | Responsibility | Communicates with |
| --- | --- | --- | --- |
| `retrieve_pilot_memory` (SQL) | **pilot_hybrid_v2_1** via new migration | Owner-scoped hybrid rank: stopword-filtered snapshot IDF + vector similarity; limit 4 (max 8) | `pilot_memory_*` tables, `auth.uid()`, `pilot_supervised()` |
| Local harness retrieval | **pilot_hybrid_v2_1** lexical mirror | Plumbing validation with the same token/IDF/stopword rules | Synthetic fixtures; optional pinned MiniLM similarities for hybrid tests |
| Edge Function `text-baseline-pilot` | Deno modules | Calls RPC unchanged; records retriever version, stopword identity/source, and config in evidence hash payload | PostgREST RPC |
| Frozen fixtures | existing JSON | Unchanged questions, memory, scoring anchors | Harness / operator loaders |
| Pinned Q09 similarities | `q09_minilm_similarities.json` | Measured cosine similarities from the existing v2 MiniLM embeddings bundle (not fabricated ranks) | Hybrid regression tests |
| Operator docs | runbook + README | State that v2.1 is a new retrieval condition requiring fresh S1/L1 exports/runs | Operators / Codex |

## Retrieval v2.1 scoring (normative)

Tokens: lowercase alphanumeric runs matching `[A-Za-z0-9]+` (PostgreSQL `simple`-style; no stemming), then drop any token in the fixed 127-word `postgresql_17_english_snowball` set **before** building query/document token sets and document frequencies.

For a caller-owned supervised snapshot with \(N\) items:

1. Build stopword-filtered document token sets and document frequencies \(df(t)\).
2. For each remaining query token \(t\): \(\mathrm{idf}(t) = \ln\frac{N+1}{df(t)+1} + 1\) (missing \(df\) treated as 0).
3. \(\mathrm{lexical\_rank}(d) = \frac{\sum_{t \in Q \cap d} \mathrm{idf}(t)}{\sum_{t \in Q} \mathrm{idf}(t)}\) (0 if the filtered query has no tokens).
4. \(\mathrm{vector\_similarity}(d) = 1 - (d.\mathrm{embedding} \Leftrightarrow q)\) unchanged.
5. \(\mathrm{combined\_score} = \mathrm{lexical\_rank} + \mathrm{vector\_similarity}\).
6. Order by `combined_score` desc, `item_id` asc; `limit least(greatest(p_limit,1), 8)` with default `p_limit = 4`.

Recorded configuration (minimum):

```json
{
  "retriever": "pilot_hybrid_v2_1",
  "lexical": "snapshot_idf_token_overlap",
  "vector": "cosine_similarity_1_minus_distance",
  "combined": "lexical_rank_plus_vector_similarity",
  "limit": 4,
  "limit_cap": 8,
  "token_pattern": "[A-Za-z0-9]+",
  "idf": "ln((N+1)/(df+1))+1",
  "stopwords": "postgresql_17_english_snowball",
  "stopword_count": 127,
  "stopword_source": "https://raw.githubusercontent.com/postgres/postgres/REL_17_STABLE/src/backend/snowball/stopwords/english.stop"
}
```

### Alternatives rejected

- **Only increase `top-k`:** conceals stopword-driven lexical noise; forbidden by the task.
- **Edit the applied v2 migration in place:** breaks migration history; v2.1 must be a new replace migration.
- **Ad-hoc domain stopword list:** less reproducible than an explicitly versioned primary-source list.
- **Editing or deleting v1/v2 result artifacts:** reproducibility requires preserving them as prior conditions.

## Trust boundaries

See [the retrieval-v2.1 diagram](../design/diagrams/2026-09-12-retrieval-v2-1-stopwords.svg).

- **Laptop:** fixtures, local IDF+stopword mirror, optional embeddings bundle / pinned similarities. Transient.
- **Supabase:** durable snapshot rows; ranking runs as the authenticated invoker under RLS/`pilot_supervised()`.
- **Model server:** receives prompt + retrieved content only; never scoring anchors, never Supabase credentials.
- **GitHub:** code, fixtures, specs; no live secrets; prior aggregates remain historical condition evidence when present.

## Unverified assumptions

- Exact PostgreSQL major version on the free-tier Supabase project is not pinned in-repo. The stopword list is embedded as a fixed array in SQL rather than read from the server’s Snowball files at runtime. Settle from the project’s reported Postgres version before apply if a function body fails to parse.
- Whether stopword-filtered IDF + vector will change any non-Q09 memory cell answers is unverified until the v2.1 text rerun. Settle by comparing v2.1 S1/L1 scores to frozen prior summaries without overwriting those files.
- Live SQL numeric equality with the local Python mirror for every question beyond the pinned Q09 regression is unverified until operators apply the migration.
