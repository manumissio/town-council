# Data Governance

Town Council ingests public municipal records and derives searchable,
summarized, entity-linked data from them. Public-record status does not by
itself justify every derived use: aggregation, entity linking, and search
change the accessibility of information about identifiable people. This
document states the project's handling policy.

Status: effective. Decision G4 was approved on 2026-07-26. Runtime enforcement
remains pending under T-GOV-2A.

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

Only names matched to independently authoritative official membership data
for the relevant municipality, governing body, and meeting date may become
person entities. Covered officials may receive profiles, memberships, and vote
attribution only after that match.

Title inference, source-document mentions, and memberships created by the
entity linker are derived evidence, not roster authority. They cannot
authorize person creation or people-facing records.

Non-roster names remain searchable source text. They do not become person
entities, people metadata, profiles, memberships, vote attribution, or
cross-document aggregation. Outside enrichment of private individuals remains
forbidden.

Corrections apply to derived records and indexes. Source documents are not
modified. Current runtime behavior does not yet enforce this policy; T-GOV-2A
owns authoritative roster input, runtime gating, existing derived-data
remediation, reindexing, and prevention of re-derivation.

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
  records remain remediation debt until T-GOV-2A removes them and prevents
  re-derivation through roster gating.
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
