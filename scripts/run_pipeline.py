import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
import zipfile


def _run_fingerprint(
  specs_path: Path,
  aws_boq_path: Path,
  region: str,
  currency: str,
  scenario: str,
  quote_plan_path: Path | None = None,
  normalized_input_path: Path | None = None,
  max_price_age_hours: float = 24.0,
  enable_web_search: bool = False,
  price_cache_path: Path | None = None,
) -> str:
  digest = hashlib.sha256()
  digest.update(json.dumps({
    "region": region,
    "currency": currency,
    "scenario": scenario,
    "enableWebSearch": enable_web_search,
    "priceCachePath": str(price_cache_path.resolve()) if price_cache_path else "default",
    "pricingFreshnessWindow": int(time.time() // max(1, max_price_age_hours * 3600)),
  }, sort_keys=True).encode("utf-8"))
  project_root = Path(__file__).resolve().parent.parent
  dependencies = [
    specs_path,
    aws_boq_path,
    *([quote_plan_path] if quote_plan_path else []),
    *([normalized_input_path] if normalized_input_path else []),
    *sorted((project_root / "scripts").glob("*.py")),
    *sorted((project_root / "mappings").glob("*.yaml")),
    *sorted((project_root / "schemas").glob("*.json")),
  ]
  for path in dependencies:
    digest.update(str(path.resolve()).encode("utf-8"))
    digest.update(path.read_bytes())
  return digest.hexdigest()


def _file_sha256(path: Path) -> str:
  digest = hashlib.sha256()
  with path.open("rb") as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
      digest.update(chunk)
  return digest.hexdigest()


def _artifacts_are_valid(manifest: dict, artifacts: dict[str, str]) -> bool:
  hashes = manifest.get("artifactHashes")
  if not isinstance(hashes, dict):
    return False
  try:
    for name, raw_path in artifacts.items():
      path = Path(raw_path)
      if not path.is_file() or hashes.get(name) != _file_sha256(path):
        return False
      if name == "workbook" and not zipfile.is_zipfile(path):
        return False
      if name in {"normalized", "quotePlan", "summary"}:
        json.loads(path.read_text(encoding="utf-8"))
  except (OSError, ValueError, json.JSONDecodeError):
    return False
  return True


def _write_json_atomic(path: Path, payload: dict) -> None:
  temporary = path.with_suffix(path.suffix + ".tmp")
  temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
  temporary.replace(path)


@contextmanager
def _run_lock(path: Path, stale_after_seconds: int = 3600) -> Iterator[None]:
  if path.exists() and time.time() - path.stat().st_mtime > stale_after_seconds:
    path.unlink()
  try:
    with path.open("x", encoding="utf-8") as stream:
      stream.write(json.dumps({"pid": os.getpid(), "startedAt": datetime.now(timezone.utc).isoformat()}))
  except FileExistsError as exc:
    raise RuntimeError(f"Another CloudQuote operation is writing {path.parent}") from exc
  try:
    yield
  finally:
    path.unlink(missing_ok=True)


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
  parser.add_argument("--plan", help="Validated CloudQuote quote-plan.json supplied by the agent workflow")
  parser.add_argument("--normalized-input", help="Previously normalized input to avoid duplicate parsing")
  parser.add_argument("--max-price-age-hours", type=float, default=24.0)
  parser.add_argument("--enable-web-search", action="store_true", help="Allow slower unstructured web estimates after official sources fail")
  parser.add_argument("--price-cache", help="Optional isolated pricing-cache path")
  args = parser.parse_args()

  out_path = Path(args.output)
  out_path.parent.mkdir(parents=True, exist_ok=True)
  artifact_base = out_path.with_suffix("")
  normalized_path = artifact_base.with_suffix(".normalized.json")
  quote_plan_path = artifact_base.with_suffix(".quote-plan.json")
  summary_path = artifact_base.with_suffix(".summary.json")
  executive_summary_path = artifact_base.with_suffix(".executive-summary.md")
  manifest_path = artifact_base.with_suffix(".cloudquote-run.json")
  supplied_plan_path = Path(args.plan) if args.plan else None
  supplied_normalized_path = Path(args.normalized_input) if args.normalized_input else None
  fingerprint = _run_fingerprint(
    Path(args.specs),
    Path(args.aws_boq),
    args.region,
    args.currency,
    args.scenario,
    supplied_plan_path,
    supplied_normalized_path,
    args.max_price_age_hours,
    args.enable_web_search,
    Path(args.price_cache) if args.price_cache else None,
  )
  artifacts = {
    "workbook": str(out_path),
    "normalized": str(normalized_path),
    "quotePlan": str(quote_plan_path),
    "summary": str(summary_path),
    "executiveSummary": str(executive_summary_path),
  }
  if manifest_path.exists():
    try:
      manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
      manifest = {}
    if manifest.get("fingerprint") == fingerprint and _artifacts_are_valid(manifest, artifacts):
      print(json.dumps({**artifacts, "reused": True}, indent=2))
      return

  lock_path = artifact_base.with_suffix(".cloudquote.lock")
  with _run_lock(lock_path):
    os.environ["CLOUDQUOTE_PRICE_CACHE_TTL_HOURS"] = str(args.max_price_age_hours)
    os.environ["CLOUDQUOTE_ENABLE_WEB_SEARCH"] = "true" if args.enable_web_search else "false"
    os.environ["CLOUDQUOTE_DEFER_CACHE_WRITES"] = "true"
    if args.price_cache:
      os.environ["CLOUDQUOTE_PRICE_CACHE_PATH"] = args.price_cache
    from build_workbook import build_workbook
    from providers.targets import require_target_provider
    from quote_plan import apply_quote_plan, build_quote_plan, load_quote_plan, save_quote_plan

    if supplied_normalized_path:
      normalized = json.loads(supplied_normalized_path.read_text(encoding="utf-8"))
    else:
      from parse_inputs import normalize_inputs

      normalized = normalize_inputs(Path(args.specs), Path(args.aws_boq), normalized_path)
    if supplied_plan_path:
      quote_plan = load_quote_plan(supplied_plan_path)
    else:
      quote_plan = build_quote_plan(normalized)
    require_target_provider(str(quote_plan["targetProvider"])).validate_plan(quote_plan)
    save_quote_plan(quote_plan, quote_plan_path)
    normalized = apply_quote_plan(normalized, quote_plan)
    _write_json_atomic(normalized_path, normalized)

    pricing_date = datetime.now(timezone.utc).date().isoformat()
    summary = build_workbook(
      normalized=normalized,
      pricing_meta={"region": args.region, "currency": args.currency, "pricingDate": pricing_date},
      output_path=out_path,
      scenario=args.scenario,
    )
    from pricing import flush_cache

    flush_cache()

    _write_json_atomic(summary_path, summary)
    executive_summary_path.write_text(_render_executive_summary(summary), encoding="utf-8")
    manifest = {
      "fingerprint": fingerprint,
      "completedAt": datetime.now(timezone.utc).isoformat(),
      "artifactHashes": {name: _file_sha256(Path(path)) for name, path in artifacts.items()},
    }
    _write_json_atomic(manifest_path, manifest)
  print(json.dumps({**artifacts, "reused": False}, indent=2))


if __name__ == "__main__":
  main()
