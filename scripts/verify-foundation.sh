#!/usr/bin/env bash
set -euo pipefail

mode="${1:-}"
case "$mode" in
  test|build) ;;
  *) echo "usage: $0 {test|build}" >&2; exit 64 ;;
esac

required_files=(
  AGENTS.md
  README.md
  architecture.md
  docs/README.md
  docs/operations/runpod-session-runbook.md
  docs/operations/gpu-session-log.md
  docs/specs/2026-09-09-vercel-supabase-runpod-deployment-design.md
  docs/design/diagrams/2026-09-09-vercel-supabase-runpod.svg
  docs/research/evaluation-protocol.md
  docs/specs/2026-09-11-text-baseline-harness-design.md
  docs/design/diagrams/2026-09-11-text-baseline-harness.svg
  docs/plans/2026-09-11-text-baseline-harness.md
  experiments/text_baseline/README.md
  supabase/migrations/20260911000000_pilot_text_baseline.sql
  .github/pull_request_template.md
)

for file in "${required_files[@]}"; do
  [[ -s "$file" ]] || { echo "Missing required file: $file" >&2; exit 1; }
done

credential_pattern='(SUPABASE[_](SERVICE_ROLE_KEY|SECRET_KEY)|RUNPOD[_](API_KEY|INFERENCE_TOKEN)|sb[_]secret_|ghp_[A-Za-z0-9]{20,}|github[_]pat_)'
if git grep -q -E "$credential_pattern"; then
  echo "Potential credential found in tracked content." >&2
  exit 1
fi

if [[ "$mode" == "build" ]]; then
  required_architecture_contract=(
    'The system studies a controller for latency-constrained voice-agent requests.'
    'small model without long-term-memory retrieval;'
    'retrieve relevant long-term memory, then use the small model; or'
    'retrieve relevant long-term memory and use a larger model.'
    'Browser/client --JWT request--> Supabase Edge Function (controller) -> RunPod model server'
    '**Vercel:** hosts the public Next.js web application'
    '**Supabase free tier:** Supabase Auth, durable structured memory and vectors'
    '**RunPod:** temporary, self-configured GPU compute'
    'A pod is terminated after active use. Its local disk is not durable storage.'
  )

  for requirement in "${required_architecture_contract[@]}"; do
    grep -Fq "$requirement" architecture.md || {
      echo "Architecture contract requirement missing." >&2
      exit 1
    }
  done

  required_shutdown_contract=(
    'Confirm the repository is pushed'
    'Verify that nothing required remains only on the pod volume.'
    'Terminate the pod.'
    'Delete attached pod storage.'
    'planned deletion date'
    'gpu-session-log.md'
  )

  for requirement in "${required_shutdown_contract[@]}"; do
    grep -Fq "$requirement" docs/operations/runpod-session-runbook.md || {
      echo "Shutdown contract requirement missing." >&2
      exit 1
    }
  done

  required_deployment_security_contract=(
    '![Deployment boundary](../design/diagrams/2026-09-09-vercel-supabase-runpod.svg)'
    'Vercel holds only public client configuration'
    'The RunPod proxy URL and inference credential belong only in Supabase Edge Function secrets.'
    'model server must reject requests without its inference token.'
    'The Edge Function must require a signed-in user and use RLS-scoped database access.'
    'Service-role access is not used for ordinary user requests.'
    'request-size limits, payload validation, and per-token rate limiting'
    "withSupabase({ auth: 'user' })"
    'browser invokes the Edge Function directly'
    'without retry loops or data loss'
    'authenticated `/healthz` check succeed'
    'The initial HTTP-proxy request budget is 75 seconds'
    'show a clear service-unavailable message'
  )

  for requirement in "${required_deployment_security_contract[@]}"; do
    grep -Fq "$requirement" docs/specs/2026-09-09-vercel-supabase-runpod-deployment-design.md architecture.md AGENTS.md || {
      echo "Deployment security contract requirement missing." >&2
      exit 1
    }
  done

  grep -Fq 'A RunPod server must be terminated when it is not actively being used.' AGENTS.md
  grep -Fq '$75 semester cap' AGENTS.md
fi

echo "Foundation $mode checks passed."
