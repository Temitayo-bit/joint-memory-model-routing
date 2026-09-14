# Documentation

Keep documentation connected to actual decisions and evidence. Do not write speculative implementation notes as if they were established system behavior.

- `specs/` contains dated architecture or implementation specifications, including verified claims and unverified assumptions. The text-baseline harness decision is [2026-09-11-text-baseline-harness-design.md](specs/2026-09-11-text-baseline-harness-design.md). Retrieval v2 (pilot_hybrid_v2 IDF lexical correction) is [2026-09-12-retrieval-v2-idf-lexical-design.md](specs/2026-09-12-retrieval-v2-idf-lexical-design.md). Retrieval v2.1 (stopword-filtered IDF) is [2026-09-12-retrieval-v2-1-stopwords-design.md](specs/2026-09-12-retrieval-v2-1-stopwords-design.md). Text benchmark v2, which separates development from held-out model-routing evaluation, is [2026-09-13-text-benchmark-v2-design.md](specs/2026-09-13-text-benchmark-v2-design.md).
- `plans/` contains executable one-time plans. Completed plans remain historical records.
- `research/` contains evaluation protocols, benchmark notes, and interpretation grounded in saved evidence. The live S1/L1 retrieval v2.1 result is [2026-09-13-retrieval-v2-1-live-findings.md](research/2026-09-13-retrieval-v2-1-live-findings.md).
- `operations/` contains RunPod session, shutdown, and cost records.
- `adr/` contains concise decisions that supersede a prior choice.
