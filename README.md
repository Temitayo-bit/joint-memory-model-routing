# Joint Memory and Model Routing for Latency-Constrained Voice Agents

CSCI 499 Senior Research project repository.

This project investigates a controller that jointly decides when to retrieve long-term memory and when to route a request to a small or larger self-hosted language model. The goal is to maintain answer quality while managing latency and cost in a voice-agent pipeline.

## Current status

Repository foundation only. The initial implementation is deliberately text-first and local-first. No experimental result should be inferred from this repository until an experiment protocol and saved result are added.

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
