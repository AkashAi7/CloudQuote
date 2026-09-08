---
name: cloudquote-rfp
description: 'Help sellers qualify cloud deals, find RFP gaps, prepare customer questions, and build defensible BOQ/BOM response packs. Use for RFP/RFQ/SOW/tender intake, bid/no-bid, Azure qualification, quote critique, amendments, cloud mapping, and competitive positioning in Microsoft Scout or Copilot.'
argument-hint: '<document or deal question> [quick-triage | working-estimate | submission-ready]'
user-invocable: true
---

# CloudQuote Seller and RFP Workflow

Help the seller make the next defensible decision. Extract before asking, expose
material uncertainty, and keep the bid machinery behind a concise decision summary.
Favor Azure where it genuinely fits; state evidenced Azure gaps and competitor strengths.

## Required companion skills

Load companion instructions using the host's skill loader before executing them.
In Scout use `m_get_skill` for installed skills; in a repository host read the
corresponding skill file. If a skill is not installed, report that rather than
claiming it ran.

- `../cloudquote-boq/SKILL.md`: Scout routing, normalized inputs, reviewed plans, compilation.
- `../cloudquote-pricing-guardrails/SKILL.md`: source evidence, units, complete costs.
- `../cloudquote-artifact-delivery/SKILL.md`: readiness summary, partial output, sharing.

Do not invoke the compiler for a discovery question, quick triage, mapping-only
analysis, or competitive strategy alone.

## Start with the seller's job

Infer the job from the request and supplied material. Do not make the seller fill
an intake form before receiving value.

| Seller request | First useful result |
|---|---|
| Should we pursue this? | Eligibility risks, decision deadline, go/no-go dependencies |
| Where does Azure fall short? | Mandatory gaps first, evidence and customer impact |
| Why is this quote expensive? | Frozen source quote, omissions, mismatches, defensible levers |
| What should I ask the customer? | At most three high-impact questions with rationale and owner |
| Build a BOM or response | Approved scope, quantities, evidenced costs, readiness |

| Mode | Output and boundary |
|---|---|
| `quick-triage` | Default for incomplete discovery or go/no-go. Findings, risks, next action; no invented price, SKU, or final qualification. No compiler or workbook required. |
| `working-estimate` | Default when pricing is requested. Price evidenced, sufficiently specified rows; preserve partial work and mark unknowns. Material assumptions need explicit approval before affected calculations. Internal draft, not a quote. |
| `submission-ready` | User requests release preparation. All mandatory gates, reconciliation and named approvals required. Requesting this mode is not approval. |

Honor an explicit mode. If intent remains ambiguous, offer these three choices;
in Scout use `m_ask_user`. Otherwise choose the applicable mode and state it briefly.
Ask only for missing information. Extract region, term, currency and scope before
asking; never substitute sample values or CLI defaults for customer facts.

Each question includes what is missing, why it affects the decision, who can answer
(seller, customer, architect, commercial owner), and which work is blocked.
Batch no more than three highest-impact questions per turn. Continue independent
analysis; do not repeatedly ask answered questions.

## Accepted inputs

RFP/RFQ/SOW, original BOQ, amendments, bidder Q&A, architecture, usage, and authorized
commercial material in text, PDF, Word, Excel, or pasted chat. Preserve originals.
Follow the BOQ skill's Scout/M365 routing before reading any document. Do not download
or locally parse cloud-hosted Office documents as a fallback. For genuinely local
Office files load the appropriate document skill; for scanned PDFs use an available,
authorized extraction tool and flag uncertain tables. Never invent unreadable cells.

## Universal gates

No mode or single-cloud fast path waives qualification, quantity integrity or truthful
cost reporting. A gate may be pending for a draft, but must never silently pass.

### 0. Scope, storage and continuity

Identify customer alias, opportunity, requested decision, due date, buying motion,
source/target clouds and permitted storage from available context. Select or resume
the existing opportunity; ask if multiple opportunities could match.

Persist only permitted structured records in the chosen destination. Reuse existing
answers, source versions and approvals. Do not create a fixed collection of empty
Markdown files. Keep originals, internal positioning and customer deliverables separate.
Record current mode, stage, blockers, decisions, affected records and next owner.

### 1. Effective requirements and early eligibility

Register each document's ID, version, reference and authoritative amendment relationship.
Retain the original text, page/table/clause and stable requirement ID (`REQ-001`).
Preserve tender row labels separately so renumbering never changes identity.

Apply an amendment only to clauses it explicitly replaces. Record old-to-new requirement
links, deleted items and quantity/unit/hour changes. A newer filename, upload time, or
unapproved Q&A is not automatically authoritative. Ask about conflicting governing
documents and block only affected decisions. Never silently discard an original row.

Extract atomic requirements with acceptance criteria and priorities `mandatory`,
`scored`, `optional`, `informational`. Keep ambiguity as a separate state. Include
non-priceable legal, procurement, security and compliance requirements; give them an
owner and unresolved status rather than treating them as irrelevant to eligibility.

Test obvious hard constraints before detailed sizing: required region, residency,
certifications, service maturity, procurement eligibility and commitment/payment rules.
Architecture-dependent qualification can remain unresolved until the design exists.

**Eligibility is Pass / Fail / Unresolved, never a weighted score.** Any active mandatory
failure means Fail; any unresolved mandatory requirement prevents Pass. Use only
eligible options in scored rankings. Show conditional designs separately, not as winners.
Tie any scored weights to published customer criteria, or label and seek approval for
proposed weights.

**Pass:** the effective baseline is approved. Recording a material unknown does not
authorize a quantity, a price, or a qualification claim.

### 2. Architecture and sizing

