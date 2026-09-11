# Joint Memory and Model Routing

Read `architecture.md` before changing the system. It is the living source of truth for the research scope, system boundaries, cost controls, and durable-data rules.

## Project purpose

This CSCI 499 Senior Research repository supports **Joint Memory and Model Routing for Latency-Constrained Voice Agents**. The contribution is the controller that jointly decides whether to retrieve long-term memory and whether to use a small or larger language model. A polished voice interface is supporting infrastructure, not the research claim.

Establish the four fixed model/memory baselines in text and then voice before designing the controller. Evaluate the controller in both modalities afterward.

## Core rules

- This is a **public** research repository. Treat every committed file, pull-request diff, issue, GitHub Actions log, and release artifact as publicly visible.
- Never invent experimental results, costs, latency measurements, benchmark outcomes, citations, or advisor feedback.
- Preserve reproducibility: version datasets, record configuration and random seeds, and save non-sensitive experiment summaries outside temporary GPUs.
- Treat Supabase as the durable research-memory store. A RunPod pod and its local disk are disposable compute, never the sole location of required code, logs, results, or memory.
- Deploy the browser application on Vercel. Use Supabase Auth, RLS, and Edge Functions for authenticated memory access and the request controller; use RunPod only for the active self-hosted inference server. Vercel holds only public client configuration, never privileged Supabase or RunPod credentials. The RunPod proxy URL and inference credential belong only in Supabase Edge Function secrets.
- A RunPod **Network Volume** may be retained separately from a pod for non-sensitive model weights, container caches, and server setup. It is not the research memory store and is never the sole location for required code, logs, results, or data. The current storage decision and price note live in `architecture.md`; the operational checklist is `docs/operations/runpod-session-runbook.md`.
- Do not commit credentials, API keys, Supabase URLs with secrets, dataset access tokens, `.env` files, model weights, audio recordings, or personally identifiable conversations.
- Use synthetic or consented data only. Do not put real personal conversations in the research database or benchmark artifacts.

## CodeRabbit-informed quality and security rules

- A design spec is never exempt from fact-checking: follow `.agents/skills/design-research/` for every change under `docs/specs/`, including a documentation-only spec. The same applies to documentation that introduces or changes an external architecture, API, pricing, or security claim.
- Pin every third-party GitHub Action to a reviewed, full-length immutable commit SHA. Do not use mutable tags such as `@v4` in workflows.
- In this public repository, credential scanning must cover all tracked paths, including `docs/` and `.agents/`. A scanner must use quiet matching and must never print a possible secret or its matching line into CI logs. Exclude only a narrowly scoped, explicitly redacted example when necessary.
- A build/CI gate that claims to validate an architectural boundary must directly test the relevant contract (for example, controller, durable-memory, and transient-compute rules). A non-empty file check or unrelated phrase match is not sufficient.

## Mandatory GPU cost rule

**A RunPod server must be terminated when it is not actively being used.** Before ending any GPU session: save/push code, export required non-sensitive experiment outputs, verify durable data is in Supabase or another approved backup, then terminate the pod. Do not leave a pod running for convenience, background work, or an unspecified future session.

Delete attached pod storage at shutdown. A deliberately retained Network Volume is the narrow exception: it may remain while it avoids repeated model/setup downloads, but it still incurs storage charges after the GPU is terminated. Record why it is retained and delete it when that reason ends.

Use a 24 GB GPU for normal integration and evaluation work. Use 48 GB only for a planned larger-model condition. Keep a per-session cost record in `docs/operations/gpu-session-log.md` and stay within the user’s $75 semester cap.

## Planning and implementation workflow

Codex is the planning, coordination, experiment-operation, and infrastructure-operation agent working with the user. When repository implementation, debugging, test writing or fixing, code review, or local development setup is ready, Codex gives the user a complete, copy-ready prompt for the user-operated local Cursor agent with the local checkout path, working-tree state, constraints, test and review status, and prohibited external actions. The user opens that local checkout and sends the prompt to Cursor. Cursor does not run real experiments or operate remote infrastructure: the user and Codex together handle Supabase migrations and deployments, RunPod provisioning and shutdown, live requests, result capture, and cost verification. Codex does not launch Cursor, implement or review code in parallel, or substitute Codex subagents unless the user explicitly overrides this workflow.

Codex must warn the user when it estimates that the current conversation is near 80% of its available context window. Because the application does not expose an exact context percentage to the model, treat this as an early best-effort threshold. At that point, write a concise current-state handoff containing completed work, verified external state, active resources and costs, repository path and Git state, uncommitted files, decisions, blockers, and exact next actions. Then provide a copy-ready onboarding prompt for a fresh Codex task before continuing context-heavy work.

1. For a change involving external services, data flow, pricing, or architecture, use `.agents/skills/design-research/` before writing its spec. Verify time-sensitive claims from primary sources.
2. Write a dated spec in `docs/specs/`, then an executable one-time plan in `docs/plans/`.
3. Implement in a feature branch. Every change, including docs and configuration, is submitted as a pull request; never push directly to `main`.
4. Run `make test` and `make build`. GitHub Actions must pass before merge.
5. Review code changes with `.agents/skills/subtask-review/` before claiming them complete. Security, data durability, cost, correctness, and simpler alternatives must be considered.
6. CodeRabbit reviews every pull request. Address, explicitly dismiss with a reason, or defer each actionable CodeRabbit finding before merge; it supplements rather than replaces human review and passing CI.
7. Merge only after GitHub Actions and the required CodeRabbit review/check pass. Do not bypass required checks.

`docs/plans/` records historical intent. Do not re-run a finished plan without a new dated plan or amendment.

## Repository conventions

- `architecture.md`: current architectural decisions and research boundaries.
- `docs/specs/`: dated design decisions and verified assumptions.
- `docs/plans/`: one-time implementation plans.
- `docs/research/`: benchmark protocols, source notes, and experiment interpretation.
- `docs/operations/`: deployment and GPU shutdown/runbooks.
- `.agents/skills/`: project-local agent workflows. The available `superpowers` guide translates the desired planning/implementation/review discipline for this repository; it is not a copied external package.

## Public repository and CodeRabbit setup

- Create the GitHub repository as public under `Temitayo-bit`.
- Before the first substantive pull request, install the CodeRabbit GitHub App for **only this repository** and use its no-cost public/open-source tier. Do not enable paid or usage-based add-ons without the user's explicit approval.
- Require the CI `test` and `build` checks and the CodeRabbit review/check in the `main` branch rule. Require pull requests and do not allow direct pushes to `main`.
- Keep external-service credentials in local environment variables or the GitHub Actions secrets store. Public issue discussions and PRs must use redacted examples and synthetic data.

## Commands

- `make test` — validates the repository foundation and required research/operations documents.
- `make build` — runs the repository build gate; until application code is scaffolded, it validates the documented architecture and deployment contract, not unimplemented runtime behavior.

When application code is added, replace these foundation checks with its real lint, typecheck, unit-test, integration-test, and build commands while retaining the same CI job names.
