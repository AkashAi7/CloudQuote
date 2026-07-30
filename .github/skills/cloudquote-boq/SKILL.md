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

## Inputs

Collect only missing required values:

- Customer specifications file
- Source-cloud BOQ file
- Target region
- Currency
- Scenario: `conservative`, `moderate`, `aggressive`, or `compare-all`
- Output `.xlsx` path
- Source provider: `aws`, `azure`, `gcp`, `github`, or `external`
- Target provider (currently implemented: `azure`)

Do not ask confirmation when defaults or prompt inputs already provide these values.

## Procedure

### Fast path (default)

For AWS-to-Azure requests with supplied input paths, run exactly one command without reading the files first:

```powershell
python scripts\run_pipeline.py --specs <specs> --aws-boq <boq> --output <output.xlsx> --region <region> --currency <currency> --scenario <scenario> --max-price-age-hours 24
```

The compiler normalizes inputs, creates the typed plan, applies executable pricing guardrails, resolves official sources, builds insights and Excel, verifies artifact integrity, and returns all final paths. Finish immediately using the artifact-delivery skill.

Do not inspect the workbook, summaries, normalized JSON, or quote plan after a successful command. Their hashes and formats are already verified by the compiler.

### Reviewed-plan path (only when needed)

Use this path only when the user asks for mapping review, required target mappings are absent, or a non-default provider workflow is requested.

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
6. Run the artifact compiler with the exact reviewed plan and normalized input:

```powershell
python scripts\run_pipeline.py --specs <specs> --aws-boq <boq> --normalized-input <output-base>.normalized.json --plan <output-base>.plan-input.json --output <output.xlsx> --region <region> --currency <currency> --scenario <scenario> --max-price-age-hours 24
```

On Windows, if `python` is unavailable, locate Python with `Get-Command python, py` and use the resolved interpreter.

7. Trust returned paths; the compiler verifies hashes and artifact formats before completion.
8. Finish using the artifact-delivery skill.

## Performance rules

- Do not narrate normal workflow progress.
- Prefer one compiler invocation over multiple inspection or preparation calls.
- Do not inspect inputs before the fast path; executable validation owns routine checks.
- Do not dump JSON, workbook rows, mappings, or pricing explanations into chat.
- Do not rerun unchanged inputs. The compiler fingerprints inputs, options, mappings, and implementation.
- Batch independent file inspection and validation operations.
- Stop once the output files exist and are verified.
- Generic Bing/DDG estimates are disabled by default because they are slow and ambiguous. Use `--enable-web-search` only when the user explicitly requests unstructured estimates.

## Boundaries

- Scripts normalize, validate, price, and compile; they do not make unrecorded mapping decisions.
- Never silently calculate across incompatible source usage and target meter dimensions.
- Use official provider catalog adapters before generic web search. GitHub plans resolve from `https://github.com/pricing`.
- Do not claim unsupported target providers; the compiler currently implements only Azure.
- Never modify customer input files.
- Keep generated engagement artifacts outside Git-tracked paths.
