# Text S0/S1 live smoke — 2026-09-11

## Status

This was a two-request deployment smoke test, not a completed baseline and not a research result. It verified that the exported harness prompts can run against a self-hosted small model and that measured responses pass the harness importer. The other 46 matrix cells remain explicitly missing.

## Runtime

- Provider: RunPod Pod `izkvn8qqesqdls`, terminated after the smoke test.
- GPU: NVIDIA GeForce RTX 3090, secure cloud, $0.50 per hour.
- Container: `vllm/vllm-openai:v0.29.0`.
- Container digest: `sha256:c2914767605584b6d8f45686b82de173ecc99e781897aa3d0a66dacd72c51ae1`.
- Server fingerprint: `vllm-0.29.0-78ac8650`.
- Model: `Qwen/Qwen3-4B-AWQ`.
- Model revision reported by vLLM: `main`; an immutable model revision was not pinned for this smoke test.
- Quantization reported by vLLM: `auto_awq`; checkpoint size 2.48 GiB.
- Maximum model length: 8192 tokens.
- Generation request: non-streaming, maximum 256 output tokens, temperature 0.7, top-p 0.8, top-k 20, min-p 0, seed 42, thinking disabled.

The RunPod HTTPS proxy was used with a temporary bearer token. No secret is stored in this repository or the saved artifacts.

## Paired result

Both requests used question Q10: “What semester GPU budget cap does Northriver record, and is that amount a hardware purchase or an operating budget?”

| Condition | Memory | Behavior | Model HTTP / end-to-end | Input tokens | Output tokens | Active-inference GPU cost |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| S0 | None | Correctly said the private amount could not be determined without memory evidence. | 1733.479 ms | 84 | 82 | $0.00024076097222222225 |
| S1 | Four lexically retrieved items | Returned the recorded $75 semester operating budget. | 1067.888 ms | 196 | 94 | $0.00014831777777777778 |

Active-inference GPU cost is measured model HTTP duration multiplied by the confirmed $0.50-per-hour rental rate. It excludes setup and idle time. It is kept separate from token-price estimates and from total session spending.

## Session cost

The account balance was $10.00 before provisioning and $9.8707596019 after both Pods were deleted and delayed charges had posted, for an observed all-in balance delta of **$0.1292403981**. This includes startup, image pull, model preparation, idle time, the two inference calls, temporary attached storage, and the earlier replaced 24 GB provisioning attempt to the extent RunPod billed them. RunPod's detailed billing endpoint had not populated line items when checked, so the balance delta is the current source for total actual spending.

Market-priced token cost remains null because this is a self-hosted open-weight model and no documented per-token market rate was selected. Quality scores remain null pending the scoring procedure.

## Limits

- S1 used the harness's local lexical retrieval plumbing. It did not test Supabase vector retrieval.
- The deployed Supabase Edge Function was not exercised in this smoke test.
- Non-streaming requests do not provide first-token latency.
- The warm S1 request followed the first request, so the lower S1 latency is not evidence that memory reduces latency.
- One question cannot support a quality, latency, or cost conclusion.
- The full baseline must pin an immutable model revision and automate all scheduled cells before data collection.

## Local evidence

Raw request, response, and importer output files are stored locally under `artifacts/smoke/2026-09-11-s0-s1/`. That directory is intentionally ignored by Git. The checked-in summary contains no credentials or private user data.
