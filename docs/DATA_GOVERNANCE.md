# Data Governance

Town Council ingests public municipal records and derives searchable,
summarized, entity-linked data from them. Public-record status does not by
itself justify every derived use: aggregation, entity linking, and search
change the accessibility of information about identifiable people. This
document states the project's handling policy.

Status: initial version. Section 3 carries the open decision (gate G4);
everything else is effective policy on merge.

## 1. Data classes

| Class | Examples | Sensitivity | Policy |
|-------|----------|-------------|--------|
| Source documents | Agendas, minutes, staff reports | Public record | Store, extract, index |
| Elected/appointed officials | Council members, commissioners acting in role | Public figures in public duty | Full treatment: profiles, memberships, vote attribution |
| Municipal staff | Clerks, department heads named in documents | Professional capacity | Index in document text; no dedicated profiles unless they hold a covered role |
| Private individuals | Public commenters, permit applicants, complainants named in minutes | Highest in scope | Governed by Section 3 |
| Derived AI content | Summaries, topics, entity links | Model output, may err | Must remain traceable to source (existing grounding contracts); correction path in Section 4 |

## 2. Principles

- Minimization: derive and expose the least person-level data needed for
  the civic-accountability purpose. Officials' public actions are the
  product; private individuals are incidental content.
- Traceability: every derived claim about a person must link back to the
  source document (the existing lineage and grounding machinery is the
  implementation surface for this).
- No enrichment of private individuals: never join private individuals'
  names against outside data sources. This is a hard line regardless of the
  Section 3 outcome.
- Correction over deletion for source records: source documents are the
  public record and are not edited; corrections apply to derived data
  (links, profiles, summaries, index entries).

## 3. Person-entity treatment for private individuals (DECISION G4 — open)

Options under consideration; exactly one will be adopted by ADR:

- Option A (roster-gated linking): `person_linker` creates/links Person
  entities only for names matching official membership rosters. Private
  individuals remain plain text in documents — searchable in full text, but
  never entity-linked, never in people metadata, never profiled.
- Option B (index-but-no-profile): names are indexed and may appear in
  people metadata on search hits, but profile pages and cross-document
  person aggregation are roster-gated.
- Option C (status quo + process): current extraction behavior, with the
  Section 4 takedown/correction process as the sole safeguard.

Working default until the ADR lands: build nothing new that expands
person-level aggregation of non-officials, and treat Option A as the design
target for City Coverage Expansion planning.

Decision owner: repository owner. Record the outcome in `docs/ADR.md` and
replace this section with the adopted policy.

## 4. Correction and takedown

Intake: the existing issue-reporting path (`POST /report-issue` via the UI)
is the canonical channel; `DataIssue`/`IssueType` records are the queue.

- Misattribution (wrong person linked, wrong vote attributed): correct the
  derived data and reindex. Target: within one release cycle.
- Private-individual removal request: remove entity links/metadata for that
  name and reindex affected documents. Source documents are not modified;
  requesters seeking source redaction are directed to the originating
  municipality.
- AI-content errors (hallucinated or misleading summary/topic): regenerate
  or clear the derived field; the UI already labels AI content as
  machine-generated — keep that labeling contractual (there is an existing
  frontend test for the disclaimer).

Every action taken under this section is logged as a resolved `DataIssue`
so decisions are auditable.

## 5. Retention

- Source documents and extraction outputs: retained indefinitely (archival
  civic record).
- Derived person-level data for private individuals: retained only while
  policy in Section 3 permits its existence; removals under Section 4 are
  permanent (re-derivation must respect a suppression list — implementation
  task to be filed with the G4 ADR).
- Operational telemetry: per `docs/OPERATIONS.md`; no person-level data in
  metrics.

## 6. Licensing

- Code: MIT (`LICENSE`).
- Source documents: remain the property/record of the originating
  municipalities; this project asserts no license over them and
  redistributes them as obtained from public portals.
- Derived data (summaries, topics, entity links, indexes): published
  without warranty; treat as CC0-style facts-plus-model-output unless and
  until a deliberate license choice is recorded here by ADR.
- Crawl conduct: honest user agent, robots.txt compliance, per-domain rate
  limits (`SECURITY.md`, crawler settings) — the project's standing terms
  of engagement with source sites.

## 7. Review triggers

Revisit this document when: onboarding a city wave (scale changes risk),
adding any new person-derived feature, receiving the first real takedown
request, or any external attention that changes the project's profile.
