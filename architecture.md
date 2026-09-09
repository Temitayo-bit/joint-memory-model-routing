# Architecture: Joint Memory and Model Routing

Last updated: 2026-09-09

## Research boundary

The system studies a controller for latency-constrained voice-agent requests. Given a completed request, the controller chooses among:

1. small model without long-term-memory retrieval;
2. retrieve relevant long-term memory, then use the small model; or
3. retrieve relevant long-term memory and use a larger model.

The primary evaluation is answer quality under latency and overall-cost constraints. The controller, its features, and its evaluation are the research artifact. Speech recognition and text-to-speech are held as bounded pipeline components rather than treated as the core contribution.

## Initial deployment boundary

```text
Browser/client --loads UI--> Vercel web app
Browser/client --JWT request--> Supabase Edge Function (controller) -> RunPod model server
Browser/client --sign-in--> Supabase Auth -> durable memory            transient compute
```

- **Local development:** controller, API, UI, tests, synthetic fixtures, and basic integration testing. No rented GPU is needed.
- **Vercel:** hosts the public Next.js web application and its preview deployments from GitHub pull requests. Production deploys from `main`; it holds no durable memory or privileged Supabase/RunPod credentials.
- **Supabase free tier:** Supabase Auth, durable structured memory and vectors, and the authenticated Edge Function that retrieves memory, makes the routing decision, and calls the active RunPod server. User requests carry a JWT; all memory reads/writes must remain RLS-scoped. The external database/function round trip is a deployment limitation to measure and report separately from model inference.
- **RunPod:** temporary, self-configured GPU compute for real model inference, planned experiments, rehearsals, and demos. A pod is terminated after active use. Its local disk is not durable storage.
- **RunPod Network Volume:** optional retained storage, created in the same region as the Pod, for non-sensitive model weights, container caches, and repeatable server setup. On 2026-09-09, the RunPod console showed **$0.07 per GB/month** (10 GB = **$0.70/month**). It survives Pod termination and continues to be billed, so it is deleted when no longer useful. Recheck the console price and region availability before creating one. It does not replace Supabase for durable research memory or GitHub/approved storage for required artifacts.
- **GitHub:** source code, non-sensitive experiment configurations, aggregate results, documentation, and CI evidence.

The free Supabase project can be paused after inactivity. The Vercel UI must handle this state without retry loops or data loss, show a clear service-unavailable message, and require the project owner to resume the project before a demo.

The full, source-checked deployment decision is in [the Vercel–Supabase–RunPod design](docs/specs/2026-09-09-vercel-supabase-runpod-deployment-design.md). The diagram there identifies payloads, trust boundaries, and retained data.

## Deliberate non-goals for the first milestone

- an always-on public GPU or anonymous public model endpoint;
- autonomous background GPU operation;
- storing real personal conversations;
- exhaustive combinations of every retrieval, routing, voice, and memory-writing variant;
- treating vendor API results as a substitute for self-hosted-server measurements.

## Evaluation baseline

The initial comparison should include no-memory and always-small/always-large baselines before joint adaptation. Candidate later conditions include fixed-threshold routing, no-memory-signal routing, joint adaptive routing, and an oracle analysis. Record quality, retrieval relevance, end-to-end latency, model-generation latency, retrieval latency, escalation rate, and cost.

## Open decisions

- Exact small and large open-weight models and quantization formats.
- Supabase `pgvector` schema, retrieval configuration, and RLS policy design.
- Benchmark subset and scoring method.
- Authenticated/private demo boundary and consent process for any live voice testing.

Each decision must be fact-checked and recorded in a dated specification before implementation.
