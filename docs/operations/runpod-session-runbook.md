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

Use image `vllm/vllm-openai:v0.29.0`. Small model `Qwen/Qwen3-4B-AWQ` at revision `74d4bd2bd4bff9cafc9345221320bffb08b406a3`. Large model `Qwen/Qwen3-14B-AWQ` at revision `31c69efc29464b6bb0aee1398b5a7b50a99340c3`. The start command must include `--generation-config vllm`. Clients must send the fixed generation body (`stream false`, `max_tokens 256`, `temperature 0.7`, `top_p 0.8`, `top_k 20`, `min_p 0`, `seed 42`, thinking disabled).

## During the session

1. Use a self-hosted model server and record the exact image, model revision, quantization, configuration, and start/end time needed to reproduce the run.
2. Export requests, then run the live harness (Codex/user operate the pod; Cursor does not):

```sh
PYTHONPATH=. python3 -m experiments.text_baseline export-requests --output /tmp/text-baseline-export --seed 0 --repeats 1

export TEXT_BASELINE_MODEL_BASE_URL='https://<pod-proxy-host>'
export TEXT_BASELINE_MODEL_BEARER='<inference-bearer>'
export TEXT_BASELINE_SMALL_MODEL_ID='Qwen/Qwen3-4B-AWQ'
export TEXT_BASELINE_LARGE_MODEL_ID='Qwen/Qwen3-14B-AWQ'

PYTHONPATH=. python3 -m experiments.text_baseline run-live \
  --requests /tmp/text-baseline-export/requests.json \
  --output /tmp/text-baseline-live \
  --transport direct \
  --hourly-rate <console-usd-per-hour> \
  --gpu-type '<gpu name>' \
  --session-id <session-id> \
  --pod-id <pod-id> \
  --model-revision <pinned-revision> \
  --quantization awq \
  --server-version vllm-0.29.0

PYTHONPATH=. python3 -m experiments.text_baseline import-responses \
  --requests /tmp/text-baseline-export/requests.json \
  --responses /tmp/text-baseline-live/responses.json \
  --output /tmp/text-baseline-import
```

3. Optional Edge Function path after Supabase deploy (user JWT only; no service-role or admin actions from this CLI):

```sh
export TEXT_BASELINE_EDGE_FUNCTION_URL='https://<project>.functions.supabase.co/text-baseline-pilot'
export TEXT_BASELINE_USER_JWT='<user-jwt>'
PYTHONPATH=. python3 -m experiments.text_baseline run-live \
  --requests /tmp/text-baseline-export/requests.json \
  --output /tmp/text-baseline-edge \
  --transport edge \
  --snapshot-id <snapshot-uuid> \
  --embeddings /tmp/embeddings-bundle.json \
  --hourly-rate <console-usd-per-hour>
```

4. Prepare snapshot embeddings offline before Codex loads them into Supabase:

```sh
PYTHONPATH=. python3 -m experiments.text_baseline prepare-embeddings --output /tmp/embeddings-bundle.json
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
