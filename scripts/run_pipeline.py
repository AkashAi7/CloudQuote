import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from build_workbook import build_workbook
from parse_inputs import normalize_inputs


def _render_executive_summary(summary: dict) -> str:
  lines: list[str] = []
  lines.append("# AWS to Azure BOQ Executive Summary")
  lines.append("")
  lines.append("## Decision Snapshot")
  lines.append(f"- Recommended scenario: {summary.get('recommendedScenario', 'N/A')}")
  lines.append(f"- Decision confidence: {summary.get('decisionConfidence', 'N/A')}")
  lines.append(f"- Validation blockers: {summary.get('validateCount', 0)}")
  lines.append("")

  totals = summary.get("scenarioTotalsMonthly", {})
  savings = summary.get("scenarioSavings", {})
  lines.append("## Monthly Cost View")
  lines.append(f"- AWS baseline: {totals.get('aws', 'N/A')} {summary.get('currency', 'USD')}")
  for scenario_name in ["conservative", "moderate", "aggressive"]:
    if scenario_name in totals:
      lines.append(f"- Azure {scenario_name}: {totals[scenario_name]} {summary.get('currency', 'USD')}")
      sv = savings.get(scenario_name)
      if isinstance(sv, dict):
        lines.append(f"  Savings vs AWS: {sv.get('amount', 'N/A')} ({sv.get('percent', 'N/A')}%)")
      elif sv:
        lines.append(f"  Savings vs AWS: {sv}")
  lines.append("")

  source_counts = summary.get("sourceCounts", {})
  if source_counts:
    lines.append("## Price Source Coverage")
    lines.append(
      f"- API: {source_counts.get('API', 0)}, WEB: {source_counts.get('WEB', 0)}, CACHE: {source_counts.get('CACHE', 0)}, NONE: {source_counts.get('NONE', 0)}"
    )
    lines.append("")

  lines.append("## Top Positive Cost Drivers")
  positives = summary.get("topDriversPositive", [])
  if positives:
    for item in positives[:3]:
      lines.append(
        f"- {item.get('line', '')}: AWS {item.get('aws', 0)} -> Azure {item.get('azure', 0)} (delta {item.get('delta', 0)})"
      )
  else:
    lines.append("- None")
  lines.append("")

  lines.append("## Top Negative Cost Drivers")
  negatives = summary.get("topDriversNegative", [])
  if negatives:
    for item in negatives[:3]:
      lines.append(
        f"- {item.get('line', '')}: AWS {item.get('aws', 0)} -> Azure {item.get('azure', 0)} (delta {item.get('delta', 0)})"
      )
  else:
    lines.append("- None")
  lines.append("")

  lines.append("## Risks and Validation")
  missing = summary.get("missingSpecFields", [])
  if missing:
    lines.append(f"- Missing/ambiguous specs: {', '.join(missing)}")
  else:
    lines.append("- Missing/ambiguous specs: none")
  if summary.get("validationItems"):
    lines.append("- Pricing validation required for one or more lines; review the workbook tab 'Validation & Coverage'.")
  else:
    lines.append("- Pricing validation required: none")

  return "\n".join(lines) + "\n"


def main() -> None:
  parser = argparse.ArgumentParser(description="Run end-to-end AWS-to-Azure BOQ workbook generation")
  parser.add_argument("--specs", required=True)
  parser.add_argument("--aws-boq", required=True)
  parser.add_argument("--output", required=True)
  parser.add_argument("--region", default="eastus")
  parser.add_argument("--currency", default="USD")
  parser.add_argument("--scenario", default="compare-all", choices=["compare-all", "conservative", "moderate", "aggressive"])
  args = parser.parse_args()

  out_path = Path(args.output)
  out_path.parent.mkdir(parents=True, exist_ok=True)
  normalized_path = out_path.parent / "normalized.json"

  normalized = normalize_inputs(Path(args.specs), Path(args.aws_boq), normalized_path)

  pricing_date = datetime.now(timezone.utc).date().isoformat()
  summary = build_workbook(
    normalized=normalized,
    pricing_meta={"region": args.region, "currency": args.currency, "pricingDate": pricing_date},
    output_path=out_path,
    scenario=args.scenario,
  )

  summary_path = out_path.parent / "summary.json"
  summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
  executive_summary_path = out_path.parent / "executive_summary.md"
  executive_summary_path.write_text(_render_executive_summary(summary), encoding="utf-8")
  print(json.dumps({
    "workbook": str(out_path),
    "normalized": str(normalized_path),
    "summary": str(summary_path),
    "executiveSummary": str(executive_summary_path),
  }, indent=2))


if __name__ == "__main__":
  main()
