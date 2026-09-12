# Local text-baseline harness

This package runs **fixed** conditions S0, S1, L0, and L1 on twelve synthetic questions. It does not implement a controller and does not claim experimental results.

Local retrieval uses **pilot_hybrid_v2** snapshot-local IDF token overlap for plumbing validation. It is not the measured semantic retrieval system. The live Supabase path uses the same lexical rule plus cosine similarity inside `retrieve_pilot_memory`.

## Retrieval versioning

- **v1** (`plainto_tsquery` AND lexical ranks): historical condition. Keep recorded v1 artifacts; do not alter or delete them.
- **v2** (`pilot_hybrid_v2`): current retrieval condition. After the v2 SQL migration is applied and the Edge Function is redeployed, **re-run memory-enabled text baselines (S1 and L1) before any voice baselines** that claim the same retrieval setup. S0/L0 need not be re-collected solely for this retrieval change.
- Manifests and evidence hashes record `retriever`, `limit` (4), `limit_cap` (8), and the IDF formula so runs are reproducible.

## Modes

```sh
PYTHONPATH=. python3 -m experiments.text_baseline mock --output /tmp/text-baseline-mock --seed 0 --repeats 1
PYTHONPATH=. python3 -m experiments.text_baseline export-requests --output /tmp/text-baseline-export --seed 0 --repeats 1
PYTHONPATH=. python3 -m experiments.text_baseline import-responses --requests /tmp/text-baseline-export/requests.json --responses /path/to/measured.json --output /tmp/text-baseline-import
```

### Live runner (operator / Codex)

Reads exported requests and calls an OpenAI-compatible endpoint. Secrets come only from environment variables and are never printed or written into artifacts.

```sh
export TEXT_BASELINE_MODEL_BASE_URL='https://<pod-proxy-host>'
export TEXT_BASELINE_MODEL_BEARER='<inference-bearer>'
export TEXT_BASELINE_SMALL_MODEL_ID='Qwen/Qwen3-4B-AWQ'
export TEXT_BASELINE_LARGE_MODEL_ID='Qwen/Qwen3-14B-AWQ'

PYTHONPATH=. python3 -m experiments.text_baseline run-live \
  --requests /tmp/text-baseline-export/requests.json \
  --output /tmp/text-baseline-live \
  --transport direct \
  --condition S0 --condition S1 \
  --question-id Q10 \
  --repeat 0 \
  --max-requests 2 \
  --hourly-rate 0.50 \
  --gpu-type 'NVIDIA GeForce RTX 3090' \
  --session-id sess-2026-09-11 \
  --pod-id <pod-id> \
  --model-revision 74d4bd2bd4bff9cafc9345221320bffb08b406a3 \
  --quantization awq \
  --server-version vllm-0.29.0
```

Optional Edge Function transport (allow-listed body only; no admin Supabase actions).
Send the user JWT only in `Authorization` and the publishable key in `apikey`. Never put the JWT in `apikey`.

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
  --hourly-rate 0.50
```

`TEXT_BASELINE_USER_JWT` and `TEXT_BASELINE_SUPABASE_PUBLISHABLE_KEY` are ephemeral operator secrets for Edge transport. They must never be committed, logged, screenshotted, or written into response/session artifacts.
`responses.json` is checkpointed after each request and is accepted by `import-responses`. Re-running the same `--output` resumes and skips completed digests.

### Embedding bundle (offline; no Supabase writes)

```sh
# Requires local: pip install sentence-transformers
PYTHONPATH=. python3 -m experiments.text_baseline prepare-embeddings \
  --output /tmp/embeddings-bundle.json
```

### RunPod launch command generator (does not execute)

```sh
PYTHONPATH=. python3 -m experiments.text_baseline print-runpod-launch --model both
```

Pins:

- Small: `Qwen/Qwen3-4B-AWQ` revision `74d4bd2bd4bff9cafc9345221320bffb08b406a3`
- Large: `Qwen/Qwen3-14B-AWQ` revision `31c69efc29464b6bb0aee1398b5a7b50a99340c3`
- Image: `vllm/vllm-openai@sha256:c2914767605584b6d8f45686b82de173ecc99e781897aa3d0a66dacd72c51ae1`
- Includes `--generation-config vllm` and the fixed generation settings in the printed JSON
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2` revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`

Mock mode writes placeholder answers and leaves latency, tokens, quality, and all three cost fields null. Existing output directories for mock/export/import are refused.

Scoring anchors in `data/scoring_anchors.json` are not loaded when prompts are built.

Active-inference processing cost per answer is `(model_http_ms / 3_600_000) * hourly_rate`. Session rental/service spending stays in `session.session_actuals` only and is never copied into per-answer cost fields. First-token latency stays null for non-streaming requests.
