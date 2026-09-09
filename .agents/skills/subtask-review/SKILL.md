---
name: subtask-review
description: Use when a coding subtask is finished and about to be reported done, committed, or handed back to the operator — before merging or claiming completion on any change that touched code, especially anything touching credentials, memory data, external database access, or GPU billing.
---

# Subtask Review

## Overview

A finished subtask gets reviewed from several independent angles before it's considered done, by separate sub-agents that don't see each other's findings. One agent trying to cover every angle in a single pass reliably misses the angle it wasn't focused on — this catches that. Treat this as mandatory rather than optional for anything touching credentials, durable memory, external storage, authentication, or GPU billing.

## When to use

- Any subtask that edited code, before reporting it complete or committing.
- Not needed for pure research/read-only work, or a change the operator explicitly said to skip review on.

## The angles

Each sub-agent reviews the SAME diff, blind to the other angles' findings:

1. **Correctness** — business logic correctness first (does the code do what the business rule says, not just run without erroring), logic bugs, unhandled edge cases, does it actually satisfy the subtask as scoped
2. **Architecture fit** — matches existing module boundaries and any relevant `docs/<layer>.md`, no new pattern duplicating one that already exists, no god files (a file/function doing more than one job)
3. **Security** — RLS/permission enforcement, no client-trusted authority flags, input validation, SQL injection vectors (parameterized queries only, no string-built SQL, including inside RPCs), secrets handling, and private endpoint exposure. Any use of an unnecessarily privileged Supabase key is an automatic blocker. Default posture: assume the change is a security risk until reasoned otherwise.
4. **Efficiency / cost** — redundant model or voice calls, N+1 queries, illogical or redundant DB writes, bloated JSON payloads, dependency bottlenecks on hot paths, unexpected GPU uptime, and any cost not recorded in the GPU session log.
5. **Alternative approach** — is there a simpler or more idiomatic way to do this; flag both over-engineering and under-engineering

**Standing focuses (every review stresses these four regardless of which angles run):** business logic correctness, SQL injection vectors, unhandled edge cases, and N+1 query patterns. Each belongs to its angle above, but no review passes without all four having been looked at.

## How to run it

1. Get the diff for the subtask (`git diff` against the base branch, or just the touched files).
2. Dispatch one sub-agent per angle, all in parallel — one message, multiple sub-agent calls. Give each the diff, the original subtask description, and only its own angle's focus above. Don't let one agent's findings leak into another's prompt; the independence is the point.
3. Each sub-agent reports findings as: `file:line` — one-sentence problem — severity (`blocker` / `should-fix` / `nit`).
4. Collect all five reports, dedupe overlapping findings, and present blockers + should-fixes to the operator before proceeding. Nits are optional — note them, don't block on them.
5. If the subtask touched authentication, Supabase access, or a public endpoint, the security angle's sub-agent should explicitly check expected and absent-user access cases — not just generic security hygiene. If it touched RunPod operations, the efficiency/cost review must verify that the pod termination path is still present and testable.

## Common mistakes

- Running one agent through all five angles sequentially instead of five agents in parallel — this defeats the purpose; independence is what surfaces the angle-specific blind spot a combined pass would rationalize away.
- Skipping review on "small" changes — small changes are exactly where nobody was specifically looking for the angle that had the problem, and in this repo a "small" permissions change is where privacy bugs hide.
- Treating this as a substitute for tests — it catches a different class of problem (design and judgment issues, not behavioral regressions).
