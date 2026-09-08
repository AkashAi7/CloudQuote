"""Content binding for normalized source inputs; no timestamps or implicit rebinding."""

import hashlib
import re
from pathlib import Path


SOURCE_FIELDS = {"specs": "specs_source", "awsBoq": "aws_boq_source"}


def file_digest(path):
  digest = hashlib.sha256()
  with Path(path).open("rb") as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
      digest.update(chunk)
  return digest.hexdigest()


def source_hashes(specs_path, boq_path):
  return {"specs": file_digest(specs_path), "awsBoq": file_digest(boq_path)}


def source_binding_issues(normalized):
  normalized = normalized or {}
  bindings = normalized.get("sourceBindings")
  issues = []
  for role, field in SOURCE_FIELDS.items():
    expected = bindings.get(role) if isinstance(bindings, dict) else None
    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
      issues.append(f"Original {role} content is unbound; rerun parse_inputs.py before rebind/reapproval")
      continue
    path = normalized.get(field)
    try:
      if not isinstance(path, str) or not path.strip():
        raise ValueError("source path missing")
      actual = file_digest(path)
    except (OSError, ValueError) as exc:
      issues.append(f"Original {role} source cannot be verified: {exc}")
      continue
    if actual != expected:
      issues.append(f"Original {role} source changed since normalization; rerun parse_inputs.py, rebind and reapprove")
  return issues
