---
name: design-research
description: Use before writing any design spec in docs/specs/ — fact-check the proposed architecture against primary sources, inventory the real components, discuss the system to agreement, then (for anything spanning two or more systems) draw it, show it inline, and save it. Runs before the spec is written, not after.
---

# Design Research

## Overview

Two failure modes this exists to stop.

The first: a spec that reads as authoritative but rests on facts nobody checked — a version that shipped differently, an API that changed signature, a price lifted from an undated blog post, a rate limit half-remembered. Everything downstream inherits the error, and by the time it surfaces it's in code.

The second: an architecture nobody can actually see. A system with four moving parts, described only in prose, is a system whose gaps stay invisible until implementation hits them.

So: verify first, agree in words, then draw. In that order — the order is the point.

## When to use

Before writing any `docs/specs/<date>-<slug>-design.md`.

- **Fact-check and component inventory: always.** Every spec, no exceptions. Small tickets make factual claims too.
- **Diagram: when the change spans two or more systems, or introduces a new boundary** — a new service, vendor, data flow, or external dependency. Decide this *after* Step 3, not from the opening description; tickets routinely turn out to have more moving parts than they looked like.
- **Skip entirely** only for documentation and configuration changes that do not create or modify a design spec and do not introduce or change external architecture, API, pricing, or security claims. A design spec is never exempt from this workflow.

## Step 1 — Fact-check

The operator's description of the system is the input. Pull every load-bearing claim out of it: versions, APIs and their signatures, platform behavior, rate limits, quotas, pricing, compatibility, security model.

Dispatch parallel research sub-agents, one per claim cluster — vendor/API surface, versions and compatibility, cost and limits, security and platform behavior. Each returns, per claim:

```text
claim  →  confirmed | corrected | unverifiable  →  source URL  →  date checked
```

Three rules, in priority order:

1. **Official docs and dated primary sources beat blog posts, which beat recollection.**
2. **Training data is never a source.** If a claim can only be supported from memory, it is unverifiable — say so plainly.
3. **Unverifiable never becomes fact.** It goes to the spec's `## Unverified assumptions` with what's missing and what would settle it.

Sub-agents rather than one sequential pass: it keeps the main thread's context free for the design itself, and separate clusters don't contaminate each other's conclusions.

## Step 2 — Component inventory

For every piece of the system: exact name, exact version, one-sentence responsibility, and what it talks to.

Cheap, and it earns its place — two components with overlapping responsibilities, or a component nobody can write a single sentence for, surface here rather than three tasks into implementation.

## Step 3 — Discuss the system

Back and forth with the operator, in words, until you both agree what's being built. Prose, trade-offs, alternatives, open questions — the ordinary design conversation, now standing on verified ground.

**Do not draw yet.** The diagram is a rendering of an agreed architecture, not the vehicle for proposing one. A picture makes a design decision look settled before it has been argued.

**If this step changes the architecture** — a different vendor, a different approach, a new dependency — **run a top-up fact-check on the new claims before moving on.** Otherwise the verification silently covers only the design that got abandoned.

## Step 4 — Draw it

Only when the multi-part test above passes.

Hand-author an SVG. Show it inline in the conversation. Walk the operator through it — the data flow, what each arrow carries, where the boundaries sit. Iterate on their feedback until the picture is right; expect more than one round.

**Every diagram in this repo must show:**

- **Trust boundaries** — what runs on the device, what runs on our servers, what runs at a vendor.
- **What crosses each arrow** — the actual payload, not just "data".
- **Transient vs. permanently retained** — which stores get cleaned up, which keep the artifact.

This project may process voice input and uses a hosted database. A diagram that does not identify which data is transient, which data is durable, and what crosses the Supabase/RunPod boundary is incomplete.

## Step 5 — Save and write

- **Diagram** → `docs/design/diagrams/<date>-<slug>.svg`, linked from the spec.
- **Spec** → `docs/specs/<date>-<slug>-design.md`, containing:
  - verified claims carrying their source and check-date **inline, where the claim is made**
  - a `## Unverified assumptions` section — **always present**, even when short — listing what could not be confirmed and what would confirm it

## Common mistakes

- **Drawing before the discussion converges.** You render the wrong system, beautifully, and the polish makes it harder to argue with.
- **Drawing before the fact-check.** The same mistake, one step earlier.
- **Citing yourself.** "I know Expo SDK 57 ships expo-audio" is not verification. A URL and a date is.
- **Letting an assumption harden.** A claim listed as unverified in the spec that reappears as settled fact in the plan — that is this skill's entire failure mode, just relocated one document later.
- **Saving a diagram nobody was shown.** If it wasn't rendered inline and talked through, it's decoration; the value is in the conversation it forces.
- **Skipping the fact-check because the ticket looks small.** The claims nobody double-checks are the ones that looked obvious.
