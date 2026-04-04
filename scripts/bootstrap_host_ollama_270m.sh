#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PROFILE_PATH="${PROFILE_PATH:-env/profiles/gemma3_270m_host_metal_conservative.env}"
MODEL_NAME="${MODEL_NAME:-gemma-3-270m-custom}"
HOST_OLLAMA_BASE_URL="${HOST_OLLAMA_BASE_URL:-http://localhost:11434}"
GGUF_CACHE_DIR="${GGUF_CACHE_DIR:-$PWD/tmp/host_ollama_models}"
GGUF_FILENAME="${GGUF_FILENAME:-gemma-3-270m-it-Q4_K_M.gguf}"
GGUF_PATH="${GGUF_PATH:-$GGUF_CACHE_DIR/$GGUF_FILENAME}"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "[bootstrap_host_ollama_270m] This helper supports Apple Silicon macOS only." >&2
  exit 2
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "[bootstrap_host_ollama_270m] Host ollama is not installed." >&2
  echo "Install Ollama first, then retry." >&2
  exit 2
fi

if [[ -f "$PROFILE_PATH" ]]; then
  # Load host override defaults from the supported profile, but let env win.
  # Why: the helper should bootstrap the same endpoint the opt-in profile uses.
  # shellcheck disable=SC1090
  source "$PROFILE_PATH"
fi

if ! curl -fsS "${HOST_OLLAMA_BASE_URL%/}/api/tags" >/dev/null; then
  echo "[bootstrap_host_ollama_270m] Host Ollama is unreachable at $HOST_OLLAMA_BASE_URL." >&2
  echo "Start it first, for example: ollama serve" >&2
  exit 2
fi

if OLLAMA_HOST="${HOST_OLLAMA_BASE_URL#http://}" ollama show "$MODEL_NAME" >/dev/null 2>&1; then
  echo "[bootstrap_host_ollama_270m] Host alias already exists: $MODEL_NAME"
  exit 0
fi

mkdir -p "$GGUF_CACHE_DIR"

if [[ ! -f "$GGUF_PATH" ]]; then
  echo "[bootstrap_host_ollama_270m] Downloading GGUF into $GGUF_CACHE_DIR ..."
  docker compose up -d semantic >/dev/null
  docker compose run --rm semantic python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='unsloth/gemma-3-270m-it-GGUF', filename='$GGUF_FILENAME', local_dir='/app/tmp/host_ollama_models')"
fi

if [[ ! -f "$GGUF_PATH" ]]; then
  echo "[bootstrap_host_ollama_270m] GGUF bootstrap failed: missing $GGUF_PATH" >&2
  exit 2
fi

MODELF_PATH="$GGUF_CACHE_DIR/${MODEL_NAME}.Modelfile"
cat > "$MODELF_PATH" <<EOF
FROM $GGUF_PATH
PARAMETER temperature 0.1
EOF

echo "[bootstrap_host_ollama_270m] Creating host alias $MODEL_NAME ..."
OLLAMA_HOST="${HOST_OLLAMA_BASE_URL#http://}" ollama create "$MODEL_NAME" -f "$MODELF_PATH"
OLLAMA_HOST="${HOST_OLLAMA_BASE_URL#http://}" ollama show "$MODEL_NAME" >/dev/null

echo "[bootstrap_host_ollama_270m] OK"
