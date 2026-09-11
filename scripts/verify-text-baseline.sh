#!/usr/bin/env bash
set -euo pipefail

mode="${1:-}"
case "$mode" in
  test|build) ;;
  *) echo "usage: $0 {test|build}" >&2; exit 64 ;;
esac

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

export PYTHONPATH="$root"

python3 -m unittest discover -s experiments/text_baseline/tests -t "$root"

deno_bin="${DENO:-}"
if [[ -z "$deno_bin" ]]; then
  if command -v deno >/dev/null 2>&1; then
    deno_bin="$(command -v deno)"
  elif [[ -x "$HOME/.deno/bin/deno" ]]; then
    deno_bin="$HOME/.deno/bin/deno"
  fi
fi

if [[ -z "$deno_bin" ]]; then
  echo "UNVERIFIED: deno is not installed; Deno type-check and tests did not run." >&2
  exit 1
fi

deno_files=()
while IFS= read -r file; do
  deno_files+=("$file")
done < <(find supabase/functions/text-baseline-pilot -name '*.ts' | sort)
"$deno_bin" check "${deno_files[@]}"
"$deno_bin" test --check supabase/functions/text-baseline-pilot

sql_file="supabase/migrations/20260911000000_pilot_text_baseline.sql"
python3 - "$sql_file" <<'PY'
import pathlib, sys
text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
required = (
    "security invoker",
    "set search_path = ''",
    "enable row level security",
    "verify_pilot_snapshot_ownership",
    "retrieve_pilot_memory",
    "extensions.vector(384)",
    "operator(extensions.<=>)",
    "claim_pilot_call",
    "insert_pilot_pending",
    "finalize_pilot_result",
    "revoke all on table public.pilot_request_results",
    "revoke all on table public.pilot_call_log",
)
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit("SQL contract missing: %s" % missing)
# Static presence checks only: CI has no live Postgres. Runtime RLS/grant
# execution remains a local supabase db lint / apply responsibility.
forbidden = (
    "grant select, insert, update on table public.pilot_request_results",
    "grant insert on table public.pilot_call_log",
)
leaked = [item for item in forbidden if item in text]
if leaked:
    raise SystemExit("SQL contract forbids: %s" % leaked)
print("Static SQL migration contract presence checks passed (not live RLS execution).")
PY

if command -v supabase >/dev/null 2>&1; then
  if supabase db lint --help >/dev/null 2>&1; then
    set +e
    lint_output="$(supabase db lint 2>&1)"
    lint_status=$?
    set -e
    if [[ "$lint_status" -ne 0 ]]; then
      lower="$(printf '%s' "$lint_output" | tr '[:upper:]' '[:lower:]')"
      if printf '%s' "$lower" | grep -Eq 'connect|connection|could not connect|database .* does not exist|no such host|dial tcp|refused|unavailable|not running|failed to connect'; then
        echo "UNVERIFIED: supabase db lint could not reach a local database. Exit $lint_status." >&2
      else
        printf '%s\n' "$lint_output" >&2
        echo "supabase db lint failed with exit $lint_status." >&2
        exit "$lint_status"
      fi
    fi
  else
    echo "UNVERIFIED: supabase db lint is unavailable in this CLI." >&2
  fi
else
  echo "UNVERIFIED: supabase CLI is not installed; db lint did not run." >&2
fi

echo "Text-baseline $mode checks passed."
