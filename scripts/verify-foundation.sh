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

credential_matches="$(find . -type f \
  ! -path './.git/*' \
  ! -path './docs/*' \
  ! -path './.agents/*' \
  ! -path './tools/*' \
  ! -path './scripts/verify-foundation.sh' \
  ! -name '*.example' \
  -exec grep -nE '(SUPABASE_SERVICE_ROLE_KEY|RUNPOD_API_KEY|ghp_[A-Za-z0-9]{20,}|github_pat_)' {} + 2>/dev/null || true)"

if [[ -n "$credential_matches" ]]; then
  printf '%s\n' "$credential_matches"
  echo "Potential credential found outside documented examples." >&2
  exit 1
fi

if [[ "$mode" == "build" ]]; then
  grep -q 'terminate the pod' AGENTS.md
  grep -q '\$75' AGENTS.md
fi

echo "Foundation $mode checks passed."
