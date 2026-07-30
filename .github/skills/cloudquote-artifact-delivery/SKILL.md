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

## Rules

- Do not include progress, methodology, pricing commentary, tables, JSON, recommendations, or next steps.
- Do not mention cache hits.
- Do not repeat validation details; they belong in the workbook and summaries.
- Include only files that exist.
- If generation is blocked, state the blocker in one sentence and list no incomplete artifacts.
