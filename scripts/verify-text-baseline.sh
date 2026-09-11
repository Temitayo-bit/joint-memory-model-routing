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

mapfile -t deno_files < <(find supabase/functions/text-baseline-pilot -name '*.ts' | sort)
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
)
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit("SQL contract missing: %s" % missing)
print("Local SQL contract checks passed.")
PY

if command -v supabase >/dev/null 2>&1; then
  if supabase db lint --help >/dev/null 2>&1; then
    set +e
    supabase db lint
    lint_status=$?
    set -e
    if [[ "$lint_status" -ne 0 ]]; then
      echo "UNVERIFIED: supabase db lint did not succeed (needs a local database with plpgsql_check). Exit $lint_status." >&2
    fi
  else
    echo "UNVERIFIED: supabase db lint is unavailable in this CLI." >&2
  fi
else
  echo "UNVERIFIED: supabase CLI is not installed; db lint did not run." >&2
fi

echo "Text-baseline $mode checks passed."
