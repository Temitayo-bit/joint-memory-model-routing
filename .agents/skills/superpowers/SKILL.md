---
name: superpowers
description: Project-local execution discipline for planning, focused implementation, review, verification, and pull-request delivery. It captures the workflow desired for this repository without claiming to be an external Superpowers package.
---

# Project execution discipline

## Before changing code or infrastructure

Read `AGENTS.md` and `architecture.md`. For any change affecting two or more systems, an external provider, data durability, or cost, use `design-research` first and write a dated spec and plan.

## Focused implementation

Work on one planned task at a time. Prefer small, independently testable modules. Preserve a clear boundary between local development, durable Supabase state, and disposable GPU compute. Do not silently broaden the research question or add components whose role cannot be measured.

## Verification and review

Run the project’s real test and build commands. For code changes, use `subtask-review` before reporting the task complete. Treat a failing or absent check as incomplete, not as a detail to explain away.

## Pull-request delivery

Every change goes through a feature branch and pull request. The PR description states the change, verification, data/privacy implications, and GPU termination status when relevant. Merge only after required CI checks pass. Never force-push or bypass protections to make a check disappear.

## GPU session completion

When a RunPod session is involved, persist the needed approved outputs, verify them, terminate the pod, and record confirmation in `docs/operations/gpu-session-log.md`. A disconnected server is not a terminated server.
