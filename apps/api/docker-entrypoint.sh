#!/bin/sh
set -e

# Render (and similar) often provide postgres:// — normalize for SQLAlchemy.
if [ -n "${DATABASE_URL:-}" ]; then
  case "$DATABASE_URL" in
    postgres://*)
      DATABASE_URL="postgresql://${DATABASE_URL#postgres://}"
      ;;
  esac
  if [ -z "${DATABASE_URL_SYNC:-}" ]; then
    DATABASE_URL_SYNC="$DATABASE_URL"
  fi
  case "$DATABASE_URL" in
    postgresql+asyncpg://*) ;;
    postgresql://*)
      DATABASE_URL="postgresql+asyncpg://${DATABASE_URL#postgresql://}"
      ;;
  esac
  export DATABASE_URL DATABASE_URL_SYNC
fi

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "Running database migrations..."
  alembic upgrade head
fi

exec "$@"
