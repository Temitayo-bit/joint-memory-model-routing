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
  docs/research/evaluation-protocol.md
  .github/pull_request_template.md
)

for file in "${required_files[@]}"; do
  [[ -s "$file" ]] || { echo "Missing required file: $file" >&2; exit 1; }
done

credential_pattern='(SUPABASE[_]SERVICE_ROLE_KEY|RUNPOD[_]API_KEY|ghp_[A-Za-z0-9]{20,}|github[_]pat_)'
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
    '**Supabase free tier:** durable structured memory and vectors'
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

  grep -Fq 'A RunPod server must be terminated when it is not actively being used.' AGENTS.md
  grep -Fq '$75 semester cap' AGENTS.md
fi

echo "Foundation $mode checks passed."
