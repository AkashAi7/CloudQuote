---
name: cloudquote-rfp
description: 'Turn an RFP, RFQ, tender, or unstructured requirements document into CloudQuote inputs and a priced, quote-ready response pack. Use when the customer supplies an RFP/RFQ/SOW/tender document instead of a structured specs file and source BOQ.'
argument-hint: '<rfp file> [region] [currency] [scenario] [output.xlsx]'
user-invocable: true
---

# CloudQuote RFP Intake

Convert an RFP into the two structured inputs the BOQ compiler requires, then run the normal BOQ workflow and return a priced response pack.

## Required companion skills

- `../cloudquote-pricing-guardrails/SKILL.md`
- `../cloudquote-boq/SKILL.md`
- `../cloudquote-artifact-delivery/SKILL.md`

## Accepted inputs

RFP text in `.md`, `.txt`, `.pdf`, `.docx`, `.xlsx`, or pasted chat content. For binary formats, convert to markdown first (`markitdown` tool, or `pandas` for workbook sheets). Never modify the customer's original file.

## Procedure

1. **Extract.** Read the RFP once. Capture only what is stated: workloads, environments, vCPU/memory, storage capacity and class, databases and HA, network egress and private connectivity, regions and DR, SLA, RTO/RPO, growth, owned licenses, term, currency, and commercial constraints.

2. **Write derived inputs** into the engagement folder, never over the source:

   - `<output-base>.specs.yaml` — same schema as `samples/customer_specs.yaml`.
   - `<output-base>.boq.csv` — same header as `samples/aws_boq.csv`. Use it as the quantity ledger for the RFP scope. Leave `Unit Price`, `Monthly`, `Annual` empty when the RFP states no incumbent pricing; the compiler resolves target prices.
   - When the RFP names products from a provider other than the target (for example an Azure-worded RFP quoted on AWS), resolve each product with `python scripts\service_search.py <product> --target-provider <target>`. Emit one BOQ line per returned component when the equivalence is `composite`, and carry the returned `[VALIDATE]` note into the requirements matrix.
   - Set `Service`/`Instance/SKU` from the RFP's own wording. If the RFP is provider-neutral, express the line by capacity (vCPU/GB/requests) and record the sizing basis as an assumption.

3. **Write the requirements matrix** `<output-base>.rfp-requirements.md` with one row per extracted requirement:

   | ID | RFP requirement | Source location | BOQ line(s) | Assumption | Status |

   `Status` is `covered`, `assumed`, `clarify`, or `out-of-scope`. Every quantity that the RFP does not state must be `assumed` or `clarify` — never silently invented.

4. **Gate on ambiguity.** If any priced dimension is unknown (request rates, read/write mix, retention, redundancy, peak concurrency, license ownership), record it in the matrix and keep the line as `[VALIDATE]` under the pricing-guardrail skill rather than guessing a number to complete a total.

5. **Compile.** Run the BOQ skill's fast path with the derived files:

```powershell
python scripts\run_pipeline.py --specs <output-base>.specs.yaml --aws-boq <output-base>.boq.csv --output <output.xlsx> --region <region> --currency <currency> --scenario <scenario> --max-price-age-hours 24
```

   Use `compare-all` when the RFP does not state a commitment posture; reserved/commitment language in the RFP maps to `moderate` or `aggressive`.

6. **Deliver** with the artifact-delivery skill, including the requirements matrix.

## Boundaries

- One requirement, one traceable row. Do not merge unrelated requirements into a single BOQ line.
- Do not answer non-priceable RFP sections (legal, compliance attestations, references) with generated claims; mark them `out-of-scope` for this workflow.
- Do not restate RFP text in chat. The matrix is the deliverable.
- Keep derived inputs and artifacts in the engagement folder, outside Git-tracked paths.
