---
date: 2026-10-27
artifact_type: consolidated-postmortem
pr_scope: "327, 328"
analyzed_commit: 3240a336706b936e77f73a6866fd2f12ac020322
commit_scope: current-master checks; historical behavior pinned separately below
tags: [agenda-extraction, cancellation, source-evidence, persistence, review]
---

# Postmortem: Agenda content needs evidence, not just successful processing

## In Brief

[PR #327](https://github.com/manumissio/town-council/pull/327) recovered missed
business from document text. [PR #328](https://github.com/manumissio/town-council/pull/328)
removed notice fragments, corrected misleading labels and links, and made empty
results safer to store. Both merged, but neither established dependable agenda
quality across complete meetings.

**The central failure was letting weak evidence support stronger decisions.**
A heading became an item, a period ended a title, cancellation text implied an
empty meeting, and a successful attempt implied reliable provenance. Tests and
browser checks often confirmed that components agreed, not that the source
document supported what the user saw.

There was also a delivery failure: two P2 findings arrived after #327's
all-addressed comment but before its merge. Both mechanisms still reproduce at
the reviewed master commit. They are follow-up defects, not completed fixes.

This report covers the two PRs and their recorded local experiments. It does
not establish a production outage, affected-user count, or production data
loss. It changes no application code, live records, model settings, item limits,
or acceptance floors.

## What Users Could Get Wrong

| Visible result | Why it mattered |
| --- | --- |
| City names, contact lines, and cancellation notices presented as agenda items | Readers could mistake administrative text for meeting business. |
| Missing, truncated, or joined titles | Readers could miss a decision or see a description presented as its title. |
| Structured items from another meeting | Plausible business could be attributed to the wrong governing body. |
| An AI label inferred from completed processing | Readers were told a generation method that the stored record did not establish. |
| A page link derived from unverified page metadata | The interface implied a more precise source location than the evidence supported. |
| Zero reported items despite retained rows | A failed new attempt could hide the existence of earlier stored business. |

The most concrete example was catalog 6961: a Zoning Administrator cancellation
notice had nine rows describing Arts Commission business, including four matter
links. Their removal required explicit operator approval. The cancellation
source was evidence against those rows; their presence in the database was not
evidence for them. See the [controlled-correction record](../reviews/2026-10-19-agenda-notice-cleanup.md).

## What Improved, And What Those Numbers Mean

These are recorded results from the same frozen Sunnyvale and Mountain View
sample: **24 documents and 96 reference units**. The reference was AI-reviewed,
not human gold. It includes substantive public-comment and presentation topics
as well as formal business. Candidate rows are not distinct business units.

| Frozen text fallback | Candidates | False items: noise/fragments | Uncertain | Missed reference units |
| --- | ---: | ---: | ---: | ---: |
| Before #327 | 241 | 203 | 14 | 78 |
| Final #327 | 231 | 173 | 8 | 48 |
| Initial #328 cleanup | 220 | 162 | 8 | 48 |
| Final #328 cancellation correction | 199 | 141 | 8 | 48 |

No previously covered reference units were lost in the recorded comparisons.
However, #328 demonstrated no further reduction in missed business, and its
final fallback still contained 141 false items. Fewer rows was an improvement,
not proof that the remaining list was dependable.

The final recorded fallback medians were 4.5 ms per document for #327 and
4.4 ms for #328. Those diagnostic replays made no model calls and had no
inference API charge; this excludes reviewer compute and machine costs. These
are **not** full-resolver latency or cost measurements.

The controlled local resolver/backfill used a different path and denominator.
Its cancellation correction reduced stored rows from 251 to 228. Catalogs
6530, 6961, 8733, and 8769 then had zero rows; 82 matter associations on
unaffected records survived. The four wrong links on 6961 were deliberately
removed. Do not subtract these database totals from the fallback table or call
them independently labeled full-resolver accuracy scores.

Sources: [#327 report](../reviews/2026-10-18-agenda-fallback-comparison.md),
[#328 report](../reviews/2026-10-19-agenda-notice-cleanup.md), and their linked
[boundary](../../experiments/results/agenda_boundary_2026_10_18.json.gz) and
[notice](../../experiments/results/agenda_notice_2026_10_19.json.gz) bundles.
The postmortem audit recomputed the final candidate/label/miss totals from the
bundles; it did not repeat inference, the live backfill, or browser runs.

## How The Work Unfolded

Times below are UTC. Commit links pin the historical implementation, not the
later default branch.

| When | Turning point |
| --- | --- |
| October 19, #327 review | Decimal and lettered boundaries, wrapped titles, record IDs, and XHTML structure received fixes. Review also rejected cross-paragraph joining and whole-document cancellation guessing. |
| October 19, 03:34 | An [all-addressed comment](https://github.com/manumissio/town-council/pull/327#issuecomment-6259077623) reported review completion. |
| October 19, 03:39 | Final-head review raised [description absorption](https://github.com/manumissio/town-council/pull/327#discussion_r4310122573) and [abbreviation truncation](https://github.com/manumissio/town-council/pull/327#discussion_r4310122577). No later #327 correction commit followed. |
| October 19, 03:43 | #327 merged as [`1383f41`](https://github.com/manumissio/town-council/commit/1383f41c446a17f33c3d765a89f57f0acd31e3e8), with those two title-boundary mechanisms still present. |
| October 19-20, #328 initial work | Notice filtering, neutral provenance, and original-source links improved presentation. Initial browser checks matched rendered titles to stored rows but still accepted cancellation fragments. |
| October 20, cancellation correction | Reading source Full Text alongside the agenda changed acceptance: confirmed cancellation-only notices must yield zero items. Early detection and empty-capable writers followed. |
| October 20-21, repeated review | Blank attachments, incomplete page markers, destructive empty replacement, batch interruption, declared page totals, spelling, and stale API counts exposed the rest of the write/read contract. |
| October 21, 01:44 | #328 merged as [`ef52320`](https://github.com/manumissio/town-council/commit/ef523207e1a25079ce22a05251e94ca498e2f776), after the final count correction. |

## Why The Bugs Kept Appearing

### 1. Text Structure Was Treated As Meaning

Numbered headings could displace paragraph fallback; decimal and lettered
business could disappear. Title discovery, record-ID anchoring, and wrapping
used different boundaries. Flattened extraction also lost distinctions among
paragraphs, lists, cells, and pages.

#327 aligned more of those boundaries and preserved XHTML structure. It also
deleted an unbounded backward join and a broad cancellation shortcut. Those
trials guessed relationships that the source representation could not prove.
Keeping uppercase business exposed additional generic headings; those were
counted as noise instead of silently discarded to improve the score.

The remaining P2s demonstrate the same reasoning gap at a smaller boundary:
an anchored title can cross a blank paragraph into its description, while a
title ending in `U.S.` can lose its continuation. Punctuation and a later
recommendation field are not reliable substitutes for source boundaries.

### 2. A Local Filter Had A Wider Effect Than Expected

Adding notice headings to shared procedural signals changed which parser
handled an entire page. A page containing notices and real numbered business
could switch parsers and lose a long business title. Removing noise locally
had accidentally changed discovery globally.

#328 restored the shared selection signals and applied the new exclusions at
candidate acceptance and the Legistar filter. Its
`test_notice_cleanup_preserves_long_numbered_business` regression checks both
sides of the requirement: remove the notice and retain the neighboring item.

**Lesson:** inspect every consumer of a shared heuristic before extending it.
Test the intended exclusion beside genuine business, not in an empty fixture.

### 3. Empty Output Had No Single Safe Write Meaning

Initially, writers could mark an empty attempt without clearing old rows.
Making every empty proposal a replacement fixed that inconsistency but created
a worse risk: failed or inconclusive extraction could erase valid stored rows.

#328 ultimately separated the cases. Confirmed cancellation can clear rows;
an empty or blank-title proposal with existing business must preserve the rows
and hash. The attempt may still fail and retry. A new catalog without stored
items can record an empty result. The low-level persistence function remains
an explicit replacement operation, not a classifier.

That decision required more than changing the writer. The new rejection error
also needed the existing per-record rollback/failure path so a rejected catalog
would not stop the normal or maintenance backfill. Finally, readers needed to
count stored rows rather than reuse a failed attempt's zero count.

See the [preservation finding](https://github.com/manumissio/town-council/pull/328#discussion_r4320167089),
[batch finding](https://github.com/manumissio/town-council/pull/328#discussion_r4331461856),
and [count finding](https://github.com/manumissio/town-council/pull/328#discussion_r4332081186).
**Lesson:** specify the classifier, write, error boundary, next-record outcome,
and API read together before changing empty-result behavior.

### 4. Cancellation Evidence Was Checked Too Late And Too Narrowly

Cancellation-only recognition needed to precede structured-source selection;
otherwise unrelated structured rows could override the notice. But putting it
first also made false confirmation dangerous: it could suppress genuine
business and authorize deletion.

Review found that the detector saw a cleaned representation rather than all
the source evidence. Blank attachment pages disappeared before counting. A
lone `Page 2` looked like one page. `Page 1 of 2` did not match the earlier
marker parser. These were successive cases of one missing invariant:
**one visible text chunk does not establish a complete single-page notice.**

#328 counted raw boundaries, rejected recognized non-first pages, and checked
declared totals separately. Mixed packets and live business remain negative
cases. Unsupported pagination and unmarked partial sources remain limits;
the detector does not prove completeness for every possible document.

### 5. Presentation Promised More Than The Record Established

A completed attempt was used to infer an AI method. Page metadata was used to
construct precise-looking source links. Attempt metadata was used as current
item count. Each shortcut replaced a different fact with a convenient proxy.

#328 used neutral `catalog_agenda_items` provenance, retained original source
URLs, removed guessed page anchors, and reused the database count query.
It withheld unsupported claims rather than adding another inference layer.
**Lesson:** task status, stored content, extraction method, and verified source
location are different facts. Keep them separate in both API and interface.

## Why Verification Did Not Catch Everything

| Evidence that passed | What it established | What it did not establish |
| --- | --- | --- |
| Focused parsing tests and frozen replay | Specific boundaries worked; labeled fallback output improved | Every candidate was useful, or the reference covered all real business |
| Initial browser/API parity | The interface displayed the stored titles consistently | Those titles belonged to that meeting or described any business |
| Helper and source-expression tests | A helper or implementation expression matched expectations | The public resolver and rendered interaction honored the user contract |
| Empty-result and page-count checks | The cases encoded by those tests worked | Unknown empty output was safe to delete, or visible text was a complete packet |
| Full suite and review receipts | Checked behavior passed at a particular revision | Later findings were absent, or all semantic cases were covered |

The underlying process problem was acceptance ordering. A sequence of local
repairs was reviewed before one connected contract covered source identity,
content, replacement safety, batch continuation, and display. More tests caught
real defects, but their number was not the missing acceptance criterion.

The late #327 findings also show why an earlier all-clear cannot authorize a
later merge. Review completion must refer to the final head and include the
findings that arrived afterward. A disputed numeric-recommendation finding was
separately adjudicated; it should not be counted as another implemented fix.

## What Worked And Should Be Reused

- Freeze the same source documents and reference units. Carry judgments only
  when candidate identity matches, and independently label newly exposed text.
- Report unfavorable results. Withdrawn guesses made interim scores worse;
  the final report kept those less flattering numbers and explicit limits.
- Read actual source content in Playwright. The corrected inspection required
  zero cards on the four real notices, not merely agreement with the API.
- Test public paths and persisted effects. Replacement tests cover the task
  family, real Celery wrapper, worker, maintenance, and later batch records.
- Make live corrections separately controlled. The recorded backfill used a
  snapshot, dependency checks, scoped writes, and preservation checks. The
  prepared rollback was not executed and must not be described as verified.

## Actionable Follow-Ups

These are recommendations, not newly approved implementation tasks, owner
assignments, or deadlines.

| When | Next action | Evidence required to close it |
| --- | --- | --- |
| First | Address the two late #327 title-boundary P2s together. Write failing public-extraction cases for anchored paragraph breaks and abbreviation continuations before the simplest shared-boundary repair. | Both source-backed titles are exact; descriptions stay descriptions; neighboring items and existing budget tests pass. No model, limit, or floor change. |
| Next | Use a small source-grounded acceptance checklist for the complete resolver, not just fallback. Include canceled meetings, mixed packets, real business beside notices, and meeting identity. | Expected-versus-actual content, false items, missed business, uncertainty, and source locations are reported separately; another reviewer checks the source. Reuse the existing sample before proposing new tooling. |
| On replacement changes | Reuse the connected regression cases instead of adding another empty-state framework. | Confirmed empty clears; inconclusive empty preserves rows/hash; failed attempt remains visible; later records run; API count equals stored rows. |
| Before restoring precise page or method claims | Require evidence for the claimed physical page and actual producer. Keep neutral labels and original links until then. | The displayed claim can be traced to the source/record, including negative cases. This report does not propose enabling those claims. |
| Every merge | Recheck findings after the final head review, not after an earlier all-clear. | Each actionable finding has a disposition against the head being merged; late findings block merge until fixed or explicitly adjudicated. |

Existing regression homes include
[`test_agenda_cancellation_notices.py`](../../tests/test_agenda_cancellation_notices.py),
[`test_agenda_notice_cleanup.py`](../../tests/test_agenda_notice_cleanup.py),
[`test_agenda_fallback_boundaries.py`](../../tests/test_agenda_fallback_boundaries.py),
and [`test_api.py`](../../tests/test_api.py). The tests named above are not new
claims that the two outstanding P2s are already covered.

## Evidence Limits And Related Lessons

The title P2 mechanisms were freshly reproduced through public fallback
extraction on `3240a33`: a blank-separated staff sentence entered the title,
and `U.S.` stopped the title before `Highway 101 interchange`. This is a
diagnostic reproduction, not a repair or a live-data audit.

Reproduce those two defects without writing records, from the repository root:

```bash
PYTHONPATH=. .venv/bin/python - <<'PY'
import logging
from pipeline.agenda_extraction_fallback import run_agenda_extraction_pipeline

sources = [
    "[PAGE 1]\n1. 25-03843 Discussion of the city charter\nand next steps\n\n"
    "Staff provided background on the proposal\n\nRecommendation: Receive the report.\n",
    "[PAGE 1]\n1. Approve improvements to the U.S.\nHighway 101 interchange\n"
    "Recommendation: Approve the project.\n",
]
for source in sources:
    agenda = run_agenda_extraction_pipeline(
        text=source, raw_provider_content=None, mode="balanced",
        logger=logging.getLogger("postmortem"),
    )
    print([row["title"] for row in agenda])
PY
```

At #328 merge, catalog 3034's meeting mismatch remained explicitly deferred.
Later [#341](https://github.com/manumissio/town-council/pull/341),
[#342](https://github.com/manumissio/town-council/pull/342), and
[#343](https://github.com/manumissio/town-council/pull/343) contain subsequent
work. Their results must not be credited to #327/#328 or treated as a fresh
full-resolver quality assessment here. Historical test and browser results in
the linked reports are recorded evidence, not checks rerun for this document.

This repeats the [baseline program's evidence-boundary lesson](2026-08-13-baseline-v2-evidence-program-prs-230-262.md)
and [PR #224's warning about reviewing an unsupported premise](2026-08-03-pr-224-speculative-follow-up-plan.md).
The agenda-specific addition is the full chain: **source meaning must survive
selection, replacement, failure handling, counting, and display.** The existing
[meeting-items design](../plans/2026-09-05-structured-meeting-design.md) provides
the proposed reader contract; it is not proof that all of it has shipped.
