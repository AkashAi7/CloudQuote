"""Optional seller review: audit metadata, not cryptographic identity verification."""

import argparse
import copy
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from input_integrity import source_binding_issues


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "opportunity-review.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
GATES = tuple(SCHEMA["$defs"]["gate"]["properties"]["id"]["enum"])
MODES = tuple(SCHEMA["properties"]["mode"]["enum"])
PLAN_ROW_FIELDS = ("Service", "Instance/SKU", "Quantity", "Source Unit", "Capacity", "Monthly",
                   "Azure Service", "Azure SKU")


class ReviewError(ValueError):
  pass


def _validate_schema(value, schema, path="opportunityReview"):
  """Execute the deliberately small JSON Schema vocabulary used by this contract."""
  if "$ref" in schema:
    return _validate_schema(value, SCHEMA["$defs"][schema["$ref"].split("/")[-1]], path)
  types = schema.get("type", [])
  types = [types] if isinstance(types, str) else types
  predicates = {
    "object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str), "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v),
  }
  if types and not any(predicates[t](value) for t in types):
    raise ReviewError(f"{path}: expected {' or '.join(types)} (numbers must be finite, not booleans)")
  if "const" in schema and value != schema["const"]:
    raise ReviewError(f"{path}: expected {schema['const']!r}")
  if "enum" in schema and value not in schema["enum"]:
    raise ReviewError(f"{path}: choose one of {', '.join(schema['enum'])}")
  if isinstance(value, dict):
    for key in schema.get("required", []):
      if key not in value:
        raise ReviewError(f"{path}.{key}: required field missing")
    properties = schema.get("properties", {})
    for key, item in value.items():
      if key not in properties and schema.get("additionalProperties") is False:
        raise ReviewError(f"{path}.{key}: unknown field")
      if key in properties:
        _validate_schema(item, properties[key], f"{path}.{key}")
  elif isinstance(value, list):
    if schema.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
      raise ReviewError(f"{path}: duplicate references")
    for index, item in enumerate(value):
      _validate_schema(item, schema.get("items", {}), f"{path}[{index}]")
  elif isinstance(value, str):
    if len(value) < schema.get("minLength", 0) or ("pattern" in schema and not re.search(schema["pattern"], value)):
      raise ReviewError(f"{path}: nonempty text or valid digest required")
    if schema.get("format") == "date-time":
      try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if "T" not in value or parsed.tzinfo is None:
          raise ValueError()
      except ValueError as exc:
        raise ReviewError(f"{path}: use an ISO-8601 timestamp with timezone") from exc
      if parsed > datetime.now(timezone.utc):
        raise ReviewError(f"{path}: confirmation cannot be in the future")
  elif isinstance(value, (int, float)) and not isinstance(value, bool):
    for key, invalid in [("minimum", lambda n: value < n), ("maximum", lambda n: value > n),
                         ("exclusiveMinimum", lambda n: value <= n)]:
      if key in schema and invalid(schema[key]):
        raise ReviewError(f"{path}: violates {key} {schema[key]}")


def _digest(value):
  try:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
  except (ValueError, TypeError) as exc:
    raise ReviewError(f"Cannot bind baseline: non-JSON or non-finite value ({exc})") from exc
  return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def baseline_for(plan, context, normalized=None):
  # Exclude generated per-row annotations; retain specs, meter pins and other pricing inputs.
  inputs = copy.deepcopy(normalized) if normalized is not None else None
  if inputs is not None:
    inputs["reviewSourceRows"] = source_rows_for(normalized)
    inputs.pop("quote_plan", None)
    inputs.pop("opportunityStatus", None)
    for row in inputs.get("aws_boq", []):
      for key in ("Quote Plan Line ID", "Mapping Assumptions", "Plan Validations", "Pricing Evidence",
                  "Source Provider", "Target Provider", "Review Assumptions"):
        row.pop(key, None)
      # Plan-owned fields are bound by planDigest; raw originals may differ after apply_quote_plan.
      for key in PLAN_ROW_FIELDS:
        row.pop(key, None)
  return {
    "planDigest": _digest({k: v for k, v in plan.items() if k != "opportunityReview"}),
    "inputsDigest": _digest(inputs) if inputs is not None else None,
    "context": dict(context),
  }


def source_rows_for(normalized):
  rows = [{key: row[key] for key in PLAN_ROW_FIELDS if key in row} for row in normalized.get("aws_boq", [])]
  snapshot = normalized.get("reviewSourceRows")
  if snapshot is None:
    return rows
  # A generated normalized file may be resumed, but edited effective rows must not reuse
  # its old source snapshot to pass a review binding check.
  old_plan = normalized.get("quote_plan", {})
  from quote_plan import effective_plan_fields
  expected = [effective_plan_fields(row, line) for row, line in zip(snapshot, old_plan.get("lines", []))]
  return copy.deepcopy(snapshot) if rows == expected else rows


