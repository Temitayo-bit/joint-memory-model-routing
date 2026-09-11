# Text-baseline harness and supervised one-request live path

**Decision date:** 2026-09-11  
**Status:** approved direction for implementation in this repository; no live infrastructure is provisioned by this change

## Decision

Establish four **fixed** text baselines before any dynamic controller or voice pipeline:

| ID | Model | Long-term memory |
| --- | --- | --- |
| S0 | small | none |
| S1 | small | retrieve |
| L0 | large | none |
| L1 | large | retrieve |

The research order is: (1) fixed text baselines, (2) fixed voice baselines, (3) controller design, (4) controller evaluation for text and voice. This specification covers only (1) plus a **prepared, undeployed** supervised one-question live path.

A local Python harness produces the complete 12-question × 4-condition matrix, keeps scoring data out of prompts, and records mock, exported, failed, and imported-measured results without inventing measurements. A separate Supabase migration and Edge Function prepare one authenticated live request. They are not applied or deployed here.

## Verified claims — checked 2026-09-11

- Qwen3 non-thinking sampling guidance is temperature **0.7**, top_p **0.8**, top_k **20**, and min_p **0**. Source: [Qwen3 quickstart](https://qwen.readthedocs.io/en/latest/getting_started/quickstart.html). This repository adopts those sampling values plus `max_tokens = 256` and `seed = 42` as **fixed request settings**. It does not claim that any Qwen artifact, quantization, or server has been verified on this project's infrastructure.
- Hybrid Qwen3 models expose a hard switch `enable_thinking=False` / `chat_template_kwargs.enable_thinking = false` for non-thinking mode on OpenAI-compatible servers. Source: [Qwen3 quickstart](https://qwen.readthedocs.io/en/latest/getting_started/quickstart.html). Whether the yet-unselected self-hosted server honors that field is unverified.
- `sentence-transformers/all-MiniLM-L6-v2` maps text to a **384-dimensional** vector. Source: [model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2). The live path therefore stores `extensions.vector(384)` and requires a client-supplied unit vector of length 384 for memory conditions. The laptop embedding step is not executed in this change.
- Supabase documents `extensions.vector(384)` columns, cosine distance `<=>`, and wrapping similarity queries in Postgres functions because PostgREST does not expose vector operators. Source: [Vector columns](https://supabase.com/docs/guides/ai/vector-columns).
- pgvector cosine similarity is `1 - (embedding <=> query)` when using `<=>`. Source: [Vector columns](https://supabase.com/docs/guides/ai/vector-columns).
- RLS continues to restrict rows returned by vector search when queries run as the invoking user. Source: [RAG with permissions](https://supabase.com/docs/guides/ai/rag-with-permissions).
- Database functions should use `SECURITY INVOKER` (the default) and pin `search_path`. An empty path (`set search_path = ''`) requires schema-qualified names. Source: [Database functions](https://supabase.com/docs/guides/database/functions) and [Advisor 0011](https://supabase.com/docs/guides/observability/advisors).
- Authenticated Edge Functions should keep `verify_jwt` enabled. This prepared function forwards the caller's JWT to PostgREST so RLS and invoker RPCs apply — the same trust model as `withSupabase({ auth: 'user' })`. The official `npm:@supabase/server` wrapper is not vendored here so CI type-checking stays hermetic. Source for the documented wrapper: [Edge Function authentication](https://supabase.com/docs/guides/functions/auth).
- `deno test` type-checks local modules by default; `--check` is redundant for local files and `--check=all` also type-checks remote modules. Source: [deno test](https://docs.deno.com/runtime/reference/cli/test/). This repository still passes `--check` so CI cannot silently disable checking.
- `supabase db lint` requires a **local** database with `plpgsql_check`; it is not a disconnected static parser. Source: [Testing and linting](https://supabase.com/docs/guides/local-development/cli/testing-and-linting).

## Component inventory

| Component | Version / pin | Responsibility | Communicates with |
| --- | --- | --- | --- |
| Local harness | Python 3.9+, standard library | Fixture load, lexical retrieval plumbing, 48-cell schedule, mock/export/import, hashing, cost-field separation | Local files only |
| Synthetic fixtures | repository JSON | Memory facts/passages, questions, scoring anchors (separate files) | Harness |
| Supervised live client | Python, undeployed | Builds the allowed JSON body; attaches a 384-d unit embedding only for S1/L1 | Intended: Supabase Auth + Edge Function |
| Supabase Auth | existing free-tier project (not modified here) | Issues application-user JWTs | Browser/laptop, Edge Function |
| Edge Function `text-baseline-pilot` | Deno; prepared, not deployed | Allowlist, payload allow-list, snapshot ownership, retrieval, one model HTTP call | Database RPCs, model server |
| Pilot snapshot tables | SQL migration, not applied remotely | Immutable owner-scoped facts/passages + 384-d embeddings | RLS, invoker RPCs |
| Model server | unselected self-hosted OpenAI-compatible HTTP API | One non-streaming generation | Edge Function only |
| CI | `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683` (v4.2.2), `actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97` (v7.0.0), `denoland/setup-deno@22d081ff2d3a40755e97629de92e3bcbfa7cf2ed` (v2.0.5) | Python tests, Deno tests with type checking, foundation gates | GitHub Actions |

## Research and measurement boundary

The harness studies **fixed** S0/S1/L0/L1 text answers. It does not choose among them. Lexical overlap retrieval in the local harness is **plumbing validation**, not the semantic retrieval system that later experiments will measure.

Three cost fields are stored separately and must never be copied into one another:

1. **Market-priced generation estimate** — computed only from *measured* input/output tokens and *documented* per-million-token rates. Missing tokens or rates → `null`.
2. **Processing cost allocated to each answer** — filled only when an operator supplies a processing-cost total (or an explicit per-answer value) for that run. Missing → `null`.
3. **Actual rental and service spending** — session-level actuals for setup, idle time, memory preparation, storage, and later speech processing. Missing → `null`. Never derived from (1) or (2).

Mock mode leaves latency, token usage, quality, and all three cost fields `null`. Failed and missing responses are stored explicitly. No field is invented.

## Local harness behavior

- Twelve synthetic questions: four memory-answerable, four general-knowledge, four where memory and general knowledge may both contribute.
- Memory fixtures, questions, and scoring anchors live in separate files. Prompt construction may read questions and memory fixtures only.
- One repeat yields all 48 question-condition pairs. Repeats are bounded (`1..5`). A seed shuffles the schedule reproducibly.
- S0 and L0 never call retrieval. S1 and L1 receive identical retrieved evidence for the same question, repeat index, and fixture hash.
- Facts and source passages are both memory items.
- Modes: `mock`, `export-requests`, `import-responses`. Output paths that already exist are refused.
- Manifests, requests, fixtures, and evidence are SHA-256 hashed over canonical JSON.

## Supervised one-request live path (prepared only)

```text
Laptop --JWT + allow-listed JSON--> Edge Function
  S0/L0: verify snapshot ownership; do not read memory content
  S1/L1: lexical + 384-d vector ranking over the caller's snapshot
Edge Function --one HTTP request, redirect=error--> model server
Edge Function --pending then success|sanitized failure--> durable result row
```

The Edge Function accepts **only**: `request_id` (UUID), `snapshot_id` (UUID), `question` (string), `condition` (`S0`|`S1`|`L0`|`L1`), and a normalized 384-d embedding **when the condition uses memory**. It rejects client-provided model URLs, model settings, prompts, owner IDs, and reference answers.

Server-side configuration holds model endpoints, bearer token, model IDs, revisions, and quantization. Small and large are **aliases** (`small`, `large`); concrete Qwen IDs are not claimed as live-verified.

No-memory conditions must still prove the caller owns the snapshot, then skip retrieval. Memory conditions combine lexical rank with cosine similarity inside a `SECURITY INVOKER` function with `set search_path = ''`.

Safety controls: supervised-pilot allowlist and deadline; missing/expired session configuration rejected; duplicate `request_id` rejected; conservative call-rate window; request and response size caps; redirects rejected; one model attempt and no automatic retry; first-token latency stays `null` for non-streaming calls; token usage recorded only when the model server supplies it; raw upstream error bodies are not stored.

Fixed generation body (non-streaming):

```json
{
  "stream": false,
  "max_tokens": 256,
  "temperature": 0.7,
  "top_p": 0.8,
  "top_k": 20,
  "seed": 42,
  "chat_template_kwargs": { "enable_thinking": false }
}
```

## Trust boundaries

See [the harness diagram](../design/diagrams/2026-09-11-text-baseline-harness.svg).

- **Laptop / local workspace:** fixtures, embeddings (later), JWT in memory. Not a durable research store.
- **Supabase:** durable owner-scoped snapshot, allowlist, pending/final result rows. RLS is the authorization boundary.
- **Model server:** transient prompt and generation. No Supabase credential or user JWT is sent there.
- **GitHub:** code, synthetic fixtures, aggregate non-sensitive exports. No secrets, no live answers claimed as results.

## Unverified assumptions

- Exact small and large open-weight artifacts, revisions, and quantization on the future RunPod server are unselected. Settle by recording the served `/v1/models` (or equivalent) output in a dated operations note after a **planned** GPU session.
- Official `withSupabase({ auth: 'user' })` packaging against this project's Edge runtime is unverified. Settle by wrapping `handlePilotRequest` with the pinned `@supabase/server` package during the first supervised deploy rehearsal.
- Whether the self-hosted server accepts `chat_template_kwargs.enable_thinking`, `top_k`, and `seed` is unverified. Settle with one supervised non-billing probe that inspects the request echo or server docs for the chosen image — without treating the probe as an experimental result.
- This project's JWT algorithm (legacy HMAC secret versus JWKS) is unverified against the live Supabase project. The prepared function relies on platform `verify_jwt` plus application-level claims checks. Settle by inspecting the project's Auth JWT settings before first live call.
- `plpgsql_check` / `supabase db lint` against a local Postgres with `pgvector` is not available in every environment. Settle by running `supabase db lint` after `supabase db start` on a machine with the CLI and Docker.
- all-MiniLM-L6-v2 encoding quality on the twelve synthetic questions is unverified. Settle when the laptop embedding step is actually run.
- Market token prices for the eventual served models are not recorded here. Settle from a dated primary provider page when an estimate is needed.
- Edge Function wall-clock budget versus RunPod's 100-second proxy cap for this one-request path is unverified. The existing deployment spec's 75-second application budget remains the planning ceiling ([port exposure](https://docs.runpod.io/pods/configuration/expose-ports), recorded 2026-09-09).
