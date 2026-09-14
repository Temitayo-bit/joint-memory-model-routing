# Initial evaluation protocol

Status: planning artifact; no results are reported here.

## Question

Does a joint controller for memory retrieval and small-versus-large model selection maintain answer quality while reducing end-to-end latency and overall cost relative to fixed baselines?

## Text-first milestones

1. Establish fixed text baselines S0, S1, L0, and L1 with a deterministic local harness (synthetic fixtures; scoring anchors never enter prompts).
2. Keep the recorded twelve-question `synthetic-northriver-pilot-v1` run as a setup/debugging pilot only.
3. Use `benchmark-v2-dev` (16 questions) only for harness checks and later controller-threshold design; never report it as the held-out result.
4. Report fixed baselines and later controller comparisons on held-out `benchmark-v2-eval` (48 questions × 4 conditions × generation seeds 42/43/44 = 576 cells) after fixtures are frozen.
5. Repeat those four conditions on a voice pipeline, reporting speech latency separately, while preserving the same held-out split discipline.
6. Design a joint controller only after the fixed baselines exist and routing signals are logged and inspectable.
7. Evaluate the controller on text, then on voice.

Do not treat local fixture retrieval as the final semantic retrieval system. Do not report mock or fixture output as experimental results. When the live hybrid retriever version changes (for example v1 `plainto_tsquery`, v2 `pilot_hybrid_v2`, or v2.1 `pilot_hybrid_v2_1`), treat memory-enabled runs as a new retrieval condition: keep prior artifacts, record the new configuration, and re-run S1/L1 text before voice baselines that depend on that memory path. Benchmark v2 keeps `pilot_hybrid_v2_1` unchanged.

## Required recording per run

- benchmark name, version/subset, and data handling note;
- small and large model revisions and quantization;
- routing/retrieval configuration and random seed;
- model-generation, retrieval, and end-to-end latency;
- quality scoring method and result;
- input/output token or GPU-time cost estimate;
- hardware and server configuration;
- known limitations, including external Supabase round-trip variability when used.

## Guardrails

Start with a limited comparison matrix. Do not expand to an exhaustive factorial experiment unless the evidence justifies the added cost and time. Separate observed results from hypotheses and treat an oracle as an analysis ceiling, not a deployable baseline.
