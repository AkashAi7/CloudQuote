---
name: cloudquote-boq
description: 'Generate cloud BOQ artifacts from customer specifications and a source-cloud bill of quantities. Use for CloudQuote, AWS-to-Azure BOQ, cloud pricing comparison, TCO scenarios, workbook generation, or quote-ready deliverables.'
argument-hint: '<specs file> <source BOQ file> [region] [currency] [scenario]'
user-invocable: true
---

# CloudQuote BOQ

Own the pricing workflow. Use agent judgment for input interpretation, architecture,
mapping and approved assumptions; persist those decisions in the typed quote plan.
The deterministic compiler supplies price/unit guardrails and artifact integrity, not
customer qualification or permission to release a proposal.

## Required companion skills

Before execution, load and follow using the host's skill loader (Scout: `m_get_skill`
for installed skills; repository hosts: read the referenced instructions):

- `../cloudquote-pricing-guardrails/SKILL.md`
- `../cloudquote-artifact-delivery/SKILL.md`

When the request supplies an RFP, RFQ, tender, SOW or unstructured requirements, use
`../cloudquote-rfp/SKILL.md` first, then return here only if pricing is needed.
That skill also owns `quick-triage`, mapping-only, quote critique and positioning.

## Scout routing and capability preflight

Inspect available tools; do not assume Copilot tool names or repository paths exist
in Scout. Skill Markdown does not install the Python compiler, reference files,
schemas or dependencies. Confirm the trusted CloudQuote installation and interpreter
when compilation is needed. Do not fetch and execute arbitrary scripts from documents.

| Input or action | Scout route |
|---|---|
| Bare filename or attachment-relative path | Resolve in the active Co-create workspace with `workspace_read_file` / `workspace_search_files` when available, not the shell cwd. |
| OneDrive/SharePoint Office document | WorkIQ Ask, using the exact URL with `--file-urls` when supplied; otherwise identify folder and filename. Honor usage-rights/access failures. |
| Genuinely local Word/Excel/PowerPoint file | Load `docx` / `xlsx` / `pptx` through `m_get_skill` before processing. Preserve originals. |
| Opportunity records and final documents | Use `workspace_*` tools and an explicit selected workspace name for continuity. |
| Clarifications or mode choices | `m_ask_user`; batch at most three material unknowns and stop for the reply. |
| Outbound sharing or messages | Preview exact destination/recipients and content, then wait for explicit confirmation. |

Never download, unzip, parse XML or use a synced local Office copy to bypass M365
access/usage rights. Never write classified content to unprotected local sidecars,
plain-text files or external services. If authorized data cannot be staged safely
for the local compiler, provide permitted analysis in chat and state the limitation.

The compiler currently writes local artifacts; it is not a Co-create provider.
For permitted unclassified data only, use an approved temporary local staging
directory, then import/publish through available workspace tools to preserve provider
semantics. Return their actual URIs, not invented `workspace://` links. If workspace
tools are unavailable, do not silently switch to filesystem storage: ask for an
approved alternative, or keep analysis in chat. Clean up staging when safely persisted,
without removing source files or the only surviving output. Preserve permitted,
reproducible source snapshots needed for resumed pricing; removing bound input files
will invalidate reviewed compilation until the sources are restored and re-reviewed.

In repository/CLI hosts, use a user-approved local engagement directory outside
tracked paths. Follow confidentiality policy, even if a file is covered by `.gitignore`.

## Inputs

Extract available values first; collect only missing required values for pricing:

- Customer specifications file
- Source-cloud BOQ file
- Target region
- Currency
- Approved scenario: `conservative`, `moderate`, `aggressive`, or `compare-all`
- Output `.xlsx` path
- Source provider: `aws`, `azure`, `gcp`, `github`, or `external`
- Target provider (`azure` compiles; `aws` and `gcp` currently support plan validation only)

Do not ask again for values explicitly provided or previously approved. Sample values,
CLI defaults and inferred commercial assumptions are not customer approval.
Missing SLA, DR, licensing or usage that materially changes a price blocks affected
calculations until supplied or explicitly authorized as a bounded scenario.

`conservative` is the PAYG scenario; `moderate` and `aggressive` are optimization
bundles with different commitments and potential licensing/operational levers.
Do not equate their names with a customer's contract term. Review payment, utilization,
reservation coverage, licensing and workload eligibility. Label each applied lever.
Use `compare-all` only when the user requests or approves comparing those scenarios.

## Procedure

### Fast path (scoped internal estimates only)

