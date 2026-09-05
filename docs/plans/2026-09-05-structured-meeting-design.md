# Meeting items: a design for discussion

Date: 2026-09-05

Code reviewed at commit: `3de41d89075af1eb599f877c7b1a10bf60371a81`

We have agreed on the product direction. Test representative documents before
deciding how to build it.

## What we want readers to see

Use the demo's readable item cards as the target experience. Agendas and
minutes should use the same layout, but describe different things:

- An agenda describes proposed business and requested actions.
- Minutes describe recorded discussion, actions, and outcomes.
- Both can contain useful reports and updates without a vote.

These differences do not require separate processing pipelines. Reuse the code
that identifies document types and extracts items where possible. Help readers
find the meeting's business and check each item against the original source.

## What to keep from the demo

Keep meaningful titles, concise descriptions, source links, and clearly labeled
outcomes when the source supports them. Leave out administrative instructions
and empty section headings. Keep the original document available.

The demo shows how items should look. It is not a complete answer key.
For example, the source for catalog 705 includes a permit-processing budget
adjustment absent from its structured list. Catalog 703's fiscal-update item
links to page 2, while its heading starts on page 1 and its action appears on
page 2. These examples do not show whether those choices were intentional.
Check what each example includes and leaves out before using it to judge results.

Evidence: [demo items](../../frontend/public/demo/search.json),
[705 source](../../frontend/public/demo/catalog_705_content.json), and
[703 source](../../frontend/public/demo/catalog_703_content.json).

## What each item should tell readers

| Reader question | Proposed behavior |
| --- | --- |
| What business is this? | Use a title that describes actual meeting business and is supported by the source. Do not turn every heading into an item or limit the list just to keep it short. |
| What is it about? | Give a short description supported by the source. Do not invent details to fill the card. |
| What was requested? | Label agenda recommendations as proposed or requested. |
| What happened? | Show an outcome from minutes only when the source records it. If the source does not say what happened, the outcome is unknown. |
| Was there a vote? | Distinguish a recorded vote from discussion, instructions to staff, and a report received by the council. Do not label every outcome "Vote". |
| Can I check it? | Link to the supporting page, text passage, or matched official item. Do not substitute page 1 when the location is unknown. |
| How much is covered? | Say when the list is incomplete or its coverage is unknown. When testing results, check for missed business as well as false items. |

Keep consent-calendar items, which are grouped for a single vote, and
informational reports. A section label such
as "Public Hearings" is not itself a hearing item. A cancellation notice does
not contain completed decisions. A previously published agenda for a canceled
meeting may still contain real proposed business; retain that distinction.
Cancellation must refer to the current meeting, not a quoted earlier event or
a proposal to cancel something unrelated.

## When to show meeting items

Reuse the existing code for choosing sources, extracting possible items, and
storing results. Decide whether the items are supported before publishing them
as current records.

1. Identify the document type and the evidence available. Missing document text
   in the database does not prove that a meeting had no business. An official
   item verified separately may still be usable when text extraction fails.
2. Check that official item lists belong to the right meeting and document.
   Matching the city and date is not enough when several governing bodies meet
   that day. An uncertain match must not override the document or supply an
   outcome for its minutes.
3. Check that each proposed item describes actual business and has supporting
   evidence. Apply this rule to every extraction method, including text rules
   and web-page parsing. Check the final list after selecting or merging results.
4. Record how each item was extracted and which source supports it. A score from
   text rules can help investigate problems, but does not tell us how likely an
   item is to be correct. Test real documents and review missed items before
   choosing any score threshold for publication.
5. Record which source version and extraction rules were used to accept the
   items. An old `complete` status does not prove they meet new rules.
6. Use that same decision in user-requested processing, background batches,
   maintenance, item display, and features that use the items. Do not create
   separate copies of the acceptance rules in each place.

These are proposed requirements. The current code does not yet enforce all of
them. This design does not propose a new classification framework, another model
to review the results, a model upgrade, or another external source.

## How to explain missing or incomplete items

The messages below explain what readers need to know. Decide database values
and API changes after testing the sample documents.

| Evidence | Reader message and action |
| --- | --- |
| Never attempted | "Meeting items haven't been generated yet." Offer generation only when usable input exists. |
| Input unavailable | "Source text is unavailable." Offer the original source when its link exists. |
| Running | "Preparing meeting items." Do not also say that no items were found. |
| Accepted | Show the supported items with agenda/minutes context and source links. |
| Partially extracted | Say that the list is incomplete. Never present it as the full list. |
| Confirmed cancellation notice or confirmed absence of meeting business | Explain that finding. Getting no items from the parser does not prove either condition. |
| Extraction uncertain or unsupported | "Meeting items aren't available for this document." Keep the source accessible and explain the reason, if known. |
| Processing failed | "We couldn't generate meeting items." Offer a retry when appropriate. Do not describe the failure as a valid empty result. |
| Source changed or old output unverified | Explain that the items need to be checked again. Do not present them as current. |

Choose the message from the processing status returned by the service. An empty
list alone must not produce an "AI found nothing" explanation.

