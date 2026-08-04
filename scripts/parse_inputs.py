import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml


def _read_aws_boq(path: Path) -> List[Dict[str, Any]]:
  if path.suffix.lower() == ".csv":
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
      return [dict(row) for row in csv.DictReader(stream)]
  elif path.suffix.lower() == ".xlsx":
    import pandas as pd

    xls = pd.ExcelFile(path, engine="openpyxl")
    preferred_sheet = None
    for sheet in xls.sheet_names:
      s = sheet.strip().lower()
      if "opex" in s and "aws" in s:
        preferred_sheet = sheet
        break
    if preferred_sheet is None:
      for sheet in xls.sheet_names:
        probe = pd.read_excel(xls, sheet_name=sheet, nrows=5)
        cols = {str(c).strip().lower() for c in probe.columns}
        if "aws sku" in cols and ("total cost" in cols or "quantity per unit per month" in cols):
          preferred_sheet = sheet
          break
    if preferred_sheet is None:
      preferred_sheet = xls.sheet_names[0]
    df = pd.read_excel(xls, sheet_name=preferred_sheet)
  else:
    import pandas as pd

    df = pd.read_excel(path)
  return df.fillna("").to_dict(orient="records")


def _read_azure_reference_map(path: Path) -> Dict[str, Dict[str, Any]]:
  if path.suffix.lower() != ".xlsx":
    return {}
  try:
    import pandas as pd

    xls = pd.ExcelFile(path, engine="openpyxl")
  except Exception:
    return {}

  azure_sheet = None
  for sheet in xls.sheet_names:
    s = sheet.strip().lower()
    if "opex" in s and "azure" in s:
      azure_sheet = sheet
      break
  if azure_sheet is None:
    return {}

  try:
    df = pd.read_excel(xls, sheet_name=azure_sheet)
  except Exception:
    return {}

  ref_map: Dict[str, Dict[str, Any]] = {}
  for _, row in df.fillna("").iterrows():
    sr = str(row.get("Sr. No", row.get("Sr No", ""))).strip()
    if not sr:
      continue
    ref_map[sr] = {
      "unit_price": row.get("Unit Price", ""),
      "total_cost": row.get("Total Cost", ""),
      "sku": row.get("AWS SKU", ""),
      "remarks": row.get("Remarks", ""),
    }
  return ref_map


def _first_non_empty(row: Dict[str, Any], keys: List[str], default: Any = "") -> Any:
  for key in keys:
    if key in row and row[key] not in (None, ""):
      return row[key]
  return default


def _infer_service(description: str, sku: str, explicit_service: str) -> str:
  if explicit_service.strip():
    return explicit_service.strip()

  haystack = f"{description} {sku}".lower()
  service_map = {
    "rds": ["rds", "db.", "postgresql", "mysql", "sql"],
    "ec2": ["ec2", "t3.", "m5.", "m6", "m7", "r6", "r7", "c6", "g4", "c5", "r5", "virtual machine", "azure vm"],
    "ebs": ["ebs", "gp3", "iops", "ssd", "managed disk"],
    "s3": ["s3", "object storage", "blob storage", "data lake storage"],
    "efs": ["efs", "file storage"],
    "lambda": ["lambda", "azure functions"],
    "dynamodb": ["dynamodb", "cosmos db"],
    "eks": ["eks", "kubernetes"],
    "elb": ["load balancer", "nlb", "network load balancer", "elb"],
    "alb": ["application gateway", "application load balancer", "alb"],
    "cloudfront": ["cloudfront", "cdn", "front door"],
    "redshift": ["redshift", "data warehouse", "synapse"],
    "vpc": ["vpc", "vnet", "peering", "nat gateway", "private endpoint", "virtual network"],
    "github": ["github team", "github enterprise", "github free", "github"],
  }

  for service, tokens in service_map.items():
    if any(token in haystack for token in tokens):
      return service
  return ""


def _to_float_if_possible(value: Any) -> Any:
  if isinstance(value, (int, float)):
    return value
  if not isinstance(value, str):
    return value
  text = value.strip()
  if not text:
    return ""
  match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)", text)
  if match:
    try:
      return float(match.group(1))
    except ValueError:
      return value
  return value


