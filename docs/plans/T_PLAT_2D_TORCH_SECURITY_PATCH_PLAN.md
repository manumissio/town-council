# T-PLAT-2D: Patch the Torch Semantic Runtime

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** Dependabot alert #121 identifies the direct semantic-runtime
dependency `torch==2.11.0` as vulnerable to memory corruption through
`torch.jit.script`. GitHub's reviewed advisory marks Torch `<=2.12.1`
vulnerable and `2.13.0` patched. Town Council does not call `torch.jit`, so
current exploit reachability is not established, but keeping the vulnerable
runtime is unnecessary risk.

**b) Canonical documents consulted.**

- `AGENTS.md` requires verified dependency changes, tests first, exact
  ownership, Docker trust-boundary reporting, and no runtime-policy drift.
- `SECURITY.md` "Dependency and supply chain" requires direct dependency
  findings to remain visible and audit execution failures to block CI.
- `docs/TESTING.MD` permits filesystem, subprocess, and container boundaries
  without production test seams.
- `docs/ENGINEERING_GUARDRAILS.md` keeps audit tooling outside production
  manifests.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` serializes one owned platform
  dependency task at a time.

**c) Remediation alignment.** This is T-PLAT-2D in the platform lane. The
separately prepared Meilisearch SDK migration remains unregistered until this
urgent patch is complete and will receive the next available task ID. Exact
`files_owned`:

- `docs/plans/T_PLAT_2D_TORCH_SECURITY_PATCH_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `semantic_service/requirements.txt`
- `docker/semantic-cpu-constraints.txt`
- `tests/test_docker_build_contracts.py`

**d) Decision-gate check.** No G1-G5 gate applies. This patch does not change
model selection, semantic behavior, API contracts, gate semantics, or soak
comparability.

## 2. Design

**e) Step-by-step approach.**

1. Register T-PLAT-2D and mark merged T-IDX-1 complete.
2. Change the existing exact-pin contract first and record its failure against
   the vulnerable pins.
3. Update the audit-visible semantic pin from `torch==2.11.0` to
   `torch==2.13.0`.
4. Update the Docker CPU constraint from `torch==2.11.0+cpu` to
   `torch==2.13.0+cpu` in the same logical change.
5. Strengthen the existing test so it also proves both declarations use the
   same upstream version.
6. Build only the `python-semantic` target, which owns Torch at runtime.
7. Verify dependency consistency, CPU-only Torch, SentenceTransformers model
   encoding, finite 384-dimensional embeddings, and FAISS nearest-neighbor
   search inside the built image.
8. Run repository gates, independent pre-commit review, atomic delivery, and
   PR CI. Confirm alert #121 is fixed after merge.

No new function or module is planned. The official CPU package index and
published CPython 3.12 wheels were verified for Torch 2.13.0. The existing
`sentence-transformers==3.3.0` requirement accepts Torch `>=1.11.0` without an
upper bound; empirical image verification remains required.

**f) Reuse audit.** Reuse the semantic manifest, CPU constraint, split Docker
image, existing dependency contract test, model name, and FAISS runtime. No
wrapper, compatibility path, dependency registry, or duplicate install path is
added. The root constraints file remains unchanged because Torch's `+cpu`
selection is semantic-image-specific.

**g) Data contracts.** The semantic manifest remains the audit-visible upstream
version contract. The Docker CPU constraint remains the deployment artifact
contract. Both must declare the same upstream version after removing the local
`+cpu` suffix.

**h) Schema/migration impact.** None. No database, Alembic, timestamp, stored
embedding, API, Celery, environment, or runtime-default change.

## 3. Security & Data Governance

**i) Security-sensitive path.** No `AGENTS.md` security-sensitive file is
edited, but the dependency executes inside the semantic runtime and processes
attacker-influenceable civic text. The patch removes a vulnerable package;
ports, credentials, container users, permissions, and model policy are
unchanged. `SECURITY.md` "Dependency and supply chain" applies.

**j) Secrets.** None.

**k) Person data.** None is created, linked, aggregated, or exposed. G4 is
unaffected.

