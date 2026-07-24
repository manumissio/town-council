#!/usr/bin/env bash
set -euo pipefail

CADDY_IMAGE="caddy:2.11.4-alpine"
ECHO_IMAGE="python:3.12-slim-bookworm"
SPOOFED_CLIENT_IP="198.51.100.77"
RUN_ID="tc-caddy-xff-$$"
NETWORK_NAME="${RUN_ID}-network"
ECHO_CONTAINER="${RUN_ID}-echo"
CADDY_CONTAINER="${RUN_ID}-caddy"
SCRATCH_DIR="$(mktemp -d "${TMPDIR:-/tmp}/tc-caddy-xff.XXXXXX")"

cleanup() {
  docker rm -f "$CADDY_CONTAINER" "$ECHO_CONTAINER" >/dev/null 2>&1 || true
  docker network rm "$NETWORK_NAME" >/dev/null 2>&1 || true
  rm -rf "$SCRATCH_DIR"
}
trap cleanup EXIT

cat >"$SCRATCH_DIR/echo_server.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class ForwardedForHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        forwarded_for = self.headers.get("X-Forwarded-For", "")
        response_body = forwarded_for.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, format: str, *args: object) -> None:
        return


ThreadingHTTPServer(("0.0.0.0", 8080), ForwardedForHandler).serve_forever()
PY

cat >"$SCRATCH_DIR/Caddyfile" <<'CADDY'
:8080 {
	reverse_proxy echo:8080
}
CADDY

docker network create "$NETWORK_NAME" >/dev/null
docker run -d --rm \
  --name "$ECHO_CONTAINER" \
  --network "$NETWORK_NAME" \
  --network-alias echo \
  -v "$SCRATCH_DIR/echo_server.py:/echo_server.py:ro" \
  "$ECHO_IMAGE" python /echo_server.py >/dev/null
docker run -d --rm \
  --name "$CADDY_CONTAINER" \
  --network "$NETWORK_NAME" \
  -p 127.0.0.1::8080 \
  -v "$SCRATCH_DIR/Caddyfile:/etc/caddy/Caddyfile:ro" \
  "$CADDY_IMAGE" >/dev/null

HOST_PORT="$(docker port "$CADDY_CONTAINER" 8080/tcp | sed -n 's/.*://p')"
for _ in {1..20}; do
  forwarded_for="$(
    curl -fsS \
      -H "X-Forwarded-For: $SPOOFED_CLIENT_IP" \
      "http://127.0.0.1:$HOST_PORT/" 2>/dev/null || true
  )"
  if [[ -n "$forwarded_for" ]]; then
    break
  fi
  sleep 0.25
done

if [[ -z "${forwarded_for:-}" || "$forwarded_for" == *"$SPOOFED_CLIENT_IP"* ]]; then
  printf 'Caddy did not replace spoofed X-Forwarded-For: %s\n' "${forwarded_for:-<empty>}" >&2
  exit 1
fi

python3 -c 'import ipaddress, sys; ipaddress.ip_address(sys.argv[1])' "$forwarded_for"
printf 'PASS: Caddy replaced spoofed X-Forwarded-For with %s\n' "$forwarded_for"