Define the minimum viable architecture before detailed pricing. Trace requirements to
components and components to normalized quantities; document justified non-priced
requirements and architecture components with no explicit customer requirement.

Cover production/non-production, peak/average usage, growth, operating hours, HA,
failure domains, DR region, RTO/RPO, backups/restore, identity, keys, security,
connectivity, egress, logs, support, licenses, migration and operations.
Record exclusions and owned-license eligibility explicitly.

Map operating outcomes, not product names. Use mapping classes `Direct equivalent`,
`Composite equivalent`, `Closest approximation`, `No clean equivalent`, separately
from delivery classifications `Native`, `Workaround`, `Roadmap/unverified`,
`Does not qualify`. A native service is not itself proof the requirement passes.
Capture current official regional/SKU availability and supporting evidence.

**Pass:** scope and sizing are internally consistent; material architecture changes
and assumptions have recorded approval. Unknowns block affected rows, not unrelated work.

### 3. Normalized BOQ and reviewed plan

Use `<output-base>.specs.yaml` with the sample specs structure and
`<output-base>.boq.csv` with the sample BOQ headers. The legacy `--aws-boq` argument is
a parser input name, not proof the customer uses AWS. Use `sourceProvider: external`
for provider-neutral requirements and explicitly review all target mappings.

Leave incumbent price fields blank when absent; an absent baseline is not zero
spend and cannot support savings percentages. Preserve source configuration, unit,
quantity and hours separately: explicitly determine whether quantity multiplies the
configuration and whether HA/environment multipliers are already included.

Create the typed plan using the BOQ reviewed-plan procedure. Store structured source,
requirement, assumption and approval records in `opportunityReview`; link active
requirements to actual plan line IDs. Keep mapping assumptions and meter conflicts in
the line's `assumptions` and `validations` arrays too. A component may serve multiple
requirements and a requirement may need multiple priced meters; preserve all links.
Generate readable requirements tables from these records, not as a second authority.

**Pass:** every active priced requirement and every plan line is traceable. Every
material assumption is either explicitly approved for its current version or blocks
its affected numeric costs. No generic "assumptions accepted" or placeholder approvals.

### 4. Evidence-backed pricing

Use the BOQ reviewed-plan path for every RFP-derived quote; never feed unreviewed,
provider-neutral text into automatic AWS mappings. Run the pricing companion skill.
Use current official APIs/catalogs first and official calculator/pages for gaps.
Preserve displayed versus derived values, exact configuration, timestamps and evidence.

Translate commercial terms intentionally. `moderate` and `aggressive` are compiler
optimization bundles, not synonyms for a customer's one-/three-year payment terms.
Do not silently select `compare-all` or assume reservation, AHB, Spot, Dev/Test,
upfront-payment or license eligibility. Record approved scenario scope and differences.
Private negotiated prices require authorized evidence, separate from public list prices.

**Pass:** all priced rows reconcile to quantities and exact meter evidence; unresolved
rows remain visibly unpriced. AWS/GCP target compilation is not implemented; provide
evidenced manual mapping/analysis if requested, not a fabricated compiled workbook.

### 5. Reconciliation and sensitivity

Always reconcile arithmetic, units, term, tax, currency/FX, support and included costs,
even for Azure-only work. For comparisons also normalize outcomes, HA/DR, performance,
operations and licensing. Never report a single definitive delta across material gaps.
Keep monthly run rate, annual/contract total, upfront, migration and negotiated costs
separate. Derive totals/deltas from unrounded inputs with visible formulas.

Test decision-sensitive changes in utilization, growth, egress, logs, HA/DR, commitment,
license benefit and FX. Show break-even points only when supported; label manual
sensitivity work separately from compiler-provided scenarios.

**Pass:** technical and pricing/reconciliation reviewers approve the current baseline.
Eligibility remains separate from price attractiveness.

### 6. Optional positioning and release

Run positioning only when requested or clearly the seller's stated job. Tie every
win theme and objection response to a customer criterion, verified proof, caveat,
discovery question, proof action and owner/due date. Explain real Azure price gaps;
never assume a private discount or hide a competitor advantage. Separate public,
internal and needs-approval content. Do not turn a weighted fit score into a predicted
win probability.

For submission-ready output require current named requirements, architecture,
qualification, BOQ, pricing/reconciliation, compliance, commercial and customer-release
approvals. Confirm editorial consistency and competitive claims when applicable.
No self-approval by the agent; no approval inferred from successful compilation.
Follow artifact delivery for the separate outbound preview/confirmation step.

## Change and recovery

Bind approvals to the current structured baseline and pricing context. On a new
amendment, region, usage, term, mapping or assumption version, mark affected requirements,
architecture, prices, comparison, strategy and approvals stale. Preserve the last
accepted version; show the delta and request only necessary new decisions.

If access, extraction, a calculator or an API fails, record resource, time and error
in the permitted opportunity record. Use only authorized official fallbacks. Do not
retry indefinitely or substitute remembered pricing. Keep existing evidence and
independent completed work, distinguish "pricing blocked" from "analysis blocked",
and resume from the failed stage after the missing input arrives.

If a reviewer is unavailable, deliver an explicitly internal draft with missing
approvals and owner visible; customer release remains blocked.

## Seller acceptance criteria

- A partial RFP produces useful triage before an exhaustive questionnaire.
- A mandatory failure cannot be offset by cost or fit scores.
- An amendment changing units/quantities invalidates affected costs and approvals.
- No DR/license/usage answer means no invented numeric price on affected lines.
- A source outage preserves partial work; returning later does not repeat answered questions.
- A compiled file never hides blockers or implies customer-release approval.
- Track time to first actionable insight, clarification turns, blocked-run recovery and
  reviewer correction rate only with approved, non-sensitive telemetry; do not fabricate metrics.
