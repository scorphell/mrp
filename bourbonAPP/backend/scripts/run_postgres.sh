#!/usr/bin/env bash
# Sobe/verifica o PostgreSQL nativo do Termux (sem systemd) via pg_ctl + nohup.
# Uso: bash scripts/run_postgres.sh   (idempotente)
set -euo pipefail

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
PGDATA="${PGDATA:-$PREFIX/var/lib/postgresql}"
PGLOG="${PGLOG:-$PREFIX/var/log/postgresql.log}"

if [[ ! -f "$PGDATA/PG_VERSION" ]]; then
  echo "PGDATA não inicializado em $PGDATA" >&2
  exit 1
fi

if pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  echo "PostgreSQL já está rodando."
  pg_isready
  exit 0
fi

mkdir -p "$(dirname "$PGLOG")"
nohup pg_ctl -D "$PGDATA" -l "$PGLOG" start >/dev/null 2>&1
for _ in $(seq 1 15); do
  if pg_isready >/dev/null 2>&1; then
    echo "PostgreSQL pronto em $(pg_isready)."
    exit 0
  fi
  sleep 1
done
echo "PostgreSQL não respondeu; veja $PGLOG" >&2
exit 1
