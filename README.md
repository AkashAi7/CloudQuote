# CloudQuote

CloudQuote helps sellers qualify cloud opportunities, identify RFP gaps and prepare
defensible estimates in Microsoft Scout or GitHub Copilot. Its pricing compiler
converts structured requirements and an AWS BOQ into an Azure workbook with regional
prices, scenarios and structured summaries. Seller discovery does not require a bill,
a complete architecture or a workbook.

The plan model is provider-neutral. Azure is the implemented compilation target;
AWS/GCP targets support plan validation only, not automatic priced workbooks.
Evidence-backed manual qualification/mapping is distinct from compiler support.

## Start with a seller outcome

| Mode | Use it for | Deliverable boundary |
|---|---|---|
| `quick-triage` | "Should we bid?" / "Where could Azure fail?" / "What should I ask?" | Decision insight, eligibility risks and up to three high-impact questions; no invented pricing |
| `working-estimate` | "Build a BOM" / "Explain this price gap" | Evidenced costs, approved assumptions and visible unpriced coverage; internal draft |
| `submission-ready` | "Prepare this for customer review" | Complete current gates and named approvals; never auto-send |

The assistant infers intent, extracts supplied facts before asking questions, and
does not use sample region/currency/commitment values as customer approval.
Material unknowns block affected costs, not independent analysis.
An active mandatory failure means **Fail**, regardless of price or weighted fit.

## Copilot usage

Open this repository in a GitHub Copilot coding agent environment and select the `cloudquote` custom agent, or run the `cloudquote` prompt from `.github/prompts/cloudquote.prompt.md`.

The workflow is skill-driven:

- `cloudquote-boq` orchestrates input interpretation, mapping, and artifact generation.
- `cloudquote-rfp` owns seller modes, procurement intake, amendments, qualification and optional positioning.
- `cloudquote-pricing-guardrails` blocks unsupported unit conversions.
- `cloudquote-artifact-delivery` presents readiness, material decisions and requested file links.

Agent decisions are persisted in a schema-validated `quote-plan.json` before compilation, so mappings and validation assumptions directly affect generated artifacts.

Scoped, structured AWS-to-Azure internal estimates retain the single-command fast
path. RFP-derived inputs, material assumptions, changed mappings, amendments and
release preparation use reviewed planning. Neither path waives pricing integrity;
unreviewed internal estimates do not imply qualification or customer readiness.

Provide:

- Customer specifications in YAML, JSON, or DOCX format
- AWS BOQ in CSV or XLSX format
- Azure region and currency
- Approved pricing scenario: `conservative`, `moderate`, `aggressive`, or `compare-all`

The scenario names represent optimization bundles, not merely contract lengths.
Review their commitment, license-benefit and operational assumptions rather than
mapping tender language directly to a scenario. Private offers and negotiated terms
are not inferred from public list prices.

The generated output includes:

- An Excel workbook with mapping, costs, assumptions, executive summary, and validation tabs
- `summary.json` for structured consumption
- `executive_summary.md` for Copilot chat
- `quote-plan.json` as the auditable agent-to-compiler contract

## Microsoft Scout usage

Install the four companion skills through Scout's supported skill-management flow.
Keep their companion references available and load instructions with `m_get_skill`
before executing a skill. The Copilot `.github` location and frontmatter are not a
claim of automatic Scout discovery. Do not assume importing only `SKILL.md` installs
Python, scripts, schemas, reference files or the compiler.

For compilation, provision a trusted local CloudQuote checkout and the dependencies
below, then make its location available to the agent. Pure triage needs only the
available document-access tools and skill instructions.

| Resource | Route |
|---|---|
| Bare filename/attachment | Resolve in the active Co-create workspace with available `workspace_*` tools |
| OneDrive/SharePoint Office document | WorkIQ Ask; ground on the exact URL with `--file-urls` when supplied |
| Genuinely local Office document | Load the appropriate Word/Excel/PowerPoint skill before processing |
| Opportunity state and deliverables | Selected Co-create workspace through its tools, preserving provider/version semantics |
| Missing values or mode choice | Grouped `m_ask_user` prompts, not an exhaustive intake form |
| Sharing | Exact content/destination preview, then explicit user confirmation |

Never download or parse a cloud-hosted Office file, or its synced copy, to bypass
M365 access or sensitivity restrictions. The Python compiler writes local files:
only stage data locally when its classification and the user's permitted storage
allow it. Import outputs through available workspace tools; do not invent workspace
URIs. If those tools or safe storage are unavailable, explain the limitation and ask
for an approved alternative, or provide allowed analysis in chat.

Example seller requests:

```text
Quick-triage this tender and its corrigendum. Tell me the Azure qualification risks
and the three most useful questions for the customer. Do not build a workbook yet.

Build a working estimate for this approved AWS inventory in Central India, INR.
Use PAYG; ask before assuming DR capacity or license benefits.

Resume this opportunity using the new amendment. Show changed requirements and
which quantities, prices and approvals are now stale.
```

## Review and change control

The RFP skill keeps stable requirement IDs, source clause/page references, document
versions and explicit amendment relationships. Newer upload timestamps alone do not
establish precedence. Renumbered tender rows retain their original requirement
identity; conflicting Q&A or amendments need resolution rather than a silent choice.

Store review decisions in the plan's structured `opportunityReview`, not a loose set
of Markdown files. Requirements link to real plan lines or justified non-priced
outcomes; material assumptions carry versions, affected lines and actual approval
metadata. Mandatory eligibility is separate from any scored evaluation.

Requirements, architecture, qualification, BOQ, pricing/reconciliation, compliance,
commercial and customer-release approvals are required for release readiness.
Editorial and competitive review apply to the relevant deliverables. Approval
metadata is an auditable record, not authenticated human identity; successful
compilation never authorizes sharing.

When sources, quantities, normalized specifications, target mappings, region,
currency, scenario or assumption versions change, affected decisions and approvals
must be revisited. Preserve the last accepted record, show the delta and resume from
the affected stage. Do not regenerate approval metadata simply to make a gate pass.

If a source or calculator is unavailable, preserve completed work and deliver a
clearly partial internal result with the missing input/owner visible. Do not replace
missing evidence with remembered prices, loop indefinitely, or hide blockers in files.

### Structured review CLI

Use the reviewed-plan steps in the BOQ skill to normalize inputs and produce a plan,
then complete target mappings before binding the review. For example, with existing
`engagements\example\quote.normalized.json` and `quote.plan-input.json`:

```powershell
python scripts\opportunity_review.py template `
  --plan engagements\example\quote.plan-input.json `
  --normalized engagements\example\quote.normalized.json `
  --output engagements\example\quote.reviewed.json `
  --mode working-estimate --region centralindia --currency INR --scenario conservative
```

These context values are examples, not defaults for an actual customer. Populate
`opportunityReview` using [the review schema](schemas/opportunity-review.schema.json):

| Record | Required content |
|---|---|
| Document | `id`, `version`, `sourceReference`, `contentId`; optional `amends` or `supersedes` |
| Requirement | `id`, `priority`, `acceptanceCriterion`, `source.documentId`, `source.location`, `qualification`, `evidence`, `lineIds`; use `nonPricedJustification` instead of mapped lines where applicable |
| Assumption | `id`, `version`, `text`, `material`, `lineIds`, `status`; actual approval metadata when approved |
| Gate | Required gate ID and status; actual approval metadata when approved, optional owner/next action |

Requirements use `pass`, `fail`, or `unresolved` qualification. Only `scored`
requirements accept a `score` (0-1) and positive `weight`; mandatory eligibility
cannot be offset by this independent score. Explicit `supersedes` links retain old
requirement versions without counting them as active requirements.

The generated template has `baselineComplete: false` and pending gates. Do not
change completeness until the effective requirements are reviewed. Add review
content before recording approvals: edits invalidate approval digests.

After an actual human confirmation, use `approve-assumption` or `approve-gate`.
Replace the placeholders with the real decision metadata; the command neither
solicits approval nor verifies identity:

```powershell
python scripts\opportunity_review.py approve-gate `
  --plan engagements\example\quote.reviewed.json `
  --normalized engagements\example\quote.normalized.json `
  --output engagements\example\quote.reviewed.json `
  --id requirements --name "<actual approver>" `
  --confirmed-at "<actual ISO timestamp with timezone>" `
  --evidence "<actual confirmation reference>" `
  --region centralindia --currency INR --scenario conservative