def review_digest(review):
  content = copy.deepcopy(review)
  content.pop("gates")
  for assumption in content["assumptions"]:
    assumption.pop("approval", None)
    assumption.pop("status", None)
  return _digest(content)


def _index(records, label):
  result = {}
  for record in records:
    if record["id"] in result:
      raise ReviewError(f"{label}: duplicate id {record['id']!r}")
    result[record["id"]] = record
  return result


def _relations(records, label, fields):
  replacements = {}
  for key, record in records.items():
    if all(field in record for field in ("supersedes", "amends")):
      raise ReviewError(f"{label} {key}: choose supersedes OR amends, not both")
    for field in fields:
      target = record.get(field)
      if target is None:
        continue
      if target not in records:
        raise ReviewError(f"{label} {key}.{field}: dangling reference {target!r}")
      if field == "supersedes":
        if target in replacements:
          raise ReviewError(f"{label} {target}: ambiguous replacement by {replacements[target]} and {key}")
        replacements[target] = key
  def visit(key, ancestors):
    if key in ancestors:
      raise ReviewError(f"{label}: cycle involving {key}")
    for field in fields:
      if field in records[key]:
        visit(records[key][field], ancestors | {key})
  for key in records:
    visit(key, set())
  return replacements


def validate_review(plan):
  if "opportunityReview" not in plan:
    return
  review = plan["opportunityReview"]
  _validate_schema(review, SCHEMA)
  documents = _index(review["documents"], "documents")
  requirements = _index(review["requirements"], "requirements")
  assumptions = _index(review["assumptions"], "assumptions")
  _index(review["gates"], "gates")
  replaced_documents = _relations(documents, "document", ("supersedes", "amends"))
  replaced_requirements = _relations(requirements, "requirement", ("supersedes",))
  line_ids = {line["id"] for line in plan["lines"]}
  for key, requirement in requirements.items():
    document = requirement["source"]["documentId"]
    if document not in documents:
      raise ReviewError(f"Requirement {key}: dangling source document {document!r}")
    if key not in replaced_requirements and document in replaced_documents:
      raise ReviewError(f"Requirement {key}: active requirement on superseded document {document}; explicitly replace it")
    if requirement["qualification"] in ("pass", "fail") and not requirement["evidence"]:
      raise ReviewError(f"Requirement {key}: {requirement['qualification']} requires actual evidence")
    if requirement["lineIds"] and "nonPricedJustification" in requirement:
      raise ReviewError(f"Requirement {key}: choose lineIds OR nonPricedJustification")
    if ("weight" in requirement) != ("score" in requirement):
      raise ReviewError(f"Requirement {key}: score and weight must be supplied together")
    if "score" in requirement and requirement["priority"] != "scored":
      raise ReviewError(f"Requirement {key}: only scored requirements may have a score")
  for label, records in (("Requirement", requirements), ("Assumption", assumptions)):
    for key, record in records.items():
      unknown = set(record["lineIds"]) - line_ids
      if unknown:
        raise ReviewError(f"{label} {key}: dangling plan line references {', '.join(sorted(unknown))}")
      if label == "Assumption" and record["material"] and not record["lineIds"]:
        raise ReviewError(f"Material assumption {key}: affected lineIds must not be empty")
  for record in review["assumptions"] + review["gates"]:
    if record["status"] == "approved" and "approval" not in record:
      raise ReviewError(f"{record['id']}: approved status requires named confirmation metadata; wording is not approval")


def _approval_current(record, digest):
  return record["status"] == "approved" and record.get("approval", {}).get("reviewDigest") == digest


