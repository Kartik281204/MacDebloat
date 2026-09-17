#!/usr/bin/env bash
#
# Convenience launcher for the deblaot backend.
# Creates a local virtualenv on first run, then starts the API.
#
# By default this binds to 127.0.0.1 only -- reachable from this Mac alone
# (the desktop GUI, curl, /docs). To also use the mobile UI from an iPhone
# on the same Wi-Fi, bind to your LAN instead:
#
#   DEBLAOT_HOST=0.0.0.0 ./run.sh
#
# The first time you do that, a random access token is generated and
# printed below (and reused from .deblaot_token on later runs). Anything
# that isn't this Mac must send it as `Authorization: Bearer <token>` --
# the mobile UI asks for it the first time you open it. Requests from this
# Mac itself never need it, whichever way you bind.
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
./.venv/bin/pip install -q -r requirements.txt

HOST="${DEBLAOT_HOST:-127.0.0.1}"
PORT="${DEBLAOT_PORT:-8765}"
TOKEN_FILE=".deblaot_token"

case "$HOST" in
  127.0.0.1|localhost|::1)
    ;;
  *)
    if [ -z "${DEBLAOT_TOKEN:-}" ]; then
      if [ -f "$TOKEN_FILE" ]; then
        DEBLAOT_TOKEN="$(cat "$TOKEN_FILE")"
      else
        DEBLAOT_TOKEN="$(./.venv/bin/python3 -c 'import secrets; print(secrets.token_urlsafe(9))')"
        echo "$DEBLAOT_TOKEN" > "$TOKEN_FILE"
        chmod 600 "$TOKEN_FILE"
      fi
    fi
    export DEBLAOT_TOKEN
    echo "Binding to $HOST -- reachable from other devices on this network."
    echo "Access token (enter this in the mobile UI): $DEBLAOT_TOKEN"
    echo "(saved to $TOKEN_FILE -- delete that file to force a new one next run)"
    ;;
esac

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"

echo "Starting deblaot on http://$HOST:$PORT"
echo "  - From this Mac:        http://127.0.0.1:$PORT/  (docs at /docs)"
if [ "$HOST" != "127.0.0.1" ] && [ "$HOST" != "localhost" ] && [ "$HOST" != "::1" ]; then
  if [ -n "$LAN_IP" ]; then
    echo "  - From your iPhone:      http://$LAN_IP:$PORT/  (same Wi-Fi network)"
  else
    echo "  - From your iPhone:      http://$HOST:$PORT/  (check System Settings > Wi-Fi for this Mac's IP if that doesn't work)"
  fi
fi

exec ./.venv/bin/uvicorn app.main:app --host "$HOST" --port "$PORT"
