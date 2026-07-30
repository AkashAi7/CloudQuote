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

Use the one-command fast path without pre-reading inputs or post-reading outputs. Use reviewed planning only when mappings are missing or explicitly requested. Return only links to the completed workbook, executive summary, structured summary, normalized inputs, and quote plan.
