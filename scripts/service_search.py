"""Provider-neutral service search and cross-provider equivalence resolution.

The pricing pipeline can only resolve a line once it knows which target product a
requirement maps to. Retail pricing APIs answer "what does this meter cost", not
"which product is the equivalent", and several products (Microsoft Fabric, Front
Door, Purview) have no single equivalent on another cloud at all.

This module answers those questions from the curated catalog in
``mappings/service_equivalence.yaml``:

* keyword, alias, and name search across every catalogued product
* equivalence lookup in any provider direction, including composite answers that
  list every product needed to reach the requested capability
* CSV/JSON export so a composite breakdown can be delivered outside the workbook
  when a special scenario calls for it
"""

from __future__ import annotations

import argparse
import csv
import difflib
import io
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

import yaml


CATALOG_PATH = Path(__file__).resolve().parent.parent / "mappings" / "service_equivalence.yaml"


# Tokens that appear in almost every cloud product name and therefore carry no
# discriminating signal for a search query.
STOPWORDS = {"service", "services", "cloud", "azure", "aws", "amazon", "microsoft", "google", "for", "and", "the"}
MIN_MATCH_SCORE = 2.0

# Below this length a token is too generic to be matched loosely; it must match a
# whole token exactly so a query such as "a" or "s" cannot match every product.
MIN_FUZZY_TOKEN_LENGTH = 4
FUZZY_RATIO = 0.82



def _stem(token: str) -> str:
  if len(token) >= 5 and token.endswith("es") and token[-3] in "sxzoh":
    return token[:-2]
  if len(token) >= 3 and token.endswith("s") and not token.endswith("ss"):
    return token[:-1]
  return token


def _tokens(text: str) -> List[str]:
  return [
    _stem(token)
    for token in re.split(r"[^a-z0-9]+", (text or "").lower())
    if token and token not in STOPWORDS
  ]


def _normalize(text: str) -> str:
  """Whitespace-joined stemmed tokens, so plural/spacing variants compare equal."""
  return " ".join(_tokens(text))


def _contains_phrase(haystack: str, needle: str) -> bool:
  """Substring match that respects word boundaries and ignores tiny needles.

  Both sides are normalized first so "virtual machine" matches "Azure Virtual
  Machines" without relying on exact surface spelling.
  """
  haystack_norm = _normalize(haystack)
  needle_norm = _normalize(needle)
  if len(needle_norm) < 2 or not haystack_norm:
    return False
  return re.search(rf"(?<![a-z0-9]){re.escape(needle_norm)}(?![a-z0-9])", haystack_norm) is not None


def _fuzzy_overlap(query_tokens: Set[str], value_tokens: Set[str]) -> bool:
  """True when a query token is a near-miss (typo) of a value token."""
  candidates = [token for token in value_tokens if len(token) >= MIN_FUZZY_TOKEN_LENGTH]
  if not candidates:
    return False
  for token in query_tokens:
    if len(token) < MIN_FUZZY_TOKEN_LENGTH:
      continue
    if difflib.get_close_matches(token, candidates, n=1, cutoff=FUZZY_RATIO):
      return True
  return False


@lru_cache(maxsize=8)
def load_catalog(path: str | None = None) -> List[Dict[str, Any]]:
  catalog_path = Path(path) if path else CATALOG_PATH
  if not catalog_path.exists():
    return []
  try:
    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
  except yaml.YAMLError:
    return []
  if not isinstance(data, dict):
    return []
  services = data.get("services")
  if not isinstance(services, list):
    return []
  return [entry for entry in services if isinstance(entry, dict)]


def _entry_haystacks(entry: Dict[str, Any]) -> Dict[str, List[str]]:
  return {
    "name": [str(entry.get("name", "")).lower()],
    "aliases": [str(item).lower() for item in entry.get("aliases") or []],
    "keywords": [str(item).lower() for item in entry.get("keywords") or []],
    "components": [
      value
      for equivalent in (entry.get("equivalents") or {}).values()
      for component in ((equivalent or {}).get("components") or [])
      if isinstance(component, dict)
      for value in (
        str(component.get("name", "")).lower(),
        str(component.get("service", "")).lower(),
        str(component.get("covers", "")).lower(),
      )
      if value
    ],
  }


