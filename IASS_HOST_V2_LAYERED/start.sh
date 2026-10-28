#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="${IASS_HOST:-0.0.0.0}"
PORT="${IASS_PORT:-5000}"
MODE="normal"

case "${1:-}" in
  --debug) MODE="debug" ;;
  --offline) MODE="offline" ;;
  "") ;;
  *)
    echo "[IASS] Unknown option: $1"
    echo "Usage: ./start.sh [--debug|--offline]"
    exit 2
    ;;
esac

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[IASS][FATAL] $PYTHON_BIN is required."
  exit 1
fi

PY_VERSION="$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_MAJOR="$($PYTHON_BIN -c 'import sys; print(sys.version_info.major)')"
PY_MINOR="$($PYTHON_BIN -c 'import sys; print(sys.version_info.minor)')"
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
  echo "[IASS][FATAL] Python 3.11+ is required (found $PY_VERSION)."
  exit 1
fi

# Keep the Python environment persistent across project re-extractions/updates.
# A local .venv is still preferred when one already exists, but fresh ZIP
# extractions reuse the user's IASS environment instead of reinstalling every boot.
LOCAL_VENV="$ROOT/.venv"
PERSISTENT_VENV="${IASS_VENV_DIR:-$HOME/.local/share/iass_host_v1/.venv}"

if [ -d "$LOCAL_VENV" ]; then
  VENV="$LOCAL_VENV"
else
  VENV="$PERSISTENT_VENV"
  if [ ! -d "$VENV" ]; then
    echo "[IASS] Creating persistent Python environment..."
    mkdir -p "$(dirname "$VENV")"
    if ! "$PYTHON_BIN" -m venv "$VENV"; then
      echo "[IASS][FATAL] Could not create Python environment. On Ubuntu install: sudo apt install python3-venv python3-full"
      exit 1
    fi
  fi
fi

PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
STAMP="$VENV/.iass_deps_hash"

if [ ! -x "$PY" ]; then
  echo "[IASS][FATAL] Virtual environment is incomplete: $PY"
  exit 1
fi

# Install dependencies only on first use or when requirements.txt actually changes.
REQ_HASH="$(sha256sum "$ROOT/requirements.txt" | awk '{print $1}')"
INSTALLED_HASH="$(cat "$STAMP" 2>/dev/null || true)"
if [ "$REQ_HASH" != "$INSTALLED_HASH" ]; then
  echo "[IASS] Installing dependencies (first run or requirements changed)..."
  "$PY" -m pip install --upgrade pip >/dev/null
  "$PIP" install -r "$ROOT/requirements.txt"
  printf '%s\n' "$REQ_HASH" > "$STAMP"
else
  echo "[IASS] Dependencies already installed. Skipping pip install."
fi

export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export IASS_START_MODE="$MODE"

PID_FILE="$ROOT/.iass.pid"
if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    CMDLINE="$(tr '\0' ' ' < "/proc/$OLD_PID/cmdline" 2>/dev/null || true)"
    if [[ "$CMDLINE" == *"iass"* ]]; then
      echo "[IASS] IASS is already running (PID $OLD_PID)."
      exit 0
    fi
  fi
  rm -f "$PID_FILE"
fi

echo $$ > "$PID_FILE"
cleanup() { rm -f "$PID_FILE"; }
trap cleanup EXIT
trap 'echo; echo "[IASS] Shutting down..."; exit 0' INT TERM

IP="$($PY -c 'import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(.2); s.connect(("1.1.1.1",80)); print(s.getsockname()[0]); s.close()' 2>/dev/null || true)"

# Phone camera access requires a secure context. Generate a local self-signed
# certificate automatically so the user does not need Chrome insecure-origin flags.
CERT_DIR="$ROOT/certs"
CERT_FILE="$CERT_DIR/iass-cert.pem"
KEY_FILE="$CERT_DIR/iass-key.pem"
mkdir -p "$CERT_DIR"

if ! command -v openssl >/dev/null 2>&1; then
  echo "[IASS][FATAL] OpenSSL is required to enable HTTPS for the phone camera."
  echo "Install it with: sudo apt install openssl"
  exit 1
fi

CERT_OK=0
if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ] && [ -n "$IP" ]; then
  if openssl x509 -in "$CERT_FILE" -noout -checkend 86400 >/dev/null 2>&1 && \
     openssl x509 -in "$CERT_FILE" -noout -text 2>/dev/null | grep -q "IP Address:$IP"; then
    CERT_OK=1
  fi
fi

if [ "$CERT_OK" -eq 0 ]; then
  echo "[IASS] Generating local HTTPS certificate..."
  SAN="DNS:localhost,IP:127.0.0.1"
  if [ -n "$IP" ]; then SAN="$SAN,IP:$IP"; fi
  TMP_CONF="$CERT_DIR/openssl.cnf.tmp"
  cat > "$TMP_CONF" <<EOF
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no
[req_distinguished_name]
CN = IASS Local Host
[v3_req]
subjectAltName = $SAN
keyUsage = digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
EOF
  openssl req -x509 -nodes -newkey rsa:2048 -sha256 -days 365 \
    -keyout "$KEY_FILE" -out "$CERT_FILE" -config "$TMP_CONF" >/dev/null 2>&1
  rm -f "$TMP_CONF"
  chmod 600 "$KEY_FILE"
  chmod 644 "$CERT_FILE"
fi

printf '\n'
printf '╔══════════════════════════════════════════════════╗\n'
printf '║        IASS — INTELLIGENT ACTIVE                ║\n'
printf '║        SURVEILLANCE SYSTEM                      ║\n'
printf '╠══════════════════════════════════════════════════╣\n'
printf '║  [✓] Python %s environment ready                ║\n' "$PY_VERSION"
printf '║  [✓] Dependencies ready                         ║\n'
printf '║  [✓] HTTPS camera transport ready               ║\n'
printf '║  [~] Optional camera/hardware may be offline    ║\n'
printf '║                                                  ║\n'
printf '║  Dashboard: https://127.0.0.1:%-5s             ║\n' "$PORT"
if [ -n "$IP" ]; then
  printf '║  Phone:    https://%s:%-5s/camera      ║\n' "$IP" "$PORT"
fi
printf '║  Mode: %-40s║\n' "$MODE"
printf '╚══════════════════════════════════════════════════╝\n'
printf '\n'
if [ -n "$IP" ]; then
  echo "[IASS] On the phone, open: https://$IP:$PORT/camera"
  echo "[IASS] First visit: accept the browser certificate warning, then tap Start Camera."
fi

echo "[IASS] Starting IASS..."
"$PY" -m iass --host "$HOST" --port "$PORT" --ssl-keyfile "$KEY_FILE" --ssl-certfile "$CERT_FILE"