**l) Untrusted input.** No new parser or rendering boundary is introduced.
Existing extracted civic text continues through the established semantic
service boundary.

## 4. Code Health

**m) GED conformance sweep.** No production Python logic, environment read,
timestamp, handler, nesting, or parameter list changes. The two exact pins are
required package coordinates, not duplicated business constants.

**n) Antipattern scan, plan pass.** A1/H1 were corrected by checking the
reviewed advisory, the upstream fix, published Torch 2.13.0 wheels, the official
CPU index, and installed dependency contracts. B1/F1 are avoided by extending
existing manifests and one test. D1 is avoided by raising the required version
rather than suppressing the alert. D3 is accepted narrowly because exact pins
are the observable deployment contract. A2-A4, B2-B3, C1-C2, D2, E1-E3, F2,
and H2-H4 have no planned violation.

**o) Ratchet interaction.** Ruff selectors, BLE001 boundaries, Mypy scope,
coverage floor, required checks, and dependency-audit policy remain unchanged.

**p) Dead code and duplication audit.** Replace both vulnerable declarations;
no old pin survives. Expected non-document delta is one test strengthening and
two version replacements.

## 5. Testing

**q) Edge cases and failures.**

1. Updating only the semantic pin makes the CPU constraint inconsistent.
2. Updating only the CPU constraint leaves the audit-visible vulnerable pin.
3. A published wheel may import but fail during model loading or encoding.
4. The image may resolve a CUDA or non-CPU artifact unexpectedly.
5. Torch, Transformers, SentenceTransformers, NumPy, or FAISS may conflict.
6. Embeddings may have wrong dimensions, non-finite values, or fail FAISS
   normalization/search.
7. Image size or latency may move; observations must not alter gates or soak
   policy in this patch.
8. An audit or CI discrepancy may leave alert #121 open after merge.

**r) Tests and mapping.**

| Verification | Scenarios |
|---|---|
| Exact semantic/CPU pin contract | 1, 2 |
| `pip check` and import smoke in `python-semantic` | 4, 5 |
| Model encode and FAISS search smoke | 3, 6 |
| Existing Docker contract suite | 1, 2, 5 |
| Complete coverage-gated Python suite | Regression coverage |
| Post-merge Dependabot readback | 8 |

Scenario 7 is recorded observationally from the Docker build and smoke; no
threshold test is added.

**s) Fakes and mocks.** None. Tests use the approved filesystem, subprocess,
and container boundaries. No application symbol or facade is patched.

**t) Verification rows.** Apply Docker dependency contracts, docs-only, and
broad cross-cutting verification. Run Ruff, Mypy, Docker contracts, semantic
tests, health-probe tests, docs links, the coverage-gated suite, and the real
semantic image smoke.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_docker_build_contracts.py::test_semantic_cpu_constraint_uses_patched_matching_upstream_version

./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_docker_build_contracts.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_semantic_*.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_role_worker_healthchecks.py tests/test_worker_health_probes.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q --cov \
  --cov-config=.coveragerc --cov-report=term-missing:skip-covered tests/
git diff --check

docker build --target python-semantic -t town-council-torch-2.13.0 .
docker run --rm --entrypoint python town-council-torch-2.13.0 -c \
  "import torch; assert torch.__version__ == '2.13.0+cpu'; assert torch.version.cuda is None"
