# Runtime Profiles

These files are explicit opt-in runtime profiles. They do not change repository defaults.

`profile_manifest.csv` is the active profile inventory:
- `preferred`: recommended opt-in path for the current host class.
- `baseline`: reproducible local baseline.
- `diagnostic`: experiment or troubleshooting profile.
- `historical`: retired profile kept under `archive/`.

## Preferred M5 MLX

- `m5_mlx_conservative.env`: first M5 Pro 64GB profile for host MLX-LM. Use this before higher-throughput tests.
- `m5_mlx_balanced.env`: higher-throughput M5 Pro 64GB profile. Use after the conservative profile has stable evidence.

Start MLX-LM on the Mac host before using either profile:

```bash
# terminal 1
mlx_lm.server --model mlx-community/gemma-3-text-4b-it-4bit --host 127.0.0.1 --port 8080

# terminal 2
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build \
  postgres redis meilisearch tika semantic semantic-worker
docker compose --env-file .env --env-file env/profiles/m5_mlx_conservative.env \
  -f docker-compose.yml -f docker-compose.dev.yml up -d --build --no-deps \
  worker api pipeline frontend
docker compose exec -T worker python scripts/worker_healthcheck.py
```

The Docker app reaches that server through `http://host.docker.internal:8080`.

## Legacy Docker/Ollama Baseline

- `m5_conservative.env`: current M5 baseline using Docker-hosted Ollama and `gemma-3-270m-custom`.
- `desktop_balanced.env`: higher-throughput Docker/Ollama profile for diagnostic runs.

## Historical M1 Baseline

- Retired M1 profiles live under `archive/env/profiles/`.

## Diagnostic Gemma Experiments

- `gemma4_e2b_second_tier.env`: Docker/Ollama Gemma 4 diagnostic profile.

Retired host-Ollama experiment profiles and helpers live under `archive/`.
