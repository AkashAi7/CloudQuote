---
name: cloudquote-artifact-delivery
description: 'Deliver CloudQuote decisions and artifacts with concise readiness, eligibility, blockers and sharing controls. Use after triage, quote review, BOQ generation or proposal packaging, including partial results.'
user-invocable: false
---

# CloudQuote Artifact Delivery

Lead with the outcome and actual readiness, not "Completed" merely because files exist.
Use the compiler's returned readiness for compiled quotes; use explicit evidence-based
provisional status for non-compiled triage. Never infer release approval from a filename,
mode, successful build, price coverage, or absence of exceptions.

## Seller summary

Use this shape, omitting inapplicable fields and keeping it brief:

```markdown
**Readiness:** <actual status>; <mode>. **Eligibility:** <Pass / Fail / Unresolved>.

<Most important finding, material blocker or decision; impact and next owner if known.>

[Workbook](<actual URI>) | [Decision summary](<actual URI>)
```

For triage, return the decision insight, up to three material risks/questions and next
action; no workbook is required. For working estimates, label provisional/internal use,
identify unpriced coverage and do not imply final qualification or complete savings.
For release preparation, list missing approvals or state the recorded readiness;
sending remains a separate user-confirmed action.

## Requested artifacts and provenance

Return only requested files that actually exist. The quote plan, normalized inputs and
structured summary are audit drill-down artifacts, not mandatory clutter in every
seller response. Include a requirements matrix or derived specifications/BOQ when
requested for an RFP handoff; derive them from the same structured records.

Use returned workspace URIs in Scout after successful publication through workspace
tools; otherwise use the approved host's actual local artifact links. Never fabricate
paths, documents, downloads or sharing links. Use document skills for requested Word,
PowerPoint or other formats; compilation alone produces no such artifacts.

Customer documents should lead with the customer outcome and recommendation, then
scope/assumptions, architecture, qualification, costs, risks and sources. Spreadsheets
must distinguish source values from formulas and show material exceptions next to
totals. Keep internal battlecards, private commercial guidance and reviewer notes out
of customer-facing output.

## Partial work and recovery

If pricing or an artifact format is blocked, say exactly what is unavailable and why.
Offer existing useful analysis or independent completed artifacts as **partial/internal**,
not as a complete proposal. Preserve the last good version; expose the next input or
review owner needed to resume. Do not hide open clarifications only inside a file.
If nothing usable was produced, say so without linking empty or nonexistent artifacts.

## Release and sharing

Before release ensure current named requirements, architecture, qualification, BOQ,
pricing/reconciliation, compliance, commercial and customer-release approvals exist.
Review editorial consistency and competitive claims when present. Never record
agent-generated or placeholder approval as a human decision.

Before any tool call that sends, posts, grants access, uploads to a shared destination
or updates content visible to other people, show exact recipients/destination and
content, including files/access role if relevant. If content uses private data, warn
that it contains private information and request confirmation. Wait for explicit
approval before the outbound call; approval to generate is not approval to share.
Honor sensitivity labels and usage rights; do not publish classified data to an
unprotected destination even if a generic release gate says approved.

## Rules

- Avoid routine process narration, cache trivia and full JSON dumps.
- Show the highest-impact uncertainty, not every diagnostic line.
- Do not suppress material blockers to keep the response short.
- Do not claim a public-list estimate is a negotiated offer or a quote commitment.
- Never send or publish as an automatic consequence of successful generation.