## How this affects summaries, votes, and search

Rejected items must not feed summaries, inferred votes, item search, or
meaning-based search. Remove their influence from existing copies too; hiding
the tab does not remove them from other features.

Show a summary as current only when the inputs it uses are still accepted and
up to date. A minutes summary supported directly by the minutes can remain
independent of agenda-item checks. So can meeting search based on original
source documents.

Preserve trusted `manual` and `legistar` vote evidence during any repair. Item
replacement currently deletes rows, so a vote extractor's overwrite protection
alone cannot guarantee that evidence survives. Linking a vote to a named person
must still follow [DATA_GOVERNANCE.md](../DATA_GOVERNANCE.md). The demo does not
authorize another way to create or publish person records.

Before repairing records, list the affected records, trusted evidence, and copies
used by other features. Decide how to keep database updates consistent, handle
overlapping runs and search-update failures, and undo the repair if needed.

If a failed attempt leaves an older accepted version available, label it as an
older version. Do not call it current or erase verified evidence. Do not use the
existing `empty` status for items withheld because they are uncertain. That
status can generate a fixed summary saying no agenda items were found.

## Where to look in the code

| Current behavior | Evidence home |
| --- | --- |
| The resolver reports fallback quality without rejecting its final list. | [agenda_resolver_runner.py](../../pipeline/agenda_resolver_runner.py), `resolve_agenda_items` |
| HTML merging can select a list solely because it contains at least three items. | [agenda_crosscheck.py](../../pipeline/agenda_crosscheck.py), `merge_ai_with_eagenda` |
| Legistar lookup chooses the first event returned for the city/date. | [agenda_legistar.py](../../pipeline/agenda_legistar.py), `fetch_legistar_agenda_items` |
| Tasks, workers, and maintenance each assign completion from persisted item count. | [task_agenda_segmentation.py](../../pipeline/task_agenda_segmentation.py), `run_segment_agenda_task_family`; [agenda_worker.py](../../pipeline/agenda_worker.py), `segment_document_agenda`; [agenda_segmentation_maintenance.py](../../pipeline/agenda_segmentation_maintenance.py), `persist_segmented_agenda` |
| Item replacement deletes existing rows and updates their summary input hash. | [agenda_service.py](../../pipeline/agenda_service.py), `persist_agenda_items` |
| Read responses infer an LLM source from completion status. | [catalog_routes.py](../../api/catalog_routes.py), `_agenda_item_source` |
| UI title and empty-body text use separate conditions; outcomes use a Vote label. | [ResultCard.js](../../frontend/components/ResultCard.js), agenda view |
| Agenda and non-agenda summaries use different input hashes. | [summary_freshness.py](../../pipeline/summary_freshness.py), `compute_summary_source_hash` |

These code paths need attention, but reading them does not tell us which one
created the bad records seen in the earlier inspection. That requires evidence
from the run that created those records.

## What to test first

Save a small, fixed set of complete source documents locally before changing
production behavior. Include the Sunnyvale cancellation and agenda that produced
noisy results, minutes recording actual business, a single-item meeting,
consent-calendar items, and information-only business. Also include a document
whose text is missing from the database and a same-day meeting match that is
ambiguous.

For each sample, record its source, a content hash to identify the exact version,
document type, expected items, supporting locations, and expected status. Keep
some examples aside for evaluation; do not use them to tune the extraction rules.

Run the existing extraction code on these samples with fixed model and source
responses. This tests how the code selects, parses, and accepts items. It does
not tell us how well a live model performs.

Test live-model output separately in a limited diagnostic run. Record the model
and runtime settings without writing results to the main database records.
Report false items, missed business, unsupported outcomes, incorrect source
references, and incorrect statuses separately. Use existing tests and manual
review. The first deliverable is a reviewed comparison of expected and actual
items, not a reusable evaluation framework.

Then plan one small change covering item acceptance, storage, display, and the
features that use the items. Before building it, name the files to change,
database changes needed, affected features, failure tests, and rollback steps.
Evaluate both agendas and minutes, even if they are delivered in stages.

Changing which records a batch processes, or changing baseline policy, requires
an explicit decision. Keep the checked-in baseline expectation unchanged unless
separately reviewed evidence supports a change.

The Berkeley records that show search text but lack stored document text need a
separate investigation that changes no records. This design explains how to show
missing text honestly; it does not claim we know why the text is missing.

## How to review this note

Check that the design handles the right source, missed items, proposed versus
recorded actions, incomplete lists, outdated copies, and trusted vote evidence.
Also check that the work stays within the agreed scope.
The existing [PR 224 postmortem](../postmortems/2026-08-03-pr-224-speculative-follow-up-plan.md)
and [baseline postmortem](../postmortems/2026-08-13-baseline-v2-evidence-program-prs-230-262.md)
support deciding what evidence is needed before building more tools.

For this document: run `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py`,
check this document's local links separately, and run `git diff --check`.
These checks cover links and formatting only. They do not establish extraction
quality or show that the application works correctly or is ready to deploy.
