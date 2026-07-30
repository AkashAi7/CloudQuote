# CloudQuote

CloudQuote is a provider-extensible bill-of-quantities workspace for GitHub Copilot. The currently implemented workflow converts customer requirements and an AWS BOQ into an Azure BOQ with regional pricing, scenario comparisons, an Excel workbook, and machine-readable and chat-ready summaries.

The repository is intentionally provider-neutral so future workflows can generate and compare AWS, Azure, and Google Cloud BOQs under the same validation and reporting model.

## Copilot usage

Open this repository in a GitHub Copilot coding agent environment and select the `cloudquote` custom agent, or run the `cloudquote` prompt from `.github/prompts/cloudquote.prompt.md`.

The workflow is skill-driven:

- `cloudquote-boq` orchestrates input interpretation, mapping, and artifact generation.
- `cloudquote-pricing-guardrails` blocks unsupported unit conversions.
- `cloudquote-artifact-delivery` returns only the completed output files.

Agent decisions are persisted in a schema-validated `quote-plan.json` before compilation, so mappings and validation assumptions directly affect generated artifacts.

Routine AWS-to-Azure requests use a single-command fast path. The agent only opens the reviewed-plan workflow when mappings are missing or review is explicitly requested.

Provide:

- Customer specifications in YAML, JSON, or DOCX format
- AWS BOQ in CSV or XLSX format
- Azure region and currency
- Pricing scenario: `conservative`, `moderate`, `aggressive`, or `compare-all`

The generated output includes:

- An Excel workbook with mapping, costs, assumptions, executive summary, and validation tabs
- `summary.json` for structured consumption
- `executive_summary.md` for Copilot chat
- `quote-plan.json` as the auditable agent-to-compiler contract

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

The default Copilot workflow uses one compiler command and returns only artifact links. CSV parsing and HTTP dependencies are lazy-loaded, independent price lookups are bounded, validation-only lines skip network calls, and pricing-cache writes are batched.

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
