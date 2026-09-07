#!/usr/bin/env bash
#
# Everything CI runs, in the same order, so a green local run means a green pipeline.
#
#   ./scripts/check.sh            format check, lint, type check, tests (no integration)
#   ./scripts/check.sh --fix      apply formatting and autofixable lint first
#   ./scripts/check.sh --all      also run the integration tests (needs Meilisearch up)

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO_ROOT="$PWD"

FIX=0
ALL=0
for arg in "$@"; do
    case "$arg" in
        --fix) FIX=1 ;;
        --all) ALL=1 ;;
        -h|--help) sed -n '2,8p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

step() { printf '\n\033[36m==> %s\033[0m\n' "$*"; }
FAILED=()

# Every Python check runs with backend/ as the working directory. pytest resolves `testpaths`
# and the `tests` package relative to the rootdir it discovers, so running it from the repo
# root silently fails to import the test package.
run_backend() {
    local name="$1"; shift
    step "$name"
    if ! (cd "$REPO_ROOT/backend" && uv run "$@"); then FAILED+=("$name"); fi
}

if [ "$FIX" -eq 1 ]; then
    step "Formatting and autofixing"
    # `|| true`, because `ruff check --fix` exits non-zero when anything is left that it cannot
    # fix automatically. Under `set -e` that would abort the run, so `--fix` would report the
    # unfixable lint and then never get as far as the tests - the opposite of what it is for.
    # The `ruff check` step below reports whatever survived, and sets the exit code.
    (cd backend && uv run ruff format src tests && uv run ruff check --fix src tests) || true
fi

run_backend "ruff format --check" ruff format --check src tests
run_backend "ruff check"          ruff check src tests
run_backend "ty check"            ty check

PYTEST_ARGS=(pytest --cov=food_api --cov-report=term-missing --cov-fail-under=85)
if [ "$ALL" -eq 1 ]; then
    run_backend "pytest (with integration)" "${PYTEST_ARGS[@]}"
else
    run_backend "pytest" "${PYTEST_ARGS[@]}" -m "not integration"
fi

if command -v bun >/dev/null 2>&1 && [ -d frontend/node_modules ]; then
    step "frontend typecheck"
    (cd frontend && bun run typecheck) || FAILED+=("frontend typecheck")
    step "frontend lint"
    (cd frontend && bun run lint) || FAILED+=("frontend lint")
    step "frontend tests"
    (cd frontend && bun run test) || FAILED+=("frontend tests")
else
    printf '\n\033[33mSkipping frontend checks\033[0m (bun or frontend/node_modules missing).\n'
fi

if [ ${#FAILED[@]} -eq 0 ]; then
    printf '\n\033[32mAll checks passed.\033[0m\n'
else
    printf '\n\033[31mFailed:\033[0m %s\n' "${FAILED[*]}"
    exit 1
fi
