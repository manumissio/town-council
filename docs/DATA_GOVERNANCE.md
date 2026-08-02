# Data Governance

Town Council ingests public municipal records and derives searchable,
summarized, entity-linked data from them. Public-record status does not by
itself justify every derived use: aggregation, entity linking, and search
change the accessibility of information about identifiable people. This
document states the project's handling policy.

Status: effective. Decision G4 was approved on 2026-07-26 and runtime
enforcement landed under T-GOV-2A on 2026-07-31. The obsolete meeting-search
people projection was deleted under T-IDX-1 on 2026-08-02.

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

## 3. Roster-gated person entities

Only records from a currently approved Legistar OfficeRecords roster for the
relevant municipality and governing body may become person entities. Covered
officials may receive profiles, memberships, and vote attribution only from
that roster evidence.

Title inference, fuzzy matching, and source-document mentions are not roster
authority. The document-derived person-linking path is removed.

Non-roster names remain searchable source text. They do not become person
entities, people metadata, profiles, memberships, vote attribution, or
cross-document aggregation. Outside enrichment of private individuals remains
forbidden.

Cities without a current approved roster source fail closed. Current registry
revocation depublishes previously stored roster records. A structurally valid
empty approved roster clears that governing body's roster; a transient or
invalid source response preserves the last verified database snapshot. When
the approved governing body changes, a successful sync depublishes the
superseded body's roster.

The current meeting-search index and response contracts contain no people
projection because event-to-body linkage is heuristic and cannot establish
roster authority. Roster-backed `/people` and `/person/{id}` publication remains
separate. A future meeting projection requires independently authoritative
event-to-body identity and separate authorization.

Corrections apply to derived records and indexes. Source documents are not
modified.

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
- Derived person-level data for non-roster people: not retained. Existing
  inferred records are removed during the roster-gate transition and cannot be
  re-derived.
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
