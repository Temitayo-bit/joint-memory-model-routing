# Joint Memory and Model Routing for Latency-Constrained Voice Agents

CSCI 499 Senior Research project repository.

This project investigates a controller that jointly decides when to retrieve long-term memory and when to route a request to a small or larger self-hosted language model. The goal is to maintain answer quality while managing latency and cost in a voice-agent pipeline.

## Current status

Text-baseline harness is in tree for fixed conditions S0, S1, L0, and L1. Mock and export modes are local-only. A supervised one-request live path is prepared in SQL and an Edge Function and is **not** deployed. No experimental result should be inferred from mock, fixture, or unmeasured output.

See [the text-baseline design](docs/specs/2026-09-11-text-baseline-harness-design.md) and [the harness README](experiments/text_baseline/README.md).

## Development and quality gates

```sh
make test
make build
```

Every change is made on a feature branch and merged through a pull request only after GitHub Actions passes. See [AGENTS.md](AGENTS.md) and [architecture.md](architecture.md).

## Compute policy

RunPod is temporary compute. Before ending a GPU session, preserve code and approved outputs elsewhere, then terminate the pod. Never leave a GPU running when it is not being actively used. See [the GPU runbook](docs/operations/runpod-session-runbook.md).

## Repository map

- `architecture.md` — current research and system boundaries
- `docs/specs/` — dated design specifications
- `docs/plans/` — one-time execution plans
- `docs/research/` — experimental protocol and source notes
- `docs/operations/` — deployment, cost, and shutdown records