def evaluate_review(plan, context, normalized=None, *, pricing_blockers=0, missing_fields=(), compiled=False):
  validate_review(plan)
  review = plan.get("opportunityReview")
  source_issues = source_binding_issues(normalized)
  from quote_plan import effective_plan_fields, source_monthly_cost
  rows = (normalized or {}).get("aws_boq", [])
  missing_costs = [
    line["id"] for index, line in enumerate(plan["lines"])
    if source_monthly_cost(effective_plan_fields(rows[index] if index < len(rows) else {}, line)) is None
  ]
  comparison_status = {
    "incumbentBaselineComplete": bool(plan["lines"]) and not missing_costs,
    "missingIncumbentCostLineIds": missing_costs,
    "comparisonLimitations": ["Incumbent costs unknown; target-only estimate, no qualified savings or cost drivers"] if missing_costs else [],
  }
  if review is None:
    return {
      "mode": "working-estimate", "eligibility": "Not reviewed",
      "readiness": "Not reviewed / internal estimate", "releaseReady": False,
      "baselineCurrent": False, "blockingReasons": ["Opportunity review not supplied"],
      "nextAction": "Create and complete an opportunity review", "owner": None,
      "coverage": {"requirements": 0, "traced": 0, "untraced": 0, "mappedLines": 0},
      "approvals": {gate: "missing" for gate in GATES}, "blockedLineIds": [],
      "assumptionApprovals": {}, "qualifiedComparison": False, "weightedScore": None,
      "sourceBindingIssues": source_issues, **comparison_status,
    }
  current_baseline = baseline_for(plan, context, normalized)
  binding_required = review["mode"] != "quick-triage"
  current = review["baseline"] == current_baseline and not (binding_required and source_issues)
  digest = review_digest(review)
  replaced = {r["supersedes"] for r in review["requirements"] if "supersedes" in r}
  active = [r for r in review["requirements"] if r["id"] not in replaced]
  mandatory = [r for r in active if r["priority"] == "mandatory"]
  eligibility = ("Fail" if any(r["qualification"] == "fail" for r in mandatory) else
                 "Unresolved" if not active or not review["baselineComplete"] or
                 any(r["qualification"] == "unresolved" for r in mandatory) else "Pass")
  if not current and eligibility != "Fail":
    eligibility = "Unresolved"
  reasons = []
  if binding_required:
    reasons.extend(source_issues)
  if not current:
    reasons.append("Review baseline is stale: rebind, re-review and explicitly reapprove")
  if not review["baselineComplete"] or not active:
    reasons.append("Requirement baseline is empty or incomplete")
  if eligibility != "Pass":
    reasons.append(f"Mandatory eligibility: {eligibility}")
  untraced = [r for r in active if not r["lineIds"] and not r.get("nonPricedJustification")]
  if untraced:
    reasons.append("Requirements need line mapping or non-priced justification: " + ", ".join(r["id"] for r in untraced))
  blocked = set()
  pending = []
  assumption_approvals = {}
  for assumption in review["assumptions"]:
    approved = current and _approval_current(assumption, digest)
    assumption_approvals[assumption["id"]] = (
      "approved" if approved else "stale" if assumption["status"] == "approved" else assumption["status"]
    )
    if assumption["material"] and not approved:
      blocked.update(assumption["lineIds"])
      reasons.append(f"Material assumption {assumption['id']} v{assumption['version']} needs current approval")
      pending.append(assumption)
  if not current:
    # We cannot attribute arbitrary baseline edits to the old assumptions safely.
    blocked.update(line["id"] for line in plan["lines"])
  gates = {g["id"]: g for g in review["gates"]}
  approvals = {
    gate: ("approved" if current and gate in gates and _approval_current(gates[gate], digest) else
           "stale" if gates.get(gate, {}).get("status") == "approved" else gates.get(gate, {}).get("status", "missing"))
    for gate in GATES
  }
  missing_gates = [gate for gate, status in approvals.items() if status != "approved"]
  if missing_gates:
    reasons.append("Release gates need approval: " + ", ".join(missing_gates))
  if pricing_blockers:
    reasons.append(f"Pricing validation blockers: {pricing_blockers}")
  if missing_fields:
    reasons.append("Missing/ambiguous specs: " + ", ".join(str(f) for f in missing_fields))
  if not compiled:
    reasons.append("Pricing/reconciliation has not been compiled")
  release = review["mode"] == "submission-ready" and not reasons
  readiness = ("Release-ready" if release else "Quick triage / not priced" if review["mode"] == "quick-triage" else
               "Submission blocked / draft" if review["mode"] == "submission-ready" else
               "Working estimate / draft")
  pending += [r for r in active if r["qualification"] != "pass"]
  pending += [gates[g] for g in missing_gates if g in gates]
  next_item = pending[0] if pending else {}
  scored = [r for r in active if "score" in r]
  max_weight = max((r["weight"] for r in scored), default=1)
  weighted_score = (sum(r["score"] * (r["weight"] / max_weight) for r in scored) /
                    sum(r["weight"] / max_weight for r in scored)) if scored else None
  return {
    "mode": review["mode"], "eligibility": eligibility, "readiness": readiness, "releaseReady": release,
    "baselineCurrent": current, "blockingReasons": reasons,
    "nextAction": next_item.get("nextAction", reasons[0] if reasons else "Review draft before any customer sharing"),
    "owner": next_item.get("owner"),
    "coverage": {"requirements": len(active), "traced": len(active) - len(untraced), "untraced": len(untraced),
                 "mappedLines": len({line for r in active for line in r["lineIds"]})},
    "approvals": approvals, "assumptionApprovals": assumption_approvals, "blockedLineIds": sorted(blocked),
    "qualifiedComparison": comparison_status["incumbentBaselineComplete"] and eligibility == "Pass" and current and not blocked and not untraced and not pricing_blockers and not missing_fields and compiled,
    "weightedScore": weighted_score,
    "sourceBindingIssues": source_issues, **comparison_status,
  }


