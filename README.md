# CloudQuote

CloudQuote is a provider-extensible bill-of-quantities workspace for GitHub Copilot. The currently implemented workflow converts customer requirements and an AWS BOQ into an Azure BOQ with regional pricing, scenario comparisons, an Excel workbook, and machine-readable and chat-ready summaries.

The repository is intentionally provider-neutral so future workflows can generate and compare AWS, Azure, and Google Cloud BOQs under the same validation and reporting model.

## Copilot usage

Open this repository in a GitHub Copilot coding agent environment and select the `cloudquote` custom agent, or run the `cloudquote` prompt from `.github/prompts/cloudquote.prompt.md`.

The workflow is skill-driven:

- `cloudquote-boq` orchestrates input interpretation, mapping, and artifact generation.
- `cloudquote-pricing-guardrails` blocks unsupported unit conversions.
- `cloudquote-artifact-delivery` returns only the completed output files.

Provide:

- Customer specifications in YAML, JSON, or DOCX format
- AWS BOQ in CSV or XLSX format
- Azure region and currency
- Pricing scenario: `conservative`, `moderate`, `aggressive`, or `compare-all`

The generated output includes:

- An Excel workbook with mapping, costs, assumptions, executive summary, and validation tabs
- `summary.json` for structured consumption
- `executive_summary.md` for Copilot chat

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

Unchanged inputs and options reuse the existing artifacts through a content fingerprint, avoiding repeated parsing, pricing, and workbook generation.

## Pricing safety

The pipeline uses Azure Retail Prices API results with cache fallback. It marks unresolved mappings and incompatible usage-to-meter conversions as `[VALIDATE]` instead of producing unsupported estimates. Review the workbook's **Validation & Coverage** tab before using results for customer decisions.

Customer workbooks, engagement outputs, local price caches, and generated summaries are excluded from Git.
