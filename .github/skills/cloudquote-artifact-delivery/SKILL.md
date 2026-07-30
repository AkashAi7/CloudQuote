---
name: cloudquote-artifact-delivery
description: 'Return completed CloudQuote files without analysis or narration. Use after BOQ generation, workbook creation, pricing comparison, or any CloudQuote operation that produces downloadable artifacts.'
user-invocable: false
---

# CloudQuote Artifact Delivery

After successful generation, respond only with links to the final files.

Use this exact shape:

```markdown
Completed:
- [CloudQuote workbook](<workbook path>)
- [Executive summary](<executive summary path>)
- [Structured summary](<summary JSON path>)
- [Normalized inputs](<normalized JSON path>)
- [Quote plan](<quote plan JSON path>)
```

## RFP/RFQ/tender runs

When the run originated from an RFP, RFQ, tender, or SOW, the derived inputs are
deliverables too: the bidder has to defend where every priced line came from.
Append these entries when the files exist:

```markdown
- [Requirements matrix](<output base>.rfp-requirements.md)
- [Derived specifications](<derived specs YAML path>)
- [Derived BOQ](<derived BOQ CSV path>)
```

## Rules

- Do not include progress, methodology, pricing commentary, tables, JSON, recommendations, or next steps.
- Do not mention cache hits.
- Do not repeat validation details; they belong in the workbook and summaries.
- Include only files that exist.
- If generation is blocked, state the blocker in one sentence and list no incomplete artifacts.
- Unresolved clarifications stay in the requirements matrix; do not restate them here.
