#!/usr/bin/env bash
# One command from a fresh clone to a running, verified system:  bash scripts/quickstart.sh
# Safe to re-run. Needs Python 3.12, Docker (running) and Ollama (running).
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n==> %s\n' "$1"; }
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1. $2"; exit 1; }; }

step "Checking requirements"
need python3 "Install Python 3.12."
need docker "Install Docker Desktop."
need ollama "Install Ollama from https://ollama.com."
docker info >/dev/null 2>&1 || { echo "Docker is installed but not running. Open Docker Desktop and retry."; exit 1; }
curl -fs http://localhost:11434 >/dev/null || { echo "Ollama is not running. Open the Ollama app (or: brew services start ollama) and retry."; exit 1; }

step "Python environment"
[ -d venv ] || python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
pip install -q -r requirements-dev.txt

step "Configuration (.env)"
if [ ! -f .env ]; then
  cp .env.example .env
  secret="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed -i.bak "s|^JWT_SECRET=.*|JWT_SECRET=${secret}|" .env && rm -f .env.bak
  echo "Created .env with a fresh random JWT_SECRET"
else
  echo ".env already exists, leaving it as it is"
fi

step "Database"
docker compose up -d --wait db
python -m scripts.init_db

step "Language model"
MODEL="$(grep -E '^LLM_MODEL=' .env | cut -d= -f2- || true)"
MODEL="${MODEL:-qwen2.5:7b}"
if ollama list | awk 'NR>1 {print $1}' | grep -qx "$MODEL"; then
  echo "$MODEL is already downloaded"
else
  echo "Downloading $MODEL (about 5 GB, one time)"
  ollama pull "$MODEL"
fi

step "Unit tests and access-control checks"
python -m pytest -q tests
python -m scripts.verify_access | tail -1

step "Demo company data"
python -m scripts.seed_demo

step "Reranking model (downloaded once, then kept in ~/.cache)"
python -c "from app.services.reranker import warm_up; warm_up(); print('reranker ready')"

step "Starting the server"
pkill -f "uvicorn app.main" 2>/dev/null || true
sleep 1
nohup uvicorn app.main:app --port 8000 > /tmp/uvicorn.log 2>&1 &
for _ in $(seq 1 60); do
  curl -fs http://127.0.0.1:8000/health >/dev/null 2>&1 && break
  sleep 1
done
curl -fs http://127.0.0.1:8000/health >/dev/null || { echo "Server did not start. See /tmp/uvicorn.log"; exit 1; }

step "End-to-end smoke test (about a minute)"
python -m scripts.smoke_test

printf '\nReady. Open http://127.0.0.1:8000 and sign in with analyst@acme.test / DemoPass2026x\n'
printf 'Server log: /tmp/uvicorn.log   Stop it with: pkill -f "uvicorn app.main"\n'
