# Retrieval v2.1 live findings

Date: 2026-09-13

## Scope

This report covers the memory-enabled text conditions only:

- S1: Qwen3-4B-AWQ with retrieval v2.1
- L1: Qwen3-14B-AWQ with retrieval v2.1

Both runs used the frozen 12-question set, frozen memory snapshot `177daa79-1210-4019-8c46-3e419b7773a8`, unchanged MiniLM embeddings, fixed generation settings, and the deployed `pilot_hybrid_v2_1` retriever. Answers were checked after collection against the frozen scoring anchors. Earlier Edge setup failures are retained separately and were not scored as research results.

## Results

| Condition | v1 score | v2.1 score | Change | Median end-to-end | p95 end-to-end | Median retrieval | Tokens in / out |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| S1 | 11/12 | 12/12 | +1 | 2.73 s | 4.75 s | 125 ms | 2,194 / 800 |
| L1 | 11/12 | 12/12 | +1 | 1.99 s | 4.45 s | 96.5 ms | 2,194 / 502 |

Q09 was the prior miss. Under v2.1, both models correctly answered that the Northriver harness uses **Python** and that Python is typically **interpreted**. All other questions remained correct, so the Q09 improvement did not introduce a regression in this 12-question set.

## Cost observations

- S1 response-only compute allocation: approximately $0.0014. The full successful pod window was approximately $0.12 by elapsed-time estimate, including startup and idle time.
- L1 response-only compute allocation: approximately $0.0019. The dashboard balance moved by approximately $0.04 during the full L1 window, including startup and idle time.
- Provider line items were not available during the run, so dashboard balance movements remain operational observations rather than final billing allocations.

## Interpretation

The live evidence supports the narrow conclusion that retrieval v2.1 fixes the known Q09 retrieval failure for both the small and large memory-enabled conditions while preserving the other eleven answers. It does not yet establish generalization beyond the frozen 12-question pilot or quantify repeat-to-repeat variance.

## Durable evidence

- S1 responses: `artifacts/live/2026-09-13-text-small-edge-v2-1-combined/responses.json`
- S1 import: `artifacts/live/2026-09-13-text-small-edge-v2-1-import/`
- L1 responses: `artifacts/live/2026-09-13-text-large-edge-v2-1-final/responses.json`
- L1 import: `artifacts/live/2026-09-13-text-large-edge-v2-1-import/`
- Request export: `artifacts/preflight/2026-09-13-text-baseline-retrieval-v2-1-final-export/`