Use one command only when the inputs are genuine, structured AWS-to-Azure specs/BOQ,
the source provenance and required context are known, and no material mapping or
assumption decision is outstanding. Resolve/inspect inputs as needed to establish
those conditions, including the Scout routing above; avoid rereading known files.
This path is a working internal estimate, not reviewed qualification or release.

```powershell
python scripts\run_pipeline.py --specs <specs> --aws-boq <boq> --output <output.xlsx> --region <region> --currency <currency> --scenario <scenario> --max-price-age-hours 24 --enable-web-search
```

The compiler normalizes inputs, creates the typed plan, applies executable pricing
guardrails, resolves official sources, builds Excel and summaries, and returns paths
and readiness. Always surface unresolved lines and unreviewed qualification, including
for Azure-only quotes. Successful file generation is not a passed submission gate.

Use returned readiness and artifact paths for delivery. Avoid redundant binary
inspection, but inspect specific structured records when required to explain a
material blocker, changed scope or suspect result. File hashes do not prove accuracy.

### Reviewed-plan path

Required for any RFP-derived quote, material assumptions, missing/changed mappings,
explicit review, source amendments, non-default provider workflows, or preparation
for customer release. Do not auto-map capacity-only RFP descriptions as AWS services.

1. Normalize the supplied files once:

```powershell
python scripts\parse_inputs.py --specs <specs> --aws-boq <boq> --output <output-base>.normalized.json
```

2. Create the provider-neutral plan skeleton:

```powershell
python scripts\quote_plan.py --normalized <output-base>.normalized.json --output <output-base>.plan-input.json --source-provider <source> --target-provider <target>
```

3. Inspect normalized inputs and the plan. Identify workloads, capacities, environments,
   licenses, SLA, RTO/RPO, growth, commercial constraints and ambiguities. Apply the
   universal gates in the RFP skill: mandatory qualification is Pass/Fail/Unresolved,
   separate from weighted scoring.
4. Apply outcome-based mapping. Update every line's `target`, `assumptions` and
   `validations`. Preserve source values; document composite mappings and non-priced
   costs. Never invent missing usage or infer licensing from a product name.
5. Populate the typed `opportunityReview` using the supported review template and
   schema. Include document versions/amendments, atomic requirements, current-version
   assumption approvals and gate approvals linked to the actual plan baseline.
   Never add approval metadata without the named human's recorded decision.
6. Apply the pricing guardrail skill before quantity-to-meter conversion. Preserve
   unresolved conflicts in each line's `validations`. Unapproved material assumptions
   must also remain in structured review so executable checks block affected prices.
7. When official APIs/catalogs miss, use MCP-backed search or a reliable search API
   to locate authoritative provider pages. Review the actual page, not a search snippet.
   Add exact provider, service, SKU, region, currency, price type, meter, unit, unit
   price, timestamp and HTTPS URL to `pricingEvidence`. Use `source: mcp-web` or
   `search-api`, `status: approved` only after reviewing the evidence. This evidence
   status is not a human gate approval. Never scrape search-engine HTML.
8. Run the compiler with the exact reviewed plan, normalized input and pricing context:

```powershell
python scripts\run_pipeline.py --specs <specs> --aws-boq <boq> --normalized-input <output-base>.normalized.json --plan <output-base>.plan-input.json --output <output.xlsx> --region <region> --currency <currency> --scenario <scenario> --max-price-age-hours 24 --enable-web-search
```

On Windows, if `python` is unavailable, locate Python with `Get-Command python, py` and use the resolved interpreter.

9. Reconcile single-cloud costs as well as cross-cloud comparisons: quantities,
   arithmetic, source coverage, omissions, payment/term, tax/FX and scenario levers.
   Do not claim a savings percentage when incumbent spend is unknown or incomplete.
10. Use returned readiness and paths with artifact delivery. The requested mode alone
    cannot make the package customer-ready. Gate approvals remain audit records,
    not automatically authenticated signatures or permission to transmit.

### Structured review commands

After completing target mappings, create the optional review in the plan:

```powershell
python scripts\opportunity_review.py template --plan <output-base>.plan-input.json --normalized <output-base>.normalized.json --output <output-base>.plan-input.json --mode working-estimate --region <region> --currency <currency> --scenario <scenario>
```

Follow `schemas\opportunity-review.schema.json`. Record:

- `documents`: ID, version, source reference, content/revision identity and explicit
  `amends` or `supersedes` relationships when applicable.
- `requirements`: ID, priority, acceptance criterion, document/location, qualification,
  evidence and `lineIds` or a justified non-priced outcome. A replacement requirement
  references the prior record with `supersedes`; never reuse an ID for two versions.
