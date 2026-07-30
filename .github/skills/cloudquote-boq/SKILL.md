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

7. Trust `reused: true` only when returned by the compiler; it verifies hashes and artifact formats.
8. Verify the five returned paths exist. Inspect detailed contents only when generation fails or the user explicitly asks for analysis.
9. Finish using the artifact-delivery skill.

## Performance rules

- Do not narrate normal workflow progress.
- Normalize once and reuse the normalized artifact during compilation.
- Do not dump JSON, workbook rows, mappings, or pricing explanations into chat.
- Do not rerun unchanged inputs. The compiler fingerprints inputs, options, mappings, and implementation.
- Batch independent file inspection and validation operations.
- Stop once the output files exist and are verified.

## Boundaries

- Scripts normalize, validate, price, and compile; they do not make unrecorded mapping decisions.
- Never silently calculate across incompatible source usage and target meter dimensions.
- Use official provider catalog adapters before generic web search. GitHub plans resolve from `https://github.com/pricing`.
- Do not claim unsupported target providers; the compiler currently implements only Azure.
- Never modify customer input files.
- Keep generated engagement artifacts outside Git-tracked paths.
