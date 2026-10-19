# Agenda fallback: boundary fixes and remaining gaps

Date: 2026-10-18. Scope: the same 24 Sunnyvale and Mountain View documents
used in the Jev experiment. This measures the deterministic text fallback,
not Jev, the complete resolver, or a promotion baseline.

## Result

The fixes reduce noise and recover business, but the fallback still produces
too many false items to present as a dependable account of a meeting.

| Measure | Original | After fixes |
| --- | ---: | ---: |
| Candidates | 241 | 225 |
| False items: source noise or fragments | 203 | 167 |
| Uncertain items, counted separately | 14 | 8 |
| Missed business units, out of 96 | 78 | 48 |
| Previously covered units lost | — | 0 |
| Median extraction time per document, fresh replay | 3.6 ms | 4.6 ms |
| Model/API calls and inference cost | 0 / $0 | 0 / $0 |

Mountain View coverage rises from 4 to 25 of 31 reference units; Sunnyvale
rises from 14 to 23 of 65. Candidate counts are not distinct-business counts.
The four cancellation notices still produce noise: 29 candidates versus 27
before, including two newly visible city mastheads. This remains unresolved.

## What changed

- Item discovery and title wrapping share item boundaries. Decimal and
  lettered items no longer disappear behind section headings.
- Explicit record IDs are attached only to the immediately preceding source
  paragraph and distinguish formal business from names and addresses. Internal
  title line breaks are normalized; separate paragraphs are never joined.
  Recognized titles printed before item numbers are normalized locally,
  without changing stored source text.
- Record-backed content before the first numbered item remains eligible.
  Parent context distinguishes recommendation children from sibling items.
- Descriptions retain bounded source text. Cancellation text inside an
  attachment does not suppress business elsewhere in a live document.
- Tika requests XHTML, preserving real pages, paragraphs, and decoded text.
  The sample uses its original stored text; no PDF was re-extracted for scoring.

Model configuration, item limits, existing acceptance thresholds, and soak
policy are unchanged. No live backfill or database rewrite was performed.

## Evidence and limits

The [compressed evidence bundle](../../experiments/results/agenda_boundary_2026_10_18.json.gz)
contains the unchanged source documents, original candidates and sealed
reference, revised candidates, both independent blind AI reviews, final labels,
configuration, source hashes, and timing metadata. It is evidence, not a new
runtime component or CI gate.

Original file hashes were recovered and checked before replay. The original
environment record is only partially recovered; both timing sets above were
measured freshly, with one warmup and three measured runs per document. These
small timings are observational, not a performance gate. Inference cost excludes
AI-review compute and machine operating costs.

Unchanged evidence retains its sealed original label or its earlier independent
blind judgments. Three new passages received two further blind reviews, which
agree. The bundle records this review chain. Text, page, result, document, and
reference must match before a judgment is reused; row order is not part of this
semantic-correctness metric.

Review rejected cross-paragraph joining and document-wide cancellation
classification. The flattened text does not reliably identify paragraph
continuations or the primary meeting. Those heuristics were removed rather
than extended with more guesses; the final figures above replace the earlier,
more optimistic interim figures.

The 96-unit reference is AI-reviewed, not human gold. It includes substantive
public-comment and presentation topics as well as formal agenda business.
The fixes do not resolve blank-line fragments, cancellation classification,
all minutes coverage, generic paragraph noise, or source reading-order problems.
Structured Legistar/HTML paths and live UI
behavior were not evaluated here. Do not infer complete meeting coverage.

## Replay the recorded candidates

Run from the repository root. This checks current extraction against the
recorded outputs; it does not independently prove the AI judgments correct.

```bash
PYTHONPATH=. .venv/bin/python - <<'PY'
import gzip, json, logging
from pathlib import Path
from pipeline import config
from pipeline.agenda_extraction_fallback import run_agenda_extraction_pipeline

evidence = json.loads(gzip.decompress(Path("experiments/results/agenda_boundary_2026_10_18.json.gz").read_bytes()))
for name, expected in evidence["current"]["config"].items():
    assert getattr(config, name) == expected, name
for document in evidence["documents"]:
    actual = run_agenda_extraction_pipeline(text=document["content"], raw_provider_content=None,
        mode="balanced", logger=logging.getLogger("replay"))
    expected = [row["candidate"] for row in evidence["current"]["candidates"]
                if row["catalog_id"] == document["catalog_id"]]
    assert actual == expected, document["catalog_id"]
labels = evidence["final_labels"]
covered = {unit for label in labels for unit in label["covered_unit_ids"]}
units = {unit["unit_id"] for document in evidence["original_reference"]["reference"]["documents"]
         for unit in document["business_units"]}
assert sum(label["label"] == "noise" for label in labels) == 167
assert len(units - covered) == 48
print("PASS: 24-document replay; 167 false items; 48 missed reference units")
PY
```
