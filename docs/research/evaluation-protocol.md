# Initial evaluation protocol

Status: planning artifact; no results are reported here.

## Question

Does a joint controller for memory retrieval and small-versus-large model selection maintain answer quality while reducing end-to-end latency and overall cost relative to fixed baselines?

## Text-first milestones

1. Build a deterministic local test harness with synthetic fixtures and known expected controller decisions.
2. Establish no-memory/always-small and no-memory/always-large baselines.
3. Add retrieve-then-small and retrieve-then-large conditions.
4. Evaluate a joint adaptive controller only after its individual signals are logged and inspectable.
5. Add controlled speech recognition and voice-pipeline measurements later, reporting their latency separately.

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
