import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List


SCHEMA_VERSION = "1.0"
SUPPORTED_PROVIDERS = {"aws", "azure", "gcp", "github", "external"}


class QuotePlanError(ValueError):
  pass


def _line_id(index: int, row: Dict[str, Any]) -> str:
  identity = json.dumps({
    "index": index,
    "service": row.get("Service", ""),
    "sku": row.get("Instance/SKU", ""),
    "capacity": row.get("Capacity", ""),
  }, sort_keys=True)
  return f"line-{index + 1:04d}-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:8]}"


def build_quote_plan(
  normalized: Dict[str, Any],
  source_provider: str = "aws",
  target_provider: str = "azure",
) -> Dict[str, Any]:
  lines: List[Dict[str, Any]] = []
  for index, row in enumerate(normalized.get("aws_boq", [])):
    lines.append({
      "id": _line_id(index, row),
      "source": {
        "provider": source_provider,
        "service": str(row.get("Service", "")),
        "sku": str(row.get("Instance/SKU", "")),
        "quantity": row.get("Quantity", 1),
        "unit": str(row.get("Source Unit", "")),
        "capacity": str(row.get("Capacity", "")),
        "monthlyCost": row.get("Monthly", 0),
      },
      "target": {
        "provider": target_provider,
        "service": str(row.get("Azure Service", "")),
        "sku": str(row.get("Azure SKU", "")),
      },
      "assumptions": [],
      "validations": [],
    })
  return {
    "schemaVersion": SCHEMA_VERSION,
    "sourceProvider": source_provider,
    "targetProvider": target_provider,
    "lines": lines,
  }


def validate_quote_plan(plan: Dict[str, Any]) -> None:
  if plan.get("schemaVersion") != SCHEMA_VERSION:
    raise QuotePlanError(f"Unsupported quote plan schemaVersion: {plan.get('schemaVersion')!r}")
  for field in ["sourceProvider", "targetProvider"]:
    provider = str(plan.get(field, "")).lower()
    if provider not in SUPPORTED_PROVIDERS:
      raise QuotePlanError(f"Unsupported {field}: {provider!r}")
  lines = plan.get("lines")
  if not isinstance(lines, list) or not lines:
    raise QuotePlanError("Quote plan must contain at least one line")
  seen_ids = set()
  for index, line in enumerate(lines):
    if not isinstance(line, dict):
      raise QuotePlanError(f"Line {index + 1} must be an object")
    line_id = str(line.get("id", ""))
    if not line_id or line_id in seen_ids:
      raise QuotePlanError(f"Line {index + 1} has a missing or duplicate id")
    seen_ids.add(line_id)
    for side in ["source", "target"]:
      if not isinstance(line.get(side), dict):
        raise QuotePlanError(f"Line {line_id} is missing {side}")
    validations = line.get("validations", [])
    assumptions = line.get("assumptions", [])
    if not isinstance(validations, list) or not all(isinstance(item, str) for item in validations):
      raise QuotePlanError(f"Line {line_id} validations must be a string array")
    if not isinstance(assumptions, list) or not all(isinstance(item, str) for item in assumptions):
      raise QuotePlanError(f"Line {line_id} assumptions must be a string array")


def apply_quote_plan(normalized: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
  validate_quote_plan(plan)
  rows = normalized.get("aws_boq", [])
  lines = plan["lines"]
  if len(rows) != len(lines):
    raise QuotePlanError(f"Quote plan has {len(lines)} lines but normalized BOQ has {len(rows)} rows")
  output = copy.deepcopy(normalized)
  output["quote_plan"] = plan
  for row, line in zip(output["aws_boq"], lines):
    source = line["source"]
    target = line["target"]
    row.update({
      "Quote Plan Line ID": line["id"],
      "Service": str(source.get("service", row.get("Service", ""))),
      "Instance/SKU": str(source.get("sku", row.get("Instance/SKU", ""))),
      "Quantity": source.get("quantity", row.get("Quantity", 1)),
      "Source Unit": str(source.get("unit", row.get("Source Unit", ""))),
      "Capacity": str(source.get("capacity", row.get("Capacity", ""))),
      "Monthly": source.get("monthlyCost", row.get("Monthly", 0)),
      "Azure Service": str(target.get("service", row.get("Azure Service", ""))),
      "Azure SKU": str(target.get("sku", row.get("Azure SKU", ""))),
      "Mapping Assumptions": list(line.get("assumptions", [])),
      "Plan Validations": list(line.get("validations", [])),
      "Source Provider": str(source.get("provider", plan["sourceProvider"])),
      "Target Provider": str(target.get("provider", plan["targetProvider"])),
    })
  return output


def load_quote_plan(path: Path) -> Dict[str, Any]:
  plan = json.loads(path.read_text(encoding="utf-8"))
  validate_quote_plan(plan)
  return plan


def save_quote_plan(plan: Dict[str, Any], path: Path) -> None:
  validate_quote_plan(plan)
  path.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def main() -> None:
  parser = argparse.ArgumentParser(description="Create a provider-neutral CloudQuote plan skeleton")
  parser.add_argument("--normalized", required=True)
  parser.add_argument("--output", required=True)
  parser.add_argument("--source-provider", default="aws", choices=sorted(SUPPORTED_PROVIDERS))
  parser.add_argument("--target-provider", default="azure", choices=sorted(SUPPORTED_PROVIDERS))
  args = parser.parse_args()

  normalized = json.loads(Path(args.normalized).read_text(encoding="utf-8"))
  plan = build_quote_plan(normalized, args.source_provider, args.target_provider)
  save_quote_plan(plan, Path(args.output))
  print(json.dumps({"quotePlan": args.output, "lines": len(plan["lines"])}, indent=2))


if __name__ == "__main__":
  main()