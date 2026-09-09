# Joint Memory and Model Routing

Read `architecture.md` before changing the system. It is the living source of truth for the research scope, system boundaries, cost controls, and durable-data rules.

## Project purpose

This CSCI 499 Senior Research repository supports **Joint Memory and Model Routing for Latency-Constrained Voice Agents**. The contribution is the controller that jointly decides whether to retrieve long-term memory and whether to use a small or larger language model. A polished voice interface is supporting infrastructure, not the research claim.

Start with text-based, reproducible experiments. Add voice only after the controller and measurements are working.

## Core rules

- This is a **public** research repository. Treat every committed file, pull-request diff, issue, GitHub Actions log, and release artifact as publicly visible.
- Never invent experimental results, costs, latency measurements, benchmark outcomes, citations, or advisor feedback.
- Preserve reproducibility: version datasets, record configuration and random seeds, and save non-sensitive experiment summaries outside temporary GPUs.
- Treat Supabase as the durable memory store. A RunPod pod and its local disk are disposable compute, never the sole location of required code, logs, results, or memory.
- Do not commit credentials, API keys, Supabase URLs with secrets, dataset access tokens, `.env` files, model weights, audio recordings, or personally identifiable conversations.
- Use synthetic or consented data only. Do not put real personal conversations in the research database or benchmark artifacts.

## Mandatory GPU cost rule

**A RunPod server must be terminated when it is not actively being used.** Before ending any GPU session: save/push code, export required non-sensitive experiment outputs, verify durable data is in Supabase or another approved backup, then terminate the pod and delete attached pod storage when it is not intentionally being retained. Do not leave a pod running for convenience, background work, or an unspecified future session.

Use a 24 GB GPU for normal integration and evaluation work. Use 48 GB only for a planned larger-model condition. Keep a per-session cost record in `docs/operations/gpu-session-log.md` and stay within the user’s $75 semester cap.

## Planning and implementation workflow

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
- `make build` — runs the repository build gate; until application code is scaffolded, it validates the documented architecture and deployment boundaries.

When application code is added, replace these foundation checks with its real lint, typecheck, unit-test, integration-test, and build commands while retaining the same CI job names.
