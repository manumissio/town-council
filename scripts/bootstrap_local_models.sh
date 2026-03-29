#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[bootstrap_models] Starting core inference services..."
docker compose up -d inference semantic >/dev/null

echo "[bootstrap_models] Caching sentence-transformer model in shared volume..."
docker compose run --rm semantic python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

echo "[bootstrap_models] Downloading Gemma GGUF into shared volume..."
docker compose run --rm semantic python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='unsloth/gemma-3-270m-it-GGUF', filename='gemma-3-270m-it-Q4_K_M.gguf', local_dir='/models')"

echo "[bootstrap_models] Registering local Ollama model alias..."
bash ./scripts/setup_ollama_270m.sh /models/gemma-3-270m-it-Q4_K_M.gguf

echo "[bootstrap_models] Verifying Ollama model is available..."
docker compose exec -T inference ollama show "${LOCAL_AI_HTTP_MODEL:-gemma-3-270m-custom}" >/dev/null

echo "[bootstrap_models] OK"