def _normalize_aws_rows(rows: List[Dict[str, Any]], azure_ref: Dict[str, Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
  azure_ref = azure_ref or {}
  normalized: List[Dict[str, Any]] = []
  for row in rows:
    sr_no = str(_first_non_empty(row, ["Sr. No", "Sr No", "sr_no"], "")).strip()
    description = str(_first_non_empty(row, ["Description", "description", "Capacity", "capacity"], "")).strip()
    sku = str(_first_non_empty(row, ["Instance/SKU", "instance", "sku", "AWS SKU", "Aws SKU"], "")).strip()
    explicit_service = str(_first_non_empty(row, ["Service", "service"], "")).strip()
    quantity = _first_non_empty(row, ["Quantity", "quantity", "Quantity per unit per Month"], 1)
    quantity_raw = str(quantity)
    monthly = _first_non_empty(row, ["Monthly", "monthly", "Monthly Cost", "Total Cost"], 0)
    source_unit = str(_first_non_empty(row, ["Unit", "unit"], "")).strip()
    environment = str(_first_non_empty(row, ["Environment", "environment"], "prod")).strip() or "prod"
    azure_service = str(_first_non_empty(row, ["Azure Service", "azure_service"], "")).strip()
    azure_sku = str(_first_non_empty(row, ["Azure SKU", "azure_sku"], "")).strip()
    meter_contains = str(_first_non_empty(row, ["Meter Contains", "meter_contains"], "")).strip()
    product_contains = str(_first_non_empty(row, ["Product Contains", "product_contains"], "")).strip()
    force_validate = str(_first_non_empty(row, ["Force Validate", "force_validate"], "")).strip()
    price_region = str(_first_non_empty(row, ["Price Region", "price_region"], "")).strip()

    capacity_value = description
    if quantity_raw and quantity_raw.strip() and quantity_raw.strip() not in {"1", "1.0"}:
      capacity_value = f"{description} {quantity_raw}".strip()

    azure_local = azure_ref.get(sr_no, {})
    normalized.append(
      {
        "Sr. No": sr_no,
        "Service": _infer_service(description, sku, explicit_service),
        "Instance/SKU": sku,
        "Quantity": _to_float_if_possible(quantity),
        "Quantity Raw": quantity_raw,
        "Monthly": _to_float_if_possible(monthly),
        "Environment": environment,
        "Capacity": capacity_value,
        "Azure Service": azure_service,
        "Azure SKU": azure_sku,
        "Meter Contains": meter_contains,
        "Product Contains": product_contains,
        "Force Validate": force_validate,
        "Price Region": price_region,
        "Source Description": description,
        "Source Unit": source_unit,
        "Local Azure Unit Price": azure_local.get("unit_price", ""),
        "Local Azure Total Cost": azure_local.get("total_cost", ""),
        "Local Azure SKU": azure_local.get("sku", ""),
        "Local Azure Remarks": azure_local.get("remarks", ""),
      }
    )
  return normalized


def _instance_map() -> Dict[str, Any]:
  mapping_path = Path(__file__).resolve().parent.parent / "mappings" / "instance_sizes.yaml"
  if not mapping_path.exists():
    return {}
  data = yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
  return data.get("instances", {})


def _apply_implied_capacity(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
  instances = _instance_map()
  out: List[Dict[str, Any]] = []
  for row in rows:
    cap = str(row.get("Capacity", row.get("capacity", ""))).strip()
    sku = str(row.get("Instance/SKU", row.get("instance", row.get("sku", "")))).strip()
    if not cap and sku in instances:
      spec = instances[sku]
      row["Capacity"] = f"{spec['vcpu']} vCPU / {spec['memory_gb']} GB"
    out.append(row)
  return out


def _read_specs(path: Path) -> Dict[str, Any]:
  suffix = path.suffix.lower()
  if suffix in {".yaml", ".yml"}:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
  if suffix == ".json":
    return json.loads(path.read_text(encoding="utf-8"))
  if suffix == ".docx":
    from docx import Document

    doc = Document(path)
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return {"raw_text": text}
  raise ValueError(f"Unsupported specs format: {path}")


def _required_fields() -> List[str]:
  return [
    "workloads",
    "sla_targets",
    "compute",
    "storage",
    "network",
    "databases",
    "environments",
    "regions",
    "availability",
    "growth",
    "owned_licenses",
  ]


def _extract_missing(specs: Dict[str, Any]) -> List[str]:
  if "raw_text" in specs:
    text = specs["raw_text"].lower()
    missing = []
    for f in _required_fields():
      key = f.replace("_", " ")
      if key not in text and f not in text:
        missing.append(f)
    return missing

  missing = []
  for f in _required_fields():
    if f not in specs or specs[f] in (None, "", [], {}):
      missing.append(f)
  return missing


def normalize_inputs(specs_path: Path, aws_boq_path: Path, output_path: Path) -> Dict[str, Any]:
  specs = _read_specs(specs_path)
  aws_rows_raw = _read_aws_boq(aws_boq_path)
  azure_ref = _read_azure_reference_map(aws_boq_path)
  aws_rows = _apply_implied_capacity(_normalize_aws_rows(aws_rows_raw, azure_ref=azure_ref))

  normalized = {
    "specs_source": str(specs_path),
    "aws_boq_source": str(aws_boq_path),
    "specs": specs,
    "aws_boq": aws_rows,
    "missing_or_ambiguous": _extract_missing(specs),
  }

  output_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
  return normalized


def main() -> None:
  parser = argparse.ArgumentParser(description="Normalize customer specs and AWS BOQ into JSON")
  parser.add_argument("--specs", required=True)
  parser.add_argument("--aws-boq", required=True)
  parser.add_argument("--output", required=True)
  args = parser.parse_args()

  result = normalize_inputs(Path(args.specs), Path(args.aws_boq), Path(args.output))
  print(json.dumps({"missing_or_ambiguous": result["missing_or_ambiguous"]}, indent=2))


if __name__ == "__main__":
  main()