def _score(entry: Dict[str, Any], query: str) -> float:
  query_lower = " ".join(str(query or "").lower().split())
  if not query_lower:
    return 0.0
  query_tokens = set(_tokens(query_lower))
  if not query_tokens:
    return 0.0
  haystacks = _entry_haystacks(entry)
  score = 0.0

  for value in haystacks["name"] + haystacks["aliases"]:
    if not value:
      continue
    value_tokens = set(_tokens(value))
    if value == query_lower or (value_tokens and value_tokens == query_tokens):
      score += 10.0
    elif _contains_phrase(value, query_lower) or _contains_phrase(query_lower, value):
      score += 6.0
    elif query_tokens & value_tokens:
      # Partial token overlap only counts in proportion to how much of the query
      # it explains, so a one-word brush against a long name cannot outrank a
      # full match.
      score += 2.0 * (len(query_tokens & value_tokens) / len(query_tokens))
    elif _fuzzy_overlap(query_tokens, value_tokens):
      score += 1.5

  for value in haystacks["keywords"]:
    if not value:
      continue
    value_tokens = set(_tokens(value))
    if _contains_phrase(query_lower, value) or _contains_phrase(value, query_lower):
      score += 2.5
    elif query_tokens & value_tokens:
      score += 1.5 * (len(query_tokens & value_tokens) / len(query_tokens))
    elif _fuzzy_overlap(query_tokens, value_tokens):
      score += 0.75

  for value in haystacks["components"]:
    if _contains_phrase(query_lower, value) or _contains_phrase(value, query_lower):
      score += 3.0

  if query_lower and _contains_phrase(str(entry.get("category", "")).lower(), query_lower):
    score += 1.0
  return score


