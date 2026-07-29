---
mode: ask
model: GPT-5.3-Codex
description: Run AWS to Azure BOQ generation with live Azure pricing and Excel output.
---

Generate an Azure BOQ from customer specs and AWS BOQ with pricing scenario `${input:scenario=compare-all}`.

Inputs:
- Specs file: `${input:specs_file}`
- AWS BOQ file: `${input:aws_boq_file}`
- Region: `${input:region=eastus}`
- Currency: `${input:currency=USD}`
- Output workbook: `${input:output_file=engagements/sample/output/azure_boq.xlsx}`

Requirements:
- Follow normalize -> parse -> map -> live pricing -> scenario levers -> workbook flow.
- Use Azure Retail Prices API values and mark [VALIDATE] if missing.
- Produce all workbook tabs (Mapping & Azure BOQ, Cost Comparison, Assumptions & Levers, Executive Summary, Validation & Coverage).
- Generate both machine-readable and chat-ready outputs (`summary.json` and `executive_summary.md`).
- Return a concise Copilot-UI decision summary with recommendation, confidence, top drivers, and blockers.
