---
name: cloudquote-boq
description: 'Generate cloud BOQ artifacts from customer specifications and a source-cloud bill of quantities. Use for CloudQuote, AWS-to-Azure BOQ, cloud pricing comparison, TCO scenarios, workbook generation, or quote-ready deliverables.'
argument-hint: '<specs file> <source BOQ file> [region] [currency] [scenario]'
user-invocable: true
---

# CloudQuote BOQ

Own the BOQ workflow. Use agent judgment for input interpretation, cloud mapping, assumptions, and validation. Use repository code only as the deterministic artifact compiler.

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

Do not ask confirmation when defaults or prompt inputs already provide these values.

## Procedure

1. Inspect the supplied files using structured file tools where available.
2. Identify source provider, workloads, capacities, environments, licenses, SLA, RTO/RPO, growth, and ambiguous fields.
3. Apply provider mapping with agent reasoning. Never invent missing workload dimensions.
4. Apply the pricing guardrail skill before accepting any quantity-to-meter conversion.
5. Run the artifact compiler once:

```powershell
python scripts\run_pipeline.py --specs <specs> --aws-boq <boq> --output <output.xlsx> --region <region> --currency <currency> --scenario <scenario>
```

On Windows, if `python` is unavailable, locate Python with `Get-Command python, py` and use the resolved interpreter.

6. Trust `reused: true` as a completed cache hit. Do not regenerate or reread unchanged outputs.
7. Verify the four returned paths exist. Inspect detailed contents only when generation fails or the user explicitly asks for analysis.
8. Finish using the artifact-delivery skill.

## Performance rules

- Do not narrate normal workflow progress.
- Do not run separate normalize, pricing, and workbook commands when the pipeline command can complete the request.
- Do not dump JSON, workbook rows, mappings, or pricing explanations into chat.
- Do not rerun unchanged inputs. The compiler fingerprints inputs, options, mappings, and implementation.
- Batch independent file inspection and validation operations.
- Stop once the output files exist and are verified.

## Boundaries

- Scripts compile artifacts; they do not replace agent judgment.
- Never silently calculate across incompatible source usage and target meter dimensions.
- Never modify customer input files.
- Keep generated engagement artifacts outside Git-tracked paths.