def search_services(query: str, limit: int = 5, catalog: Iterable[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
  """Return catalogued products ranked by relevance to a free-text query."""
  if limit <= 0:
    return []
  entries = list(catalog) if catalog is not None else load_catalog()
  scored = [(entry, _score(entry, query)) for entry in entries]
  matches = [(entry, score) for entry, score in scored if score >= MIN_MATCH_SCORE]
  matches.sort(key=lambda item: (-item[1], str(item[0].get("name", ""))))
  return [{**entry, "matchScore": round(score, 2)} for entry, score in matches[:limit]]


def find_service(query: str, catalog: Iterable[Dict[str, Any]] | None = None) -> Dict[str, Any] | None:
  results = search_services(query, limit=1, catalog=catalog)
  return results[0] if results else None


def resolve_equivalents(query: str, target_provider: str, catalog: Iterable[Dict[str, Any]] | None = None) -> Dict[str, Any]:
  """Resolve the requested product into its equivalent(s) on ``target_provider``.

  The result always reports whether the answer is a single product or a
  composite of several, so callers never present a partial capability match as a
  like-for-like replacement.
  """
  entries = list(catalog) if catalog is not None else load_catalog()
  target = target_provider.strip().lower()
  entry = find_service(query, catalog=entries)
  if not entry:
    return {
      "query": query,
      "matched": False,
      "targetProvider": target,
      "components": [],
      "validations": [f"[VALIDATE] No catalogued equivalence for {query!r}; agent research required"],
    }

  source_provider = str(entry.get("provider", "")).lower()
  if target == source_provider:
    return {
      "query": query,
      "matched": True,
      "service": entry.get("name", ""),
      "sourceProvider": source_provider,
      "targetProvider": target,
      "type": "direct",
      "components": [{"name": entry.get("name", ""), "covers": "same-provider product"}],
      "validations": [],
    }

  equivalent = (entry.get("equivalents") or {}).get(target)
  if not equivalent:
    return {
      "query": query,
      "matched": True,
      "service": entry.get("name", ""),
      "sourceProvider": source_provider,
      "targetProvider": target,
      "type": "unmapped",
      "components": [],
      "validations": [
        f"[VALIDATE] {entry.get('name', query)} has no catalogued {target} equivalent; agent research required"
      ],
    }

  components = [dict(component) for component in equivalent.get("components", [])]
  equivalence_type = str(equivalent.get("type", "direct"))
  validations: List[str] = []
  if equivalence_type == "composite":
    names = ", ".join(str(component.get("name", "")) for component in components)
    validations.append(
      f"[VALIDATE] {entry.get('name', query)} has no single {target} equivalent; "
      f"capability requires the combination of {names}, and each component must be priced separately"
    )
  if equivalent.get("pricing_note"):
    validations.append(f"[VALIDATE] {equivalent['pricing_note']}")

  return {
    "query": query,
    "matched": True,
    "service": entry.get("name", ""),
    "sourceProvider": source_provider,
    "targetProvider": target,
    "type": equivalence_type,
    "rationale": str(equivalent.get("rationale", "")).strip(),
    "components": components,
    "validations": validations,
  }


def reverse_lookup(target_service: str, source_provider: str = "azure", catalog: Iterable[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
  """Find catalogued ``source_provider`` products whose equivalents include ``target_service``.

  This is what makes an Azure-sourced BOQ convertible: given ``Amazon Redshift``
  it reports every Azure product that covers it, including the composite ones
  where Redshift is only one component.
  """
  entries = list(catalog) if catalog is not None else load_catalog()
  needle = target_service.strip().lower()
  if not needle:
    return []
  results: List[Dict[str, Any]] = []
  for entry in entries:
    if str(entry.get("provider", "")).lower() != source_provider.strip().lower():
      continue
    for provider, equivalent in (entry.get("equivalents") or {}).items():
      for component in ((equivalent or {}).get("components") or []):
        if not isinstance(component, dict):
          continue
        component_name = str(component.get("name", "")).lower()
        component_service = str(component.get("service", "")).lower()
        if _contains_phrase(component_name, needle) or (component_service and needle == component_service):
          results.append({
            "service": entry.get("name", ""),
            "provider": entry.get("provider", ""),
            "targetProvider": provider,
            "type": str(equivalent.get("type", "direct")),
            "matchedComponent": component.get("name", ""),
            "partialMatch": str(equivalent.get("type", "direct")) == "composite",
          })
          break
  results.sort(key=lambda item: (item["partialMatch"], str(item["service"])))
  return results


def describe_line_equivalence(
  source_service: str,
  source_provider: str,
  target_provider: str,
  catalog: Iterable[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
  """Describe how one BOQ line's source product is covered on the target provider.

  Works in both directions: a catalogued target-provider product resolves through
  ``resolve_equivalents``, while a source product named in another provider's
  terms (an AWS line targeting Azure) resolves through ``reverse_lookup``.
  """
  entries = list(catalog) if catalog is not None else load_catalog()
  target = target_provider.strip().lower()
  source = source_provider.strip().lower()
  query = (source_service or "").strip()
  if not query:
    return {"query": "", "matched": False, "targetProvider": target, "components": [], "validations": []}

  entry = find_service(query, catalog=entries)
  if entry and str(entry.get("provider", "")).lower() == source and target != source:
    return resolve_equivalents(query, target, catalog=entries)

  matches = reverse_lookup(query, source_provider=target, catalog=entries)
  if not matches:
    return {
      "query": query,
      "matched": False,
      "sourceProvider": source,
      "targetProvider": target,
      "type": "unmapped",
      "components": [],
      "validations": [f"[VALIDATE] No catalogued {target} equivalence for {query!r}; agent research required"],
    }

  direct = [match for match in matches if not match["partialMatch"]]
  chosen = direct[0] if direct else matches[0]
  reported = direct or matches
  resolution: Dict[str, Any] = {
    "query": query,
    "matched": True,
    "service": query,
    "sourceProvider": source,
    "targetProvider": target,
    "type": "direct" if direct else "partial",
    "components": [{"name": match["service"], "covers": match["matchedComponent"]} for match in reported],
    "validations": [],
    "rationale": "",
  }
  if not direct:
    covering = ", ".join(match["service"] for match in matches)
    resolution["validations"].append(
      f"[VALIDATE] {query} is only one component of {covering}; the remaining components must be "
      f"quoted separately before the {target} line is comparable"
    )
  else:
    resolution["service"] = chosen["service"]
  return resolution


def equivalence_rows(resolution: Dict[str, Any]) -> List[Dict[str, str]]:
  """Flatten a resolution into one row per component for CSV/workbook output."""
  rows: List[Dict[str, str]] = []
  components = resolution.get("components") or [{}]
  for component in components:
    rows.append({
      "Query": str(resolution.get("query", "")),
      "Source service": str(resolution.get("service", "")),
      "Source provider": str(resolution.get("sourceProvider", "")),
      "Target provider": str(resolution.get("targetProvider", "")),
      "Equivalence": str(resolution.get("type", "")),
      "Target component": str(component.get("name", "")),
      "Capability covered": str(component.get("covers", "")),
      "Rationale": str(resolution.get("rationale", "")),
      "Notes/[VALIDATE]": "; ".join(resolution.get("validations", [])),
    })
  return rows


def to_csv(resolutions: List[Dict[str, Any]]) -> str:
  fieldnames = [
    "Query",
    "Source service",
    "Source provider",
    "Target provider",
    "Equivalence",
    "Target component",
    "Capability covered",
    "Rationale",
    "Notes/[VALIDATE]",
  ]
  buffer = io.StringIO()
  writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
  writer.writeheader()
  for resolution in resolutions:
    for row in equivalence_rows(resolution):
      writer.writerow(row)
  return buffer.getvalue()


def main() -> None:
  parser = argparse.ArgumentParser(description="Search cloud services and resolve cross-provider equivalents")
  parser.add_argument("query", nargs="+", help="Service name, alias, or capability keyword")
  parser.add_argument("--target-provider", default="aws", help="Provider the equivalents should be expressed in")
  parser.add_argument("--format", default="json", choices=["json", "csv"])
  parser.add_argument("--output", help="Optional file to write results to (.json or .csv)")
  parser.add_argument("--limit", type=int, default=5, help="Maximum search matches to report per query")
  args = parser.parse_args()

  resolutions = [resolve_equivalents(query, args.target_provider) for query in args.query]
  payload = {
    "results": resolutions,
    "searchMatches": {query: [match["name"] for match in search_services(query, args.limit)] for query in args.query},
  }
  rendered = to_csv(resolutions) if args.format == "csv" else json.dumps(payload, indent=2)

  if args.output:
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(json.dumps({"output": str(output_path), "results": len(resolutions)}, indent=2))
  else:
    print(rendered)


if __name__ == "__main__":
  main()
