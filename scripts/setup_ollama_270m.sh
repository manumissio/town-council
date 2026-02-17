#!/usr/bin/env bash
set -euo pipefail

MODEL_NAME="${MODEL_NAME:-gemma-3-270m-custom}"
GGUF_PATH="${1:-/models/gemma-3-270m-it-Q4_K_M.gguf}"

# Why this helper exists: the A/B plan requires both arms to use HTTP inference
# to avoid backend confounds (inprocess vs http).

if ! docker compose ps inference >/dev/null 2>&1; then
  echo "inference service is not available; start it first"
  exit 2
fi

TMP_GGUF="/tmp/${MODEL_NAME}.gguf"
TMP_FILE="/tmp/${MODEL_NAME}.Modelfile"

if [[ -f "$GGUF_PATH" ]]; then
  docker compose cp "$GGUF_PATH" inference:"$TMP_GGUF"
else
  echo "GGUF not found on host path: $GGUF_PATH"
  echo "Trying in-container path directly..."
  TMP_GGUF="$GGUF_PATH"
fi

docker compose exec -T inference sh -lc "cat > '$TMP_FILE' <<EOF
FROM $TMP_GGUF
PARAMETER temperature 0.1
EOF
ollama create '$MODEL_NAME' -f '$TMP_FILE'"

docker compose exec -T inference ollama show "$MODEL_NAME" >/dev/null

echo "created model: $MODEL_NAME"