```

Use the same arguments with `approve-assumption --id <assumption-id>` for a versioned
assumption. Never invent confirmation metadata or bulk-approve from "build a quote".
Pass the resulting reviewed plan to `run_pipeline.py --plan` with the matching
`--normalized-input`, region, currency and scenario.

The `status` command takes `--plan`, optional `--normalized`, and pricing context
without an output path. It does not price, share or claim compilation completed.
For a changed baseline, `rebind` takes those arguments plus explicit `--output`;
preserve the old plan first. Rebinding clears approvals and resets completeness.
It conservatively invalidates the whole review, not just an automatically inferred
subset of affected clauses. Re-review and seek current approvals before release.

The baseline binds plan content, normalized source/specification inputs and pricing
context. Normalization records absolute source paths and
`sourceBindings: {specs: "<sha256>", awsBoq: "<sha256>"}`. Reviewed compilation verifies
the original files, including when `--normalized-input` is supplied. Changed,
unavailable or unbound originals block reviewed prices and readiness. Regenerate
old/stale normalization with `parse_inputs.py`, then rebind, review and reapprove;
`rebind` cannot bless stale source hashes. Preserve permitted input snapshots for
resumption; do not manually edit their hashes.

Document `contentId` is a recorded source revision, not an automatic fetch of a
cloud document. Agents must re-read amended cloud sources through authorized tools;
local hashing cannot discover an upstream change that was never supplied.

`opportunityStatus` appears in fresh/reused compiler stdout, summary JSON, executive
summary and the workbook's **Opportunity Review** sheet. Readiness is one of:
`Not reviewed / internal estimate`, `Quick triage / not priced`,
`Working estimate / draft`, `Submission blocked / draft`, or `Release-ready`.
Legacy plans still generate internal estimates but never acquire release readiness
implicitly. Triage can remain entirely in chat; no plan or compiler is required.

The status also reports `sourceBindingIssues`, `incumbentBaselineComplete`,
`missingIncumbentCostLineIds` and `comparisonLimitations`. Missing incumbent costs
remain unknown, not zero: a standalone target estimate can be release-ready while
savings, comparison recommendations and cost drivers remain unavailable. Explicit
zero spend is known, but percentage savings against it is undefined.

## Local setup

Requires Python 3.10 or later.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the sample pipeline:

```powershell
python scripts\run_pipeline.py `
  --specs samples\customer_specs.yaml `
  --aws-boq samples\aws_boq.csv `
  --output engagements\sample\azure_boq.xlsx `
  --region centralindia `
  --currency INR `
  --scenario moderate
```

`--output` must be an `.xlsx` file path. The JSON and Markdown summaries are written beside it.

Each sidecar is prefixed by the workbook name, preventing collisions when multiple quotes share a directory. Unchanged inputs and options reuse existing artifacts only after fingerprint, hash, JSON, and workbook-format validation. Price reuse expires after 24 hours by default.

Official provider catalogs and the Azure Retail Prices API are always used first. For unresolved reviewed-plan lines, the agent can supply approved MCP/search-API results through the typed `pricingEvidence` contract. The compiler never scrapes search-engine HTML. `--enable-web-search` remains as a compatibility flag that requires this reviewed evidence after official-source misses.

Use `--price-cache <path>` to isolate pricing caches for separate environments or benchmark first-run behavior.

## Performance

Eligible internal-estimate requests use one compiler command and return concise
readiness plus requested artifact links. CSV parsing and HTTP dependencies are
lazy-loaded, independent price lookups are bounded, validation-only lines skip
network calls, and pricing-cache writes are batched.

Reference measurements for the included samples on Python 3.12:

- Standard first build with warm pricing cache: about 3.3 seconds
- GitHub catalog build: about 2.3 seconds
- Unchanged repeat build with integrity verification: under 1 second

Cold Azure API performance varies with network and service response time. Generated summaries and run manifests report unresolved rate, source coverage, fallback success, and fallback latency.

## Pricing safety

The pipeline uses Azure Retail Prices API results, timestamped cache fallback, and official public catalogs. GitHub Team and Enterprise prices resolve from [GitHub Pricing](https://github.com/pricing). It marks stale evidence, currency mismatches, unresolved mappings, composite-service omissions, incompatible usage-to-meter conversions, and unverified web estimates as `[VALIDATE]` instead of producing unsupported totals.

Azure is the production compilation target. AWS and Google Cloud adapters validate provider-neutral quote plans and expose explicit capability gates; compilation remains blocked until their pricing and workbook backends are implemented.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Run the optional live Azure pricing canary with:

```powershell
$env:CLOUDQUOTE_LIVE_PRICING_CANARY = "true"
python -m unittest tests.test_pricing_canary -v
```

Customer workbooks, engagement outputs, local price caches, and generated summaries are excluded from Git.

## Seller experience acceptance

Exercise incomplete RFP intake, a mandatory failure despite lower cost, renumbered
amendments, unapproved usage/DR assumptions, a source outage, a resumed opportunity
and missing release reviewers. Expected behavior is useful partial work with
explicit uncertainty, no fabricated prices or approvals, and no hidden blockers.

For a seller pilot, measure time to first actionable insight, clarification turns,
recovery after a blocker and reviewer correction rate. Collect only approved,
non-sensitive telemetry; these are proposed product measures, not measured results.
