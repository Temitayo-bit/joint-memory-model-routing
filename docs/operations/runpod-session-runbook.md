# RunPod session runbook

## Before starting a pod

1. Confirm the session has a defined purpose: integration test, planned evaluation condition, rehearsal, or demo.
2. Record the planned GPU, hourly rate shown by RunPod, expected duration, and budget remaining in `gpu-session-log.md`.
3. Confirm the repository is pushed and that required durable memory is in Supabase or another approved store.
4. Do not place secrets in commits, logs, screenshots, or shared experiment artifacts.
5. If using a Network Volume, create or attach it in the same RunPod region as the Pod. It may contain only non-sensitive model weights, container caches, and setup material. Recheck its displayed monthly price before creating it.
6. Print the pinned launch command locally (do not execute this generator against RunPod):

```sh
PYTHONPATH=. python3 -m experiments.text_baseline print-runpod-launch --model small
PYTHONPATH=. python3 -m experiments.text_baseline print-runpod-launch --model large
```

Use the digest-pinned image from the printed JSON (`vllm/vllm-openai@sha256:c2914767605584b6d8f45686b82de173ecc99e781897aa3d0a66dacd72c51ae1`, tag alias `v0.29.0`). Small model `Qwen/Qwen3-4B-AWQ` at revision `74d4bd2bd4bff9cafc9345221320bffb08b406a3`. Large model `Qwen/Qwen3-14B-AWQ` at revision `31c69efc29464b6bb0aee1398b5a7b50a99340c3`. The start command must include `--generation-config vllm`. Clients must send the fixed generation body (`stream false`, `max_tokens 256`, `temperature 0.7`, `top_p 0.8`, `top_k 20`, `min_p 0`, thinking disabled). For the legacy pilot the generation seed remains `42`. For benchmark v2, each request carries an allow-listed `generation_seed` of `42`, `43`, or `44`; that value is distinct from the schedule shuffle `--seed`.

## Retrieval condition (pilot_hybrid_v2_1)

Memory-enabled live runs (S1/L1 via Edge + `retrieve_pilot_memory`) use **pilot_hybrid_v2_1**: snapshot-local IDF token overlap with the fixed PostgreSQL 17 English Snowball stopword list (`postgresql_17_english_snowball`, 127 words) plus cosine similarity, default limit 4 (cap 8). This is a **new retrieval condition** relative to v1 and to deployed v2. After applying `20260912210000_retrieve_pilot_memory_v2_1.sql` and redeploying `text-baseline-pilot`, produce **fresh S1 and L1 text exports/runs** and record the v2.1 retriever config before collecting voice baselines under the same memory path. Do not alter or delete recorded v1 results. Preserve the existing v2 preflight export. S0/L0 need not be re-collected solely for this retrieval change.

## Dataset selection (legacy vs benchmark v2)

- **Legacy pilot** (`data/`): twelve-question setup/debugging reproduction. Default export path below.
- **Development-only** (`--dataset benchmark-v2-dev`): sixteen questions for harness checks; do not report as held-out findings.
- **Held-out evaluation** (`--dataset benchmark-v2-eval`): forty-eight questions and three generation seeds → 576 cells. Use separate snapshot/request/artifact paths; never reuse legacy request IDs, manifests, or score files.

Retriever remains `pilot_hybrid_v2_1`. Do not design or evaluate a controller until fixed text and voice baselines exist.

## During the session

1. Use a self-hosted model server and record the exact image digest, model revision, quantization, configuration, and start/end time needed to reproduce the run.
2. Export requests, then run small and large conditions in separate live sessions so each session records one pinned revision:

