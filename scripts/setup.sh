#!/usr/bin/env bash
#
# One-command setup: check prerequisites, install dependencies, start Meilisearch, seed it.
#
#   ./scripts/setup.sh              backend + Meilisearch, ready for ./scripts/dev.sh
#   ./scripts/setup.sh --full       also build and run the API and frontend containers
#   ./scripts/setup.sh --no-seed    skip indexing (useful when Meilisearch is already loaded)
#
# Anything with real logic lives in `food-api` (backend/src/food_api/cli.py) rather than here,
# so this script and its PowerShell twin cannot drift apart.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO_ROOT="$PWD"

FULL=0
SEED=1
for arg in "$@"; do
    case "$arg" in
        --full)    FULL=1 ;;
        --no-seed) SEED=0 ;;
        -h|--help) sed -n '2,10p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

info()  { printf '\033[36m==>\033[0m %s\n' "$*"; }
ok()    { printf '\033[32m  ok\033[0m %s\n' "$*"; }
fail()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

require() {
    command -v "$1" >/dev/null 2>&1 || fail "$1 is required but not on PATH. $2"
}

info "Checking prerequisites"
require docker "Install Docker Desktop or the Docker Engine: https://docs.docker.com/get-docker/"
require uv     "Install uv: https://docs.astral.sh/uv/getting-started/installation/"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required (\`docker compose\`)."
docker info >/dev/null 2>&1 || fail "Docker is installed but not running. Start it and retry."
ok "docker $(docker --version | awk '{print $3}' | tr -d ,), uv $(uv --version | awk '{print $2}')"

if [ ! -f .env ]; then
    info "Creating .env from .env.example"
    cp .env.example .env
    ok "wrote $REPO_ROOT/.env"
fi

info "Installing backend dependencies"
uv sync --project backend --frozen
ok "backend environment ready"

info "Starting Meilisearch"
docker compose up -d meilisearch
ok "meilisearch container up"

# Load .env into the environment so the CLI sees the same configuration as the containers do.
# `set -a` exports everything the file assigns; the directive has to sit directly above the
# `.` for shellcheck to honour it, and .env is generated above rather than committed, so there
# is nothing for it to follow.
set -a
# shellcheck disable=SC1091
. ./.env
set +a
export FOOD_API_MEILI_MASTER_KEY="${MEILI_MASTER_KEY:-devMasterKeyChangeMe}"
export FOOD_API_MEILI_URL="http://localhost:${MEILI_PORT:-7700}"

info "Waiting for Meilisearch and validating the dish corpus"
if [ "$SEED" -eq 1 ]; then
    uv run --project backend food-api bootstrap --timeout 90
else
    uv run --project backend food-api check
    uv run --project backend food-api wait-for-search --timeout 90
fi

if [ "$FULL" -eq 1 ]; then
    info "Building and starting the API and frontend containers"
    docker compose up -d --build api frontend
    ok "stack up"
    printf '\n  Frontend  http://localhost:%s\n' "${FRONTEND_PORT:-5173}"
    printf '  API docs  http://localhost:%s/api/docs\n' "${API_PORT:-8000}"
else
    printf '\n\033[32mSetup complete.\033[0m Next:\n'
    printf '  ./scripts/dev.sh     run the API and the frontend on the host with reload\n'
    printf '  ./scripts/check.sh   format, lint, type-check and test\n'
fi
printf '  Meilisearch  http://localhost:%s\n' "${MEILI_PORT:-7700}"