docker run --rm --entrypoint pip town-council-torch-2.13.0 check
```

The runtime smoke downloads the public `all-MiniLM-L6-v2` model into the
ephemeral container, encodes two strings, verifies finite 384-dimensional
vectors, normalizes them with FAISS, and completes one nearest-neighbor search.
Model download or inference errors fail the command immediately:

```bash
docker run --rm -i --entrypoint python town-council-torch-2.13.0 - <<'PY'
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = np.asarray(
    model.encode(["city council agenda", "approved meeting minutes"]),
    dtype="float32",
)
assert embeddings.shape == (2, 384)
assert np.isfinite(embeddings).all()
faiss.normalize_L2(embeddings)
index = faiss.IndexFlatIP(embeddings.shape[1])
index.add(embeddings)
distances, neighbors = index.search(embeddings[:1], 1)
assert distances.shape == (1, 1)
assert neighbors.tolist() == [[0]]
PY
```

The API and worker entrypoints run against isolated PostgreSQL and Redis. The
trap removes all smoke containers and the network on success or failure:

```bash
set -euo pipefail
SMOKE_NETWORK=tc-torch-smoke
SMOKE_POSTGRES=tc-torch-postgres
SMOKE_REDIS=tc-torch-redis
SMOKE_SEMANTIC=tc-torch-semantic
cleanup() {
  docker rm -f "$SMOKE_SEMANTIC" "$SMOKE_POSTGRES" "$SMOKE_REDIS" \
    >/dev/null 2>&1 || true
  docker network rm "$SMOKE_NETWORK" >/dev/null 2>&1 || true
}
wait_for_container() {
  local container_name=$1
  shift
  for _attempt in $(seq 1 60); do
    if docker exec "$container_name" "$@" >/dev/null 2>&1; then
      return 0
    fi
    if ! docker inspect -f '{{.State.Running}}' "$container_name" \
      2>/dev/null | grep -qx true; then
      docker logs "$container_name"
      return 1
    fi
    sleep 1
  done
  docker logs "$container_name"
  return 1
}
trap cleanup EXIT
cleanup
docker network create "$SMOKE_NETWORK"
docker run -d --name "$SMOKE_POSTGRES" --network "$SMOKE_NETWORK" \
  -e POSTGRES_USER=town_council -e POSTGRES_PASSWORD=smoke_password \
  -e POSTGRES_DB=town_council_db postgres:15-alpine
docker run -d --name "$SMOKE_REDIS" --network "$SMOKE_NETWORK" \
  redis:7-alpine redis-server --requirepass smoke_password
wait_for_container "$SMOKE_POSTGRES" pg_isready -U town_council
wait_for_container "$SMOKE_REDIS" sh -c \
  'redis-cli -a smoke_password ping | grep -qx PONG'
docker run -d --name "$SMOKE_SEMANTIC" --network "$SMOKE_NETWORK" \
  -e DATABASE_URL=postgresql://town_council:smoke_password@tc-torch-postgres:5432/town_council_db \
  -e MEILI_HOST=http://127.0.0.1:7700 \
  --entrypoint python town-council-torch-2.13.0 \
  -m uvicorn semantic_service.main:app --host 0.0.0.0 --port 8010
wait_for_container "$SMOKE_SEMANTIC" python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=5)"
docker run --rm --network "$SMOKE_NETWORK" \
  -e DATABASE_URL=postgresql://town_council:smoke_password@tc-torch-postgres:5432/town_council_db \
  -e CELERY_BROKER_URL=redis://:smoke_password@tc-torch-redis:6379/0 \
  -e CELERY_RESULT_BACKEND=redis://:smoke_password@tc-torch-redis:6379/0 \
  -e SEMANTIC_INDEX_DIR=/tmp/semantic \
  --entrypoint python town-council-torch-2.13.0 \
  scripts/semantic_worker_healthcheck.py
```

**v) Rollback.** Revert both pin changes together, rebuild `python-semantic`,
and rerun the same dependency, image, and repository checks. No migration,
reindex, data repair, or external-state cleanup is required. Rollback knowingly
restores Dependabot alert #121.

**w) Docs synchronization.** Update only this implementation plan and the
remediation ledger. `SECURITY.md`, README, ADR, operations, performance,
testing, architecture, API contracts, and data-governance docs remain accurate.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject one-sided pin changes, a new constraint
registry, Dockerfile churn, alert suppression, runtime-policy drift, unrelated
dependency upgrades, compatibility code, test weakening, or edits outside the
five owned files.

**y) Evidence.** Report the tests-first failure; exact local gate outcomes;
Docker build, package, model, and FAISS smoke outcomes; pre-commit review;
commit hashes; PR URL; unresolved P1/P2 count; CI state; and post-merge alert
state. Anything unrun is `NOT VERIFIED`.

**z) Deviations.** Expected result is none. Any additional file, dependency,
model, Dockerfile, workflow, API, schema, runtime-default, or soak-policy change
is a blocker.