def prepare_review_inputs(normalized, context):
  """Reapply plan-owned fields and enforce blockers even for direct workbook invocation."""
  from quote_plan import apply_quote_plan, build_quote_plan, validate_quote_plan
  if normalized.get("quote_plan") is not None:
    return apply_quote_plan(normalized, normalized["quote_plan"], context)
  output = copy.deepcopy(normalized)
  output["quote_plan"] = build_quote_plan(normalized)
  validate_quote_plan(output["quote_plan"])
  return output


def append_status_sheet(workbook, status, review=None):
  sheet = workbook.create_sheet("Opportunity Review")
  sheet.append(["Status field", "Value"])
  for key, value in status.items():
    sheet.append([key, json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value])
  if review is not None:
    for category in ("documents", "requirements", "assumptions", "gates"):
      sheet.append([category, "Audit records (approval metadata is not identity verification)"])
      for record in review[category]:
        sheet.append([record["id"], json.dumps(record, ensure_ascii=False)])


def template_review(plan, context, mode="working-estimate", normalized=None):
  return {
    "version": "1.0", "mode": mode, "baseline": baseline_for(plan, context, normalized),
    "baselineComplete": False, "documents": [], "requirements": [], "assumptions": [],
    "gates": [{"id": gate, "status": "pending"} for gate in GATES],
  }


def main():
  parser = argparse.ArgumentParser(description="Create, rebind, inspect or record explicitly confirmed opportunity review metadata (no pricing or sharing)")
  parser.add_argument("command", choices=["template", "rebind", "status", "approve-gate", "approve-assumption"])
  parser.add_argument("--plan", required=True)
  parser.add_argument("--output", help="Output plan (required for mutations; input is never overwritten implicitly)")
  parser.add_argument("--normalized", help="Current normalized input; required to bind a compilable estimate")
  parser.add_argument("--mode", choices=MODES, default="working-estimate")
  parser.add_argument("--region", default="eastus")
  parser.add_argument("--currency", default="USD")
  parser.add_argument("--scenario", default="compare-all", choices=SCHEMA["$defs"]["context"]["properties"]["scenario"]["enum"])
  parser.add_argument("--id", help="Gate or assumption ID to approve")
  parser.add_argument("--name", help="Name supplied by the actual approver")
  parser.add_argument("--confirmed-at", help="Actual user confirmation timestamp with timezone")
  parser.add_argument("--evidence", help="Reference to actual user confirmation; never inferred")
  args = parser.parse_args()
  from quote_plan import load_quote_plan, save_quote_plan
  try:
    plan = (json.loads(Path(args.plan).read_text(encoding="utf-8")) if args.command == "template"
            else load_quote_plan(Path(args.plan)))
    if not isinstance(plan, dict):
      raise ReviewError("Quote plan must be an object")
    normalized = json.loads(Path(args.normalized).read_text(encoding="utf-8")) if args.normalized else None
    context = {"region": args.region, "currency": args.currency, "scenario": args.scenario}
    if args.command == "status":
      print(json.dumps(evaluate_review(plan, context, normalized), indent=2))
      return
    if not args.output:
      raise ReviewError("--output is required; choose a new file or explicitly name the input to replace")
    if args.command == "template":
      if "opportunityReview" in plan:
        raise ReviewError("Review already exists; use rebind to preserve requirements and clear approvals")
      plan["opportunityReview"] = template_review(plan, context, args.mode, normalized)
    else:
      if "opportunityReview" not in plan:
        raise ReviewError("No opportunityReview; run template first")
      review = plan["opportunityReview"]
      if review["mode"] != "quick-triage":
        issues = source_binding_issues(normalized)
        if issues:
          raise ReviewError("; ".join(issues))
      if args.command == "rebind":
        review["baseline"] = baseline_for(plan, context, normalized)
        review["baselineComplete"] = False
        for record in review["assumptions"] + review["gates"]:
          record.pop("approval", None)
          record["status"] = "proposed" if record in review["assumptions"] else "pending"
      else:
        if review["baseline"] != baseline_for(plan, context, normalized):
          raise ReviewError("Baseline stale; rebind and re-review before recording approval")
        records = review["gates"] if args.command == "approve-gate" else review["assumptions"]
        record = next((r for r in records if r["id"] == args.id), None)
        if record is None:
          raise ReviewError("--id must name an existing gate or assumption")
        record["approval"] = {"name": args.name, "confirmedAt": args.confirmed_at, "evidence": args.evidence,
                              "reviewDigest": review_digest(review)}
        record["status"] = "approved"
    save_quote_plan(plan, Path(args.output))
    print(json.dumps({"quotePlan": args.output, "opportunityStatus": evaluate_review(plan, context, normalized)}, indent=2))
  except (ValueError, OSError) as exc:
    parser.error(str(exc))


if __name__ == "__main__":
  main()
