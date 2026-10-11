#!/usr/bin/env bash
# Voxel Asset Registry — local setup and launch (verified on Linux).
#
#   ./run.sh                  prepare Python/frontend, then start API + UI
#   ./run.sh --build-demo     build starter examples, then start the service
#   ./run.sh --setup-only     prepare without starting the service
#   ./run.sh --doctor         check tools and paths without model builds
#   ./run.sh --dev            API reload + Vite hot reload (UI on :5173)
#
# Preparation reuses pinned dependencies and the frontend when inputs are unchanged.
# Personal overrides can be stored in ignored config.local.yaml.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

HOST=""
PORT=""
BUILD=0
BUILD_DEMO=0
DOCTOR=0
SETUP_ONLY=0
DEV=0
RELOAD=0
SETUP=1
FORCE_FRONTEND=0

usage() {
  sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

Options:
  --host HOST          bind address (default config, 127.0.0.1)
  --port PORT          port (default config, 8000)
  --build-demo         build only starter examples; fail if a build fails
  --build              build every stale variant; requires Blender
  --setup-only         prepare dependencies/frontend/registry, then exit
  --doctor             check tools and paths, then exit
  --dev                uvicorn reload + npm run dev
  --reload             reload backend/builder code
  --rebuild-frontend   force rebuild frontend/dist
  --no-setup           skip dependency/frontend/init preparation
  -h, --help           this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --build) BUILD=1; shift ;;
    --build-demo) BUILD_DEMO=1; shift ;;
    --setup-only) SETUP_ONLY=1; shift ;;
    --doctor) DOCTOR=1; shift ;;
    --dev) DEV=1; RELOAD=1; shift ;;
    --reload) RELOAD=1; shift ;;
    --rebuild-frontend) FORCE_FRONTEND=1; shift ;;
    --no-setup) SETUP=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;33m▸\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;31m!\033[0m %s\n' "$*" >&2; }
die()  { warn "$*"; exit 1; }

VENV="$ROOT/.venv"
PY="$VENV/bin/python"

# ---------------------------------------------------------------- python
setup_python() {
  command -v python3 >/dev/null || die "Python 3.11+ required (verified with 3.12)"
  python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' \
    || die "Python 3.11+ required; found $(python3 --version)"
  if [[ ! -x "$PY" ]]; then
    say "creating .venv"
    python3 -m venv "$VENV"
  fi
  local stamp="$VENV/.requirements.sha256"
  local sum
  sum="$(sha256sum requirements.txt constraints.txt)"
  if [[ ! -f "$stamp" || "$(cat "$stamp")" != "$sum" ]]; then
    say "installing pinned Python runtime dependencies"
    "$PY" -m pip install --disable-pip-version-check -q -r requirements.txt
    echo "$sum" > "$stamp"
  fi
  ok "Python: $("$PY" --version | cut -d' ' -f2) (.venv)"
}

# ---------------------------------------------------------------- node / frontend
load_node() {
  # nvm-установленный Node приоритетнее системного
  if [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
    # shellcheck disable=SC1091
    set +u; . "${NVM_DIR:-$HOME/.nvm}/nvm.sh" >/dev/null; set -u
  fi
  command -v npm >/dev/null
}

frontend_stale() {
  [[ $FORCE_FRONTEND -eq 1 || ! -f frontend/dist/index.html ]] && return 0
  [[ -n "$(find frontend/src frontend/index.html frontend/vite.config.ts frontend/tsconfig.json \
            frontend/package.json frontend/package-lock.json \
            -newer frontend/dist/index.html -print -quit 2>/dev/null)" ]]
}

setup_frontend() {
  local need_npm=0
  [[ $DEV -eq 1 ]] && need_npm=1
  frontend_stale && need_npm=1
  if [[ $need_npm -eq 0 ]]; then
    ok "frontend/dist is current"
    return
  fi
  if ! load_node; then
    [[ -f frontend/dist/index.html && $DEV -eq 0 ]] && { warn "npm unavailable; using existing frontend/dist"; return; }
    die "Node 20.19+ (Node 20) or 22.12+ and npm are required"
  fi
  node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit((a===20 && b>=19)||(a===22 && b>=12)||a>22 ? 0 : 1)' \
    || die "unsupported Node $(node --version); requires 20.19+ (Node 20) or 22.12+"
  [[ -f frontend/package-lock.json ]] || die "frontend/package-lock.json is missing"
  local stamp="frontend/node_modules/.registry-lock.sha256"
  local sum
  sum="$(sha256sum frontend/package.json frontend/package-lock.json)"
  if [[ ! -f "$stamp" || "$(cat "$stamp")" != "$sum" ]]; then
    say "npm ci (locked dependencies)"
    (cd frontend && npm ci --no-audit --no-fund --maxsockets=4 --fetch-retries=5)
    echo "$sum" > "$stamp"
  fi
  if [[ $DEV -eq 0 ]] && frontend_stale; then
    say "building frontend"
    (cd frontend && npm run build --silent)
  fi
  ok "frontend ready (Node $(node --version))"
}

# ---------------------------------------------------------------- registry / blender
setup_registry() {
  local registry
  registry="$("$PY" -c 'from backend.config import load_config; print(load_config().registry_dir)')"
  if [[ ! -f "$registry/palette.yaml" ]]; then
    say "initializing the configured registry from the shipped seed"
    "$PY" -m registry init
  fi
  local blender
  blender="$("$PY" -c 'from backend.config import load_config; print(load_config().blender_bin)')"
  if command -v "$blender" >/dev/null 2>&1; then
    ok "Blender: $(command -v "$blender")"
  else
    warn "Blender ('$blender') unavailable; browsing works, builds require Blender 5.1+"
    if [[ $BUILD -eq 1 || $BUILD_DEMO -eq 1 ]]; then
      die "model builds require Blender"
    fi
  fi
}

# ---------------------------------------------------------------- port
config_value() {
  "$PY" -c "from backend.config import load_config; c = load_config(); print(c.server.$1)"
}

port_free() {
  "$PY" - "$1" "$2" <<'EOF'
import socket, sys
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind((sys.argv[1], int(sys.argv[2])))
except OSError:
    sys.exit(1)
finally:
    s.close()
EOF
}

# ---------------------------------------------------------------- main
[[ $BUILD -eq 0 || $BUILD_DEMO -eq 0 ]] || die "choose either --build or --build-demo"
if [[ $DOCTOR -eq 1 ]]; then
  if [[ $SETUP -eq 1 ]]; then
    setup_python
  else
    [[ -x "$PY" ]] || die ".venv missing; run without --no-setup"
  fi
  load_node || true
  exec "$PY" -m registry doctor
fi
if [[ $SETUP -eq 1 ]]; then
  setup_python
  setup_frontend
  setup_registry
else
  [[ -x "$PY" ]] || die ".venv missing; run without --no-setup"
fi

if [[ $SETUP_ONLY -eq 1 ]]; then
  ok "setup complete; ./run.sh starts the service, ./run.sh --build-demo builds starter examples"
  exit 0
fi

HOST="${HOST:-$(config_value host)}"
PORT="${PORT:-$(config_value port)}"
if ! port_free "$HOST" "$PORT"; then
  who="$(ss -ltnp 2>/dev/null | grep -E "[:.]$PORT\\b" | grep -oE 'users:\(\("[^"]+",pid=[0-9]+' | head -1 | sed 's/users:(("//; s/",pid=/ pid /' || true)"
  die "port $HOST:$PORT is occupied${who:+ ($who)}; choose ./run.sh --port N"
fi

if [[ $BUILD -eq 1 ]]; then
  "$PY" -m registry doctor --no-frontend --require-blender || die "build preflight failed"
  say "building stale variants (build-all --only-stale)"
  "$PY" -m registry build-all --only-stale || die "one or more builds failed; see build/<hash>/report.json"
fi
if [[ $BUILD_DEMO -eq 1 ]]; then
  say "building the explicit starter examples"
  "$PY" -m registry build-demo || die "starter build failed; see the reported reference and build report"
fi

if [[ $DEV -eq 1 ]]; then
  say "dev: API http://$HOST:$PORT, hot reload UI http://127.0.0.1:5173"
  "$PY" -m registry serve --host "$HOST" --port "$PORT" --reload &
  BACKEND=$!
  trap 'kill "$BACKEND" 2>/dev/null; wait "$BACKEND" 2>/dev/null' EXIT INT TERM
  (cd frontend && REGISTRY_API="http://$HOST:$PORT" npm run dev)
else
  ok "Voxel Asset Registry → http://$HOST:$PORT  (Ctrl+C to stop)"
  SERVE_ARGS=(--host "$HOST" --port "$PORT")
  if [[ $RELOAD -eq 1 ]]; then
    say "reload on backend/builder code changes"
    SERVE_ARGS+=(--reload)
  fi
  exec "$PY" -m registry serve "${SERVE_ARGS[@]}"
fi
