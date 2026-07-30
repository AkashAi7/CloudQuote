---
mode: agent
model: GPT-5.3-Codex
description: 'Generate CloudQuote BOQ artifacts and return only the completed files.'
---

Use the `cloudquote-boq` skill to generate BOQ artifacts.

Inputs:
- Specifications: `${input:specs_file}`
- Source BOQ: `${input:source_boq_file}`
- Source provider: `${input:source_provider=aws}`
- Target provider: `${input:target_provider=azure}`
- Target region: `${input:region=eastus}`
- Currency: `${input:currency=USD}`
- Scenario: `${input:scenario=compare-all}`
- Output workbook: `${input:output_file=engagements/sample/cloudquote.xlsx}`

Use the one-command fast path without pre-reading inputs or post-reading outputs. Official APIs and catalogs remain authoritative. Use reviewed planning when mappings are missing, explicitly requested, or approved MCP/search-API pricing evidence is needed. Store that evidence in each plan line's typed `pricingEvidence`; never scrape search-engine HTML. Return only links to the completed workbook, executive summary, structured summary, normalized inputs, and quote plan.
