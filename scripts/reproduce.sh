#!/usr/bin/env bash
# Run every check in this repository once and keep the evidence.
#   bash scripts/reproduce.sh
# Writes evaluation/logs/<timestamp>/ with one log per check, the environment, and SUMMARY.md.
# Needs the same things as quickstart.sh (Docker, Ollama, the venv). Takes about 40 minutes with the 7B model.
set -uo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source venv/bin/activate

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="evaluation/logs/$STAMP"
mkdir -p "$OUT"
SUMMARY="$OUT/SUMMARY.md"
FAILED=0

run() {  # run <name> <command...>: saves the full output, records the last meaningful line
  local name="$1"; shift
  echo "==> $name"
  "$@" > "$OUT/$name.log" 2>&1
  local code=$?
  local last
  last="$(grep -E "passed|checks passed|defended|accounted|Wrote|PASS|FAIL" "$OUT/$name.log" | tail -1 | cut -c1-160)"
  [ "$code" -ne 0 ] && FAILED=1
  printf '| %s | %s | %s |\n' "$name" "$([ $code -eq 0 ] && echo ok || echo "exit $code")" "${last:-see log}" >> "$SUMMARY"
}

{
  echo "# Reproducibility run $STAMP"
  echo
  echo "- Commit: $(git rev-parse --short HEAD) ($(git status --porcelain | wc -l | tr -d ' ') uncommitted changes)"
  echo "- Python: $(python --version 2>&1)"
  echo "- Model: $(grep -E '^LLM_MODEL=' .env 2>/dev/null || echo 'default from config') ; Ollama: $(ollama --version 2>&1 | tail -1)"
  echo "- Machine: $(uname -sm)"
  echo
  echo "| Check | Result | Last line |"
  echo "|---|---|---|"
} > "$SUMMARY"
pip freeze > "$OUT/pip-freeze.txt"

curl -fs http://127.0.0.1:8000/health >/dev/null || { echo "Start the server first: bash scripts/quickstart.sh"; exit 1; }

run unit_tests            python -m pytest -q tests
run access_checks         python -m scripts.verify_access
# verify_access rebuilds the demo accounts without passwords; give them back before the checks that log in.
run seed_demo             python -m scripts.seed_demo
run validator_check       python -m scripts.check_validator
run inspector_check       python -m scripts.check_inspector
run crash_test            python -m scripts.crash_test
run smoke_test            python -m scripts.smoke_test
run security_probe        python -m scripts.security_probe
run evaluation_86         python -m scripts.evaluate
run evaluation_independent python -m scripts.evaluate --eval-set evaluation/independent_set.json --tag independent
run evaluation_research   python -m scripts.evaluate_research

cp /tmp/uvicorn.log "$OUT/server.log" 2>/dev/null || true
cp evaluation/EVAL_REPORT.md evaluation/INDEPENDENT_REPORT.md evaluation/RESEARCH_EVAL.md "$OUT/" 2>/dev/null || true
echo; cat "$SUMMARY"
echo; echo "Evidence saved in $OUT"
exit $FAILED
