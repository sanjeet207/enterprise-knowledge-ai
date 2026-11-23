#!/usr/bin/env bash
# Backup and restore drill. Dumps the running database, restores the dump into a scratch database, compares the row
# count of every table and the number of indexes, then removes the scratch database. The live database is only read.
# Needs the Docker database container (docker compose up -d db). The dump is written to backups/ (git-ignored: it
# holds real data). Exit code 0 only when the restored copy matches.
set -euo pipefail
cd "$(dirname "$0")/.."

DB=knowledge
SCRATCH=knowledge_restore_drill
OUT=${1:-backups}
mkdir -p "$OUT"
FILE="$OUT/knowledge-$(date +%Y%m%d-%H%M%S).dump"
dc() { docker compose exec -T db "$@" </dev/null; }

echo "==> dump $DB"
start=$(date +%s)
docker compose exec -T db pg_dump -U app -Fc "$DB" > "$FILE"
echo "    $FILE ($(du -h "$FILE" | cut -f1), $(( $(date +%s) - start ))s)"

echo "==> restore into scratch database $SCRATCH"
start=$(date +%s)
dc psql -U app -d postgres -q -c "DROP DATABASE IF EXISTS $SCRATCH" -c "CREATE DATABASE $SCRATCH"
docker compose exec -T db pg_restore -U app -d "$SCRATCH" --no-owner < "$FILE"
echo "    restored in $(( $(date +%s) - start ))s"

counts() {
  local db=$1 t
  for t in $(dc psql -U app -d "$db" -At -c "select table_name from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1"); do
    echo "$t $(dc psql -U app -d "$db" -At -c "select count(*) from \"$t\"")"
  done
  echo "(indexes) $(dc psql -U app -d "$db" -At -c "select count(*) from pg_indexes where schemaname='public'")"
}

echo "==> compare"
counts "$DB" > /tmp/drill_live.txt
counts "$SCRATCH" > /tmp/drill_restored.txt
status=0
if diff /tmp/drill_live.txt /tmp/drill_restored.txt > /tmp/drill_diff.txt; then
  echo "PASS  restored copy matches: $(( $(wc -l < /tmp/drill_live.txt) - 1 )) tables, same row counts, same index count"
else
  echo "FAIL  differences (live < , restored >):"; cat /tmp/drill_diff.txt; status=1
fi

dc psql -U app -d postgres -q -c "DROP DATABASE IF EXISTS $SCRATCH"
echo "==> scratch database removed"
exit $status
