#!/usr/bin/env bash
# Sobe o gunicorn da API em background (nohup) e salva o PID em gunicorn.pid.
# Uso: bash scripts/run_server.sh [--foreground|-f] [--port N] [--bind HOST]
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BACKEND_DIR"

PORT="${PORT:-8000}"
BIND="${BIND:-0.0.0.0}"
FOREGROUND=0
PID_FILE="gunicorn.pid"
LOG_FILE="gunicorn.log"
VENV_DIR=".venv"
WORKERS=2
TIMEOUT=30

usage() {
  cat <<EOF
Uso: $0 [opções]

Opções:
  -f, --foreground   roda em foreground (sem nohup; Ctrl+C para parar)
      --port N       porta de escuta (default: 8000)
      --bind HOST    endereço de escuta (default: 0.0.0.0)
  -h, --help         mostra esta ajuda

Variáveis de ambiente alternativas: PORT, BIND.
EOF
}

while (($# > 0)); do
  case "$1" in
    -f | --foreground) FOREGROUND=1; shift ;;
    --port) PORT="${2:?--port exige um valor}"; shift 2 ;;
    --port=*) PORT="${1#*=}"; shift ;;
    --bind) BIND="${2:?--bind exige um valor}"; shift 2 ;;
    --bind=*) BIND="${1#*=}"; shift ;;
    -h | --help) usage; exit 0 ;;
    *)
      echo "Erro: argumento desconhecido: $1" >&2
      usage
      exit 1
      ;;
  esac
done

[[ "$PORT" =~ ^[0-9]+$ ]] || { echo "Erro: porta inválida: $PORT" >&2; exit 1; }
[[ -d "$VENV_DIR" ]] || { echo "Erro: venv não encontrada em $BACKEND_DIR/$VENV_DIR" >&2; exit 1; }
source "$VENV_DIR/bin/activate"
command -v gunicorn >/dev/null 2>&1 || { echo "Erro: gunicorn não instalado na venv" >&2; exit 1; }

ACCESS_URL="http://${BIND}:${PORT}"
if [[ "$BIND" == "0.0.0.0" || "$BIND" == "::" || "$BIND" == "127.0.0.1" ]]; then
  ACCESS_URL="http://localhost:${PORT}"
fi

GUNICORN_ARGS=(
  config.wsgi:application
  --bind "${BIND}:${PORT}"
  --workers "$WORKERS"
  --timeout "$TIMEOUT"
  --access-logfile -
  --error-logfile -
)

if [[ "$FOREGROUND" == 1 ]]; then
  echo "gunicorn ouvindo em $ACCESS_URL (Ctrl+C para parar)"
  exec gunicorn "${GUNICORN_ARGS[@]}"
fi

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE")"
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "gunicorn já está rodando (PID $OLD_PID)."
    exit 0
  fi
fi

nohup gunicorn "${GUNICORN_ARGS[@]}" >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

sleep 3
if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "gunicorn rodando em $ACCESS_URL (PID $(cat "$PID_FILE")); log: $LOG_FILE"
else
  echo "gunicorn falhou ao subir; veja $LOG_FILE" >&2
  exit 1
fi
