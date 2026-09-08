---
mode: agent
model: GPT-5.3-Codex
description: 'Triage a cloud deal or build a reviewed estimate with visible readiness and next decisions.'
---

Use the CloudQuote agent and select the skill for the seller's job.

Inputs:
- Seller's question and available documents: `${input:request}`
- Mode if known: `${input:mode}`

Resolve unfilled placeholders by asking the user; never treat placeholder text as a
filename. Do not require specs, a source bill or an output workbook for quick triage.
Infer supplied region, currency and commercial terms from the request/documents;
ask only for missing material values rather than defaulting to eastus, USD or a
commitment bundle.

For RFPs, qualification, quote critique or discovery follow `cloudquote-rfp`.
For scoped structured pricing follow `cloudquote-boq` and its companions. Preserve
the safe one-command internal-estimate path; require a reviewed plan for RFP-derived
inputs, material assumptions, changed mappings or submission-ready preparation.
Use official price evidence and typed `pricingEvidence`; never scrape search-engine
HTML. Return a concise readiness/eligibility summary, the highest-impact decision,
and only requested, available artifact links. Always expose material blockers and
obtain explicit confirmation after preview before sharing externally.