```sh
# Legacy pilot reproduction
PYTHONPATH=. python3 -m experiments.text_baseline export-requests --output /tmp/text-baseline-export --seed 0 --repeats 1

# Held-out benchmark v2 (after fixtures are frozen; do not run from an implementation-only PR)
PYTHONPATH=. python3 -m experiments.text_baseline export-requests --dataset benchmark-v2-eval --output /tmp/benchmark-v2-eval-export --seed 0 --repeats 1

# Direct-run secret exception: TEXT_BASELINE_MODEL_BASE_URL and TEXT_BASELINE_MODEL_BEARER
# may exist only as ephemeral local operator environment variables for --transport direct.
# They must never be committed, logged, screenshotted, or written into artifacts.
# Production Edge Function secrets remain the durable home for the proxy URL and bearer.
export TEXT_BASELINE_MODEL_BASE_URL='https://<pod-proxy-host>'
export TEXT_BASELINE_MODEL_BEARER='<inference-bearer>'
export TEXT_BASELINE_SMALL_MODEL_ID='Qwen/Qwen3-4B-AWQ'
export TEXT_BASELINE_LARGE_MODEL_ID='Qwen/Qwen3-14B-AWQ'

# Small conditions only
PYTHONPATH=. python3 -m experiments.text_baseline run-live \
  --requests /tmp/text-baseline-export/requests.json \
  --output /tmp/text-baseline-live-small \
  --transport direct \
  --condition S0 --condition S1 \
  --hourly-rate <console-usd-per-hour> \
  --gpu-type '<gpu name>' \
  --session-id <session-id-small> \
  --pod-id <pod-id> \
  --small-model-revision 74d4bd2bd4bff9cafc9345221320bffb08b406a3 \
  --quantization awq \
  --server-version vllm-0.29.0

# Large conditions only (separate pod/session recommended)
PYTHONPATH=. python3 -m experiments.text_baseline run-live \
  --requests /tmp/text-baseline-export/requests.json \
  --output /tmp/text-baseline-live-large \
  --transport direct \
  --condition L0 --condition L1 \
  --hourly-rate <console-usd-per-hour> \
  --gpu-type '<gpu name>' \
  --session-id <session-id-large> \
  --pod-id <pod-id> \
  --large-model-revision 31c69efc29464b6bb0aee1398b5a7b50a99340c3 \
  --quantization awq \
  --server-version vllm-0.29.0

PYTHONPATH=. python3 -m experiments.text_baseline import-responses \
  --requests /tmp/text-baseline-export/requests.json \
  --responses /tmp/text-baseline-live-small/responses.json \
  --output /tmp/text-baseline-import-small
```

3. Prepare snapshot embeddings offline before any Edge Function memory run and before Codex loads them into Supabase:

```sh
PYTHONPATH=. python3 -m experiments.text_baseline prepare-embeddings \
  --output /tmp/embeddings-bundle.json \
  --model-revision 1110a243fdf4706b3f48f1d95db1a4f5529b4d41
```

4. Optional Edge Function path after Supabase deploy (user JWT in `Authorization`, publishable key in `apikey`; no service-role or admin actions from this CLI). Treat both as ephemeral operator secrets: never commit, log, screenshot, or write them into artifacts.

```sh
export TEXT_BASELINE_EDGE_FUNCTION_URL='https://<project>.functions.supabase.co/text-baseline-pilot'
export TEXT_BASELINE_USER_JWT='<user-jwt>'
export TEXT_BASELINE_SUPABASE_PUBLISHABLE_KEY='<supabase-publishable-key>'
PYTHONPATH=. python3 -m experiments.text_baseline run-live \
  --requests /tmp/text-baseline-export/requests.json \
  --output /tmp/text-baseline-edge \
  --transport edge \
  --snapshot-id <snapshot-uuid> \
  --embeddings /tmp/embeddings-bundle.json \
  --hourly-rate <console-usd-per-hour>
```

5. Save aggregate, non-sensitive outputs and configuration to the repository or approved durable storage.
6. Keep the pod private; do not expose an unauthenticated model endpoint to the public internet.
7. Record actual rental/service spending in `session.json` → `session_actuals` and in `gpu-session-log.md`. Do not copy that total into per-answer `allocated_processing_cost` or token-price fields.

## Required shutdown

At the end of active work, rehearsal, or demo:

1. Push code and save approved experiment artifacts.
2. Verify that nothing required remains only on the pod volume.
3. Terminate the pod. Do not merely disconnect from it or leave it stopped with retained storage by default.
4. Delete attached pod storage. A Network Volume may stay only for a documented short-term setup/model-cache reason; it is billed independently after the Pod ends, so record its monthly rate and planned deletion date.
5. Complete the actual cost, retained-volume decision, and termination confirmation in `gpu-session-log.md`.

If termination cannot be verified, report that immediately; do not claim the session is shut down.
