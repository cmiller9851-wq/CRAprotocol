#!/usr/bin/env bash
set -euo pipefail

# Supply secrets through the parent process environment, not command-line
# arguments or committed files. The child runner inherits both variables.
if [[ -z "${DATABASE_URL:-}" ]]; then
  printf '%s\n' 'DATABASE_URL must be exported before starting the runner.' >&2
  exit 1
fi
if [[ -z "${STRIPE_ACCOUNT_ID:-}" ]]; then
  printf '%s\n' 'STRIPE_ACCOUNT_ID must be exported before starting the runner.' >&2
  exit 1
fi

case "$DATABASE_URL" in
  postgres://*|postgresql://*) ;;
  *)
    printf '%s\n' 'DATABASE_URL must use postgres:// or postgresql://.' >&2
    exit 1
    ;;
esac

if [[ "$STRIPE_ACCOUNT_ID" != "acct_1T0RqjD96uXY23io" ]]; then
  printf '%s\n' 'STRIPE_ACCOUNT_ID does not match the configured read-only routing account.' >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  printf '%s\n' 'Usage: with-runner-env.sh -- COMMAND [ARG...]' >&2
  exit 2
fi
if [[ "${1:-}" == "--" ]]; then
  shift
fi
if [[ $# -eq 0 ]]; then
  printf '%s\n' 'A runner command is required after --.' >&2
  exit 2
fi

# Do not echo the environment or command; replace this process so signals and
# exit status are delivered directly to the runner.
exec "$@"
