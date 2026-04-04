# Gemma 4 Host-Metal Strict Swap v1 Writeup

Date: 2026-04-04

## Scope

This was a strict backend-swap experiment.

- The Docker app stack stayed in place.
- Docker `inference` was stopped for the full run.
- Host-native Ollama served both the control and treatment models from `http://localhost:11434`.
- The Docker app stack pointed to `http://host.docker.internal:11434`.
- The smoke set, prompts, worker settings, and timeout budgets stayed fixed.

This was not a baseline-valid promotion run. It was a diagnostic experiment to answer whether the Docker CPU-only backend was the main bottleneck.

## Outcome

Result: promising enough to continue, but not yet ready for a broad opt-in recommendation.

- The strict backend swap removed the dominant runtime bottleneck.
- `gemma4:e2b` completed all segment and summarize tasks without timeout-driven failures.
- Treatment latency improved dramatically relative to the earlier Docker CPU-only second-tier run.
- One important quality caveat remains: treatment segmentation for `cid=933` produced only `2` items where the control found `12`.

Decision for this pass: iterate.

- Proceed to the next investigation step only if we explicitly validate the `cid=933` segmentation quality drift.
- Do not change the default runtime policy.

## Provenance

Evidence that the backend swap was clean:

- Experiment directory:
  - `experiments/results/gemma4_host_metal_strict_swap_v1_20260404_015722`
- Control snapshot:
  - `experiments/results/gemma4_host_metal_strict_swap_v1_20260404_015722/control_snapshot.json`
- Treatment snapshot:
  - `experiments/results/gemma4_host_metal_strict_swap_v1_20260404_015722/treatment_snapshot.json`

Key provenance facts:

- Docker `inference` was stopped and remained stopped.
- Host Ollama version was `0.20.0`.
- `host_ollama_ps` showed both models running on `100% GPU`.
- Worker env snapshots showed `LOCAL_AI_HTTP_BASE_URL=http://host.docker.internal:11434`.

## Evidence

### Control vs prior Docker control

Control run artifact:

- `experiments/results/gemma4_host_metal_strict_swap_v1_control_20260404_015727/tasks.jsonl`

Most important deltas:

- `cid=3`
  - segment: `301.255s` -> `166.684s`
  - summarize: `145.502s` -> `2.212s`
- `cid=609`
  - segment: `20.903s` -> `4.351s`
  - summarize: `4.290s` -> `2.232s`
- `cid=933`
  - segment: `52.047s` -> `10.550s`
  - summarize: `8.448s` -> `2.218s`

The usual non-gating extract warnings remained:

- `cid=933` extract failed
- `cid=996` extract failed

Those are consistent with prior runs and are non-gating under repo policy.

### Treatment vs prior Docker Gemma 4 second-tier

Treatment run artifact:

- `experiments/results/gemma4_host_metal_strict_swap_v1_treatment_20260404_020105/tasks.jsonl`

Per-catalog timings:

- `cid=3`
  - segment: `238.757s` -> `37.402s`
  - summarize: `60.379s` -> `6.352s`
- `cid=609`
  - segment: `184.868s` -> `10.448s`
  - summarize: `64.485s` -> `6.314s`
- `cid=933`
  - segment: `234.650s` -> `12.539s`
  - summarize: `87.320s` -> `6.296s`
- `cid=996`
  - segment: `2.206s` -> `2.148s`
  - summarize: `60.342s` -> `6.325s`

Median treatment deltas versus prior Docker Gemma 4 second-tier:

- segment median: about `209.759s` -> `11.494s`
  - about `94.5%` lower
- summarize median: about `62.432s` -> `6.319s`
  - about `89.9%` lower

Most importantly:

- no segment timeout outcomes
- no summarize timeout outcomes
- no summarize task failures
- no empty-response deterministic fallback events

## Quality Caveat

The strict swap solved the runtime problem, but it also surfaced a likely quality regression on one document.

For `cid=933`:

- host-Metal control segmentation found `12` agenda items
- host-Metal treatment segmentation found `2` agenda items

This is the strongest reason not to overclaim success yet.

The backend swap appears to have removed the main performance bottleneck, but the treatment still needs targeted quality review before we treat the result as a clean opt-in win.

## Strongest Alternative Explanation

The strongest alternative explanation is not backend provenance anymore. That part was controlled successfully.

The strongest remaining alternative explanation is model behavior on this document:

- `gemma4:e2b` may decode or truncate differently on `cid=933`
- the large runtime win may come with a segmentation-shape regression on some agendas

That explanation is not yet ruled out.

## Decision

Decision: iterate.

What we learned:

- Docker CPU-only inference was the main runtime bottleneck.
- Host-native Metal is a materially better execution path for this repo on this machine.
- `gemma4:e2b` is now viable enough to evaluate further on host-native Metal.

What should happen next:

1. Run a targeted quality review for `cid=933` and any similar heavy agenda documents.
2. If that review looks acceptable, proceed to the broader practical-tuning step on host-native Metal.
3. If the quality regression is confirmed, stop the Gemma 4 opt-in track until the prompt or segmentation contract changes.
