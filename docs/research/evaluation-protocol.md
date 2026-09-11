# Initial evaluation protocol

Status: planning artifact; no results are reported here.

## Question

Does a joint controller for memory retrieval and small-versus-large model selection maintain answer quality while reducing end-to-end latency and overall cost relative to fixed baselines?

## Text-first milestones

1. Establish fixed text baselines S0, S1, L0, and L1 with a deterministic local harness (synthetic fixtures; scoring anchors never enter prompts).
2. Repeat those four conditions on a voice pipeline, reporting speech latency separately.
3. Design a joint controller only after the fixed baselines exist and routing signals are logged and inspectable.
4. Evaluate the controller on text, then on voice.

Do not treat local lexical fixture retrieval as the final semantic retrieval system. Do not report mock or fixture output as experimental results.

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
