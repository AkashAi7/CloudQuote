---
name: cloudquote-boq
description: 'Generate cloud BOQ artifacts from customer specifications and a source-cloud bill of quantities. Use for CloudQuote, AWS-to-Azure BOQ, cloud pricing comparison, TCO scenarios, workbook generation, or quote-ready deliverables.'
argument-hint: '<specs file> <source BOQ file> [region] [currency] [scenario]'
user-invocable: true
---

# CloudQuote BOQ

Own the BOQ workflow. Use agent judgment for input interpretation, cloud mapping, assumptions, and validation. Persist those decisions in the typed quote plan consumed by the deterministic artifact compiler.

## Required companion skills

Before execution, load and follow:

- `../cloudquote-pricing-guardrails/SKILL.md`
- `../cloudquote-artifact-delivery/SKILL.md`

When the request supplies an RFP, RFQ, tender, SOW, or any unstructured requirements document instead of a specs file and source BOQ, follow `../cloudquote-rfp/SKILL.md` first to derive those two inputs, then return here.

## Inputs

Collect only missing required values:

- Customer specifications file
- Source-cloud BOQ file
- Target region
- Currency
- Scenario: `conservative`, `moderate`, `aggressive`, or `compare-all`
- Output `.xlsx` path
- Source provider: `aws`, `azure`, `gcp`, `github`, or `external`
- Target provider (`azure` compiles; `aws` and `gcp` currently support plan validation only)

Do not ask confirmation when defaults or prompt inputs already provide these values.

## Procedure

### Fast path (default)

For AWS-to-Azure requests with supplied input paths, run exactly one command without reading the files first:

```powershell
python scripts\run_pipeline.py --specs <specs> --aws-boq <boq> --output <output.xlsx> --region <region> --currency <currency> --scenario <scenario> --max-price-age-hours 24 --enable-web-search
```

The compiler normalizes inputs, creates the typed plan, applies executable pricing guardrails, resolves official sources, builds insights and Excel, verifies artifact integrity, and returns all final paths. Finish immediately using the artifact-delivery skill.

Do not inspect the workbook, summaries, normalized JSON, or quote plan after a successful command. Their hashes and formats are already verified by the compiler.

### Reviewed-plan path (only when needed)

Use this path only when the user asks for mapping review, required target mappings are absent, a non-default provider workflow is requested, or the inputs were derived from an RFP with unresolved assumptions.

1. Normalize the supplied files once:

```powershell
python scripts\parse_inputs.py --specs <specs> --aws-boq <boq> --output <output-base>.normalized.json
```

2. Create the provider-neutral plan skeleton:

```powershell
python scripts\quote_plan.py --normalized <output-base>.normalized.json --output <output-base>.plan-input.json --source-provider <source> --target-provider <target>
```

3. Inspect the normalized inputs and plan. Identify workloads, capacities, environments, licenses, SLA, RTO/RPO, growth, and ambiguous fields.
4. Apply provider mapping with agent reasoning. Update every plan line's `target`, `assumptions`, and `validations`. Never invent missing workload dimensions.
5. Apply the pricing guardrail skill before accepting any quantity-to-meter conversion. Put unresolved conflicts in each line's `validations` array.
6. Resolve cross-provider product equivalence with `python scripts\service_search.py <service or capability> --target-provider <target>` before mapping any line whose target product is unclear. When the result is `composite`, map one plan line per component, put the returned `[VALIDATE]` note in the line's `validations`, and never present the partial set as a like-for-like replacement. Add `--format csv --output <path>` when the breakdown must be delivered outside the workbook.
7. When official APIs and catalogs miss, use an MCP-backed search provider or reliable search API. Add only reviewed results to the line's `pricingEvidence` array with exact provider, service, SKU, region, currency, price type, meter, unit, unit price, retrieval time, and HTTPS evidence URL. Set `source` to `mcp-web` or `search-api` and `status` to `approved`. Never scrape Bing, DuckDuckGo, or other search-result HTML.
8. Run the artifact compiler with the exact reviewed plan and normalized input:

```powershell
python scripts\run_pipeline.py --specs <specs> --aws-boq <boq> --normalized-input <output-base>.normalized.json --plan <output-base>.plan-input.json --output <output.xlsx> --region <region> --currency <currency> --scenario <scenario> --max-price-age-hours 24 --enable-web-search
```

On Windows, if `python` is unavailable, locate Python with `Get-Command python, py` and use the resolved interpreter.

9. Trust returned paths; the compiler verifies hashes and artifact formats before completion.
10. Finish using the artifact-delivery skill.

## Performance rules

- Do not narrate normal workflow progress.
- Prefer one compiler invocation over multiple inspection or preparation calls.
- Do not inspect inputs before the fast path; executable validation owns routine checks.
- Do not dump JSON, workbook rows, mappings, or pricing explanations into chat.
- Do not rerun unchanged inputs. The compiler fingerprints inputs, options, mappings, and implementation.
- Batch independent file inspection and validation operations.
- Stop once the output files exist and are verified.
- Use typed, reviewed MCP/search-API evidence after official API and catalog misses. The compiler does not scrape search-engine HTML.

## Boundaries

- Scripts normalize, validate, price, and compile; they do not make unrecorded mapping decisions.
- Never silently calculate across incompatible source usage and target meter dimensions.
- Resolve product equivalence from the curated `mappings/service_equivalence.yaml` catalog rather than assuming a pricing API can answer it.
- Use official provider catalog adapters before reviewed search evidence. GitHub plans resolve from `https://github.com/pricing`.
- Do not claim AWS or GCP compilation support; their adapters currently validate plans only.
- Never modify customer input files.
- Keep generated engagement artifacts outside Git-tracked paths.