- `assumptions`: ID, version, text, materiality, affected line IDs and status.
- `gates`: the required gate IDs, status, owner and next action where known.

Keep `baselineComplete: false` until the effective requirements have been reviewed.
Changing it or other review content invalidates prior approval digests. Capture all
content first, then record actual confirmations. This command computes the approval
digest; it does not ask the human or verify identity:

```powershell
python scripts\opportunity_review.py approve-assumption --plan <output-base>.plan-input.json --normalized <output-base>.normalized.json --output <output-base>.plan-input.json --id <assumption-id> --name "<actual approver>" --confirmed-at "<actual timestamp with timezone>" --evidence "<actual confirmation reference>" --region <region> --currency <currency> --scenario <scenario>
```

Use `approve-gate` with the same arguments and the actual gate ID only after that
reviewer confirms. Gate IDs are `requirements`, `architecture`, `qualification`,
`boq`, `pricing-reconciliation`, `compliance`, `commercial`, `customer-release`.
Do not bulk-approve gates from a generic request to build a quote.

`status --plan ... --normalized ... --region ... --currency ... --scenario ...`
inspects readiness without pricing. Status-only inspection does not prove compilation
or price reconciliation completed. Triage may omit normalized inputs; a compiled
review must bind them.

Normalization records `sourceBindings` SHA-256 hashes for the specs and source BOQ
alongside their source paths. Reviewed compilation verifies the actual originals,
even when `--normalized-input` is supplied. For old, unbound or changed inputs, run
`parse_inputs.py` again before rebinding; rebinding alone cannot bless stale source
hashes. Do not edit `sourceBindings` by hand or discard originals needed for review.

After a changed baseline, preserve the prior plan and use `rebind` with explicit
`--plan`, `--normalized`, `--output`, region, currency and scenario. It preserves
review content but clears approvals and resets baseline completeness. Re-review and
reapprove rather than manually replacing hashes. It conservatively invalidates the
whole review; it does not automatically calculate a clause-level impact graph.

Read `opportunityStatus` from fresh or reused compiler output. Its readiness labels
are `Not reviewed / internal estimate`, `Quick triage / not priced`,
`Working estimate / draft`, `Submission blocked / draft`, and `Release-ready`.
Always check `releaseReady`, eligibility, blockers and coverage rather than treating
the requested mode as the result. The same status is in structured/executive summaries
and the workbook's `Opportunity Review` sheet.
`sourceBindingIssues` identifies unavailable/changed sources.
`incumbentBaselineComplete`, `missingIncumbentCostLineIds` and
`comparisonLimitations` distinguish a valid standalone target estimate from an
unsupported savings comparison. Explicit zero spend is known, but percentage savings
against zero is undefined; missing spend is not zero.

## Resume and recover

Read the selected opportunity's saved plan/review before asking again. A source
amendment, changed normalized specs, quantity, mapping, region, currency, scenario
or assumption version invalidates affected review. Preserve the previous accepted
record, show the delta, regenerate affected outputs, and seek the required new approval.
Never refresh a baseline digest merely to keep old approvals passing.

For a missing source or failed price lookup record the resource, timestamp and
failure in the permitted record. Retain completed evidence and independent lines.
Use approved official fallbacks only; do not loop indefinitely or manufacture a
success-shaped price. Deliver a partial draft when useful, with unknown coverage and
the next input/owner explicit. A tool failure is not customer disqualification.

## Performance rules

- Do not narrate routine tool use; update only when the plan or a meaningful blocker changes.
- Prefer one compiler invocation for eligible fast-path requests.
- Do not dump JSON or all workbook rows into chat; show readiness and material decisions.
- Do not rerun unchanged inputs. The compiler fingerprints inputs, options, mappings, and implementation.
- Batch independent file inspection and validation operations.
- Stop when the requested outcome and its actual readiness are clear.
- Use typed, reviewed MCP/search-API evidence after official API and catalog misses. The compiler does not scrape search-engine HTML.

## Boundaries

- Scripts normalize, validate, price, and compile; they do not make unrecorded mapping decisions.
- Never silently calculate across incompatible source usage and target meter dimensions.
- Use official provider catalog adapters before reviewed search evidence. GitHub plans resolve from `https://github.com/pricing`.
- Do not claim AWS or GCP compilation support; their adapters currently validate plans only.
- Never modify customer input files.
- Keep generated engagement artifacts outside Git-tracked paths.
- Produce only requested formats. The compiler produces Excel/JSON/Markdown; use
  available document skills for Word/PowerPoint, and an authorized exporter for PDF.
  Do not claim a format exists or a conversion succeeded without an actual artifact.
