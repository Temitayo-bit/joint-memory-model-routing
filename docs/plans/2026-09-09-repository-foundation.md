# Repository foundation plan

Date: 2026-09-09
Status: in progress

## Objective

Create a public repository under `Temitayo-bit` for the Senior Research project with a PR-only workflow, passing CI and CodeRabbit review gates, agent guidance, research documentation, and a non-optional GPU shutdown procedure.

## Tasks

1. Create the local repository foundation and copied planning/review skills.
2. Create the public GitHub repository after `Temitayo-bit` authentication is verified.
3. Push this work as a feature branch and open the first pull request rather than pushing foundation content to `main`.
4. Configure `main` to require pull requests and the `CI / test`, `CI / build`, and CodeRabbit checks before merge, where the authenticated account has permission.
5. Verify the pull-request checks and report any GitHub permission limitation precisely.

## Constraints

- The initial empty remote commit is platform bootstrap only; all repository content is delivered in the feature PR.
- RunPod is temporary compute. Every session ends with a verified pod termination and documented cost.
- Supabase/durable backups, not temporary pod storage, hold data needed after a session.
