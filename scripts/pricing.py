from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List
from urllib.parse import quote

if TYPE_CHECKING:
  import requests

API_BASE = "https://prices.azure.com/api/retail/prices"
DEFAULT_CACHE_PATH = Path(__file__).resolve().parent.parent / "pricing_cache.json"
CACHE_PATH = Path(os.getenv("CLOUDQUOTE_PRICE_CACHE_PATH", str(DEFAULT_CACHE_PATH)))
_CACHE_DATA: Dict[str, Any] | None = None
_CACHE_MUTEX = threading.Lock()
_PENDING_CACHE: Dict[str, Any] = {}
_HTTP_LOCAL = threading.local()
DEFAULT_CACHE_TTL_HOURS = float(os.getenv("CLOUDQUOTE_PRICE_CACHE_TTL_HOURS", "24"))


def _utc_now() -> datetime:
  return datetime.now(timezone.utc)


def _new_session():
  import requests

  if not hasattr(_HTTP_LOCAL, "session"):
    _HTTP_LOCAL.session = requests.Session()
  return _HTTP_LOCAL.session


def _cache_entry_is_fresh(value: Any, max_age_hours: float = DEFAULT_CACHE_TTL_HOURS) -> bool:
  if not isinstance(value, dict) or max_age_hours <= 0:
    return False
  cached_at = value.get("cachedAt")
  if not cached_at:
    return False
  try:
    timestamp = datetime.fromisoformat(str(cached_at).replace("Z", "+00:00"))
  except ValueError:
    return False
  return _utc_now() - timestamp <= timedelta(hours=max_age_hours)


def _with_cache_timestamp(value: Dict[str, Any]) -> Dict[str, Any]:
  return {**value, "cachedAt": _utc_now().isoformat()}


def _cache_key(
  region: str,
  currency_code: str,
  service_name: str | None,
  sku_name: str | None,
  meter_name: str | None,
  price_type: str,
  reservation_term: str | None,
) -> str:
  return json.dumps(
    {
      "region": region,
      "currency": currency_code,
      "serviceName": service_name,
      "skuName": sku_name,
      "meterName": meter_name,
      "priceType": price_type,
      "reservationTerm": reservation_term,
    },
    sort_keys=True,
  )


def load_cache(cache_path: Path = CACHE_PATH) -> Dict[str, Any]:
  global _CACHE_DATA
  if not cache_path.exists():
    _CACHE_DATA = {}
    return {}
  if cache_path == CACHE_PATH and _CACHE_DATA is not None:
    return _CACHE_DATA
  try:
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    if cache_path == CACHE_PATH:
      _CACHE_DATA = cache
    return cache
  except Exception:
    if cache_path == CACHE_PATH:
      _CACHE_DATA = {}
    return {}


def _write_cache(cache: Dict[str, Any], cache_path: Path = CACHE_PATH) -> None:
  global _CACHE_DATA
  temporary = cache_path.with_suffix(cache_path.suffix + f".{os.getpid()}.tmp")
  temporary.write_text(json.dumps(cache, indent=2), encoding="utf-8")
  temporary.replace(cache_path)
  if cache_path == CACHE_PATH:
    _CACHE_DATA = cache


@contextmanager
def _cache_write_lock(cache_path: Path, timeout_seconds: float = 5.0):
  lock_path = cache_path.with_suffix(cache_path.suffix + ".lock")
  deadline = time.monotonic() + timeout_seconds
  while True:
    if lock_path.exists() and time.time() - lock_path.stat().st_mtime > 60:
      lock_path.unlink(missing_ok=True)
    try:
      with lock_path.open("x", encoding="utf-8") as stream:
        stream.write(str(os.getpid()))
      break
    except FileExistsError:
      if time.monotonic() >= deadline:
        raise RuntimeError(f"Timed out waiting for pricing cache lock: {lock_path}")
      time.sleep(0.05)
  try:
    yield
  finally:
    lock_path.unlink(missing_ok=True)


def _update_cache_entry(key: str, value: Dict[str, Any], cache_path: Path = CACHE_PATH) -> None:
  global _CACHE_DATA
  if os.getenv("CLOUDQUOTE_DEFER_CACHE_WRITES", "false").lower() in {"1", "true", "yes"}:
    with _CACHE_MUTEX:
      if _CACHE_DATA is None:
        try:
          _CACHE_DATA = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        except (OSError, json.JSONDecodeError):
          _CACHE_DATA = {}
      _CACHE_DATA[key] = value
      _PENDING_CACHE[key] = value
    return
  with _cache_write_lock(cache_path):
    try:
      cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    except (OSError, json.JSONDecodeError):
      cache = {}
    cache[key] = value
    _write_cache(cache, cache_path)
    if cache_path == CACHE_PATH:
      _CACHE_DATA = cache


def flush_cache(cache_path: Path = CACHE_PATH) -> None:
  global _CACHE_DATA
  with _CACHE_MUTEX:
    pending = dict(_PENDING_CACHE)
    _PENDING_CACHE.clear()
  if not pending:
    return
  with _cache_write_lock(cache_path):
    try:
      cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    except (OSError, json.JSONDecodeError):
      cache = {}
    cache.update(pending)
    _write_cache(cache, cache_path)
    _CACHE_DATA = cache


def _build_filter(region: str, service_name: str | None, sku_name: str | None, meter_name: str | None, price_type: str, reservation_term: str | None) -> str:
  filters = [f"armRegionName eq '{region}'", f"priceType eq '{price_type}'"]
  if service_name:
    filters.append(f"serviceName eq '{service_name}'")
  if sku_name:
    filters.append(f"skuName eq '{sku_name}'")
  if meter_name:
    filters.append(f"meterName eq '{meter_name}'")
  if reservation_term:
    filters.append(f"reservationTerm eq '{reservation_term}'")
  return " and ".join(filters)


def fetch_prices(
  region: str,
  currency_code: str,
  service_name: str | None = None,
  sku_name: str | None = None,
  meter_name: str | None = None,
  price_type: str = "Consumption",
  reservation_term: str | None = None,
  session: requests.Session | None = None,
  fallback_to_cache: bool = True,
) -> List[Dict[str, Any]]:
  session = session or _new_session()
  cache_key = _cache_key(region, currency_code, service_name, sku_name, meter_name, price_type, reservation_term)
  query_filter = _build_filter(region, service_name, sku_name, meter_name, price_type, reservation_term)
  url = f"{API_BASE}?$filter={quote(query_filter)}&currencyCode={currency_code}"

  items: List[Dict[str, Any]] = []
  while url:
    last_error: Exception | None = None
    response = None
    for _ in range(3):
      try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        break
      except Exception as exc:  # pragma: no cover - network instability path
        last_error = exc
        response = None
    if response is None:
      if fallback_to_cache:
        cached = load_cache().get(cache_key)
        if _cache_entry_is_fresh(cached) and isinstance(cached.get("items"), list):
          return cached["items"]
      raise last_error or RuntimeError("Azure Retail Prices API request failed")
    payload = response.json()
    items.extend(payload.get("Items", []))
    url = payload.get("NextPageLink")

  _update_cache_entry(cache_key, _with_cache_timestamp({"items": items}))

  return items


def _resolved_cache_key(
  region: str,
  currency_code: str,
  service_name: str | None,
  sku_name: str | None,
  meter_name: str | None,
  price_type: str,
  reservation_term: str | None,
  target_sku: str | None,
  meter_contains: str | None,
  product_contains: str | None,
  select_service_name: str | None,
  strict_contains: bool = False,
  reviewed_evidence: List[Dict[str, Any]] | None = None,
) -> str:
  payload = {
    "region": region,
    "currency": currency_code,
    "serviceName": service_name,
    "skuName": sku_name,
    "meterName": meter_name,
    "priceType": price_type,
    "reservationTerm": reservation_term,
    "targetSku": target_sku,
    "meterContains": meter_contains,
    "productContains": product_contains,
    "selectServiceName": select_service_name,
    "strictContains": strict_contains,
    "reviewedEvidence": reviewed_evidence or [],
  }
  return "resolved::" + json.dumps(payload, sort_keys=True)


def _save_resolved_cache(key: str, value: Dict[str, Any], cache_path: Path = CACHE_PATH) -> None:
  _update_cache_entry(key, _with_cache_timestamp(value), cache_path)


def resolve_best_price(
  region: str,
  currency_code: str,
  service_name: str | None,
  sku_name: str | None,
  meter_name: str | None,
  price_type: str,
  reservation_term: str | None,
  target_sku: str | None = None,
  meter_contains: str | None = None,
  product_contains: str | None = None,
  select_service_name: str | None = None,
  search_hint: str | None = None,
  enable_web_search: bool | None = None,
  strict_contains: bool = False,
  reviewed_evidence: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
  resolved_key = _resolved_cache_key(
    region,
    currency_code,
    service_name,
    sku_name,
    meter_name,
    price_type,
    reservation_term,
    target_sku,
    meter_contains,
    product_contains,
    select_service_name,
    strict_contains,
    reviewed_evidence,
  )
  if enable_web_search is None:
    enable_web_search = os.getenv("CLOUDQUOTE_ENABLE_WEB_SEARCH", "false").lower() in {"1", "true", "yes"}
  cache = load_cache()

  cached = cache.get(resolved_key)
  if _cache_entry_is_fresh(cached):
    cached_best = cached.get("best")
    cached_note = str(cached.get("note", ""))
    if cached_best or not enable_web_search:
      return {
        "source": "CACHE" if cached_best else "NONE",
        "originSource": cached.get("originSource") or cached.get("source"),
        "best": cached_best,
        "links": cached.get("links", []),
        "note": "[CACHE_HIT] Using previously resolved price" if cached_best else (cached_note or "[CACHE_HIT] Reusing previous unresolved lookup"),
      }

  # 1) API
  try:
    api_items = fetch_prices(
      region=region,
      currency_code=currency_code,
      service_name=service_name,
      sku_name=sku_name,
      meter_name=meter_name,
      price_type=price_type,
      reservation_term=reservation_term,
      fallback_to_cache=False,
    )
  except Exception:
    api_items = []

  api_best = select_best_price(
    api_items,
    target_sku=target_sku,
    meter_contains=meter_contains,
    product_contains=product_contains,
    service_name=select_service_name,
    strict_contains=strict_contains,
  )
  if api_best:
    resolved = {
      "source": "API",
      "best": api_best,
      "links": [],
      "note": "",
    }
    _save_resolved_cache(resolved_key, resolved)
    return resolved

  fallback_attempted = bool(reviewed_evidence and service_name and (sku_name or target_sku))
  fallback_started = time.perf_counter()
  if fallback_attempted:
    from providers.evidence import resolve_reviewed_evidence

    evidence_result = resolve_reviewed_evidence(
      reviewed_evidence,
      provider="azure",
      region=region,
      currency=currency_code,
      service=service_name,
      sku=sku_name or target_sku or "",
      price_type=price_type,
      reservation_term=reservation_term,
      max_age_hours=float(os.getenv("CLOUDQUOTE_EVIDENCE_MAX_AGE_HOURS", "168")),
    )
    if evidence_result:
      evidence_result = {
        **evidence_result,
        "fallbackAttempted": True,
        "fallbackSucceeded": True,
        "fallbackLatencyMs": round((time.perf_counter() - fallback_started) * 1000.0, 3),
      }
      _save_resolved_cache(resolved_key, evidence_result)
      return evidence_result

  fallback_latency_ms = round((time.perf_counter() - fallback_started) * 1000.0, 3) if fallback_attempted else 0.0

  if not enable_web_search:
    return {
      "source": "NONE",
      "best": None,
      "links": [],
      "note": "[VALIDATE] Azure Retail Prices API did not resolve this meter and no approved pricing evidence was supplied",
      "fallbackAttempted": fallback_attempted,
      "fallbackSucceeded": False,
      "fallbackLatencyMs": fallback_latency_ms,
    }

  resolved = {
    "source": "NONE",
    "best": None,
    "links": [],
    "note": "[VALIDATE] API price unresolved; approved MCP or search-API pricing evidence is required. Compiler HTML scraping is disabled",
    "fallbackAttempted": fallback_attempted,
    "fallbackSucceeded": False,
    "fallbackLatencyMs": fallback_latency_ms,
  }
  _save_resolved_cache(resolved_key, resolved)
  return resolved


def _contains(value: str, needle: str | None) -> bool:
  return needle is None or needle.lower() in value.lower()


def select_best_price(
  items: List[Dict[str, Any]],
  target_sku: str | None = None,
  meter_contains: str | None = None,
  product_contains: str | None = None,
  service_name: str | None = None,
  allow_zero_price: bool = False,
  strict_contains: bool = False,
) -> Dict[str, Any] | None:
  if not items:
    return None

  candidates = list(items)
  if service_name:
    matches = [i for i in candidates if str(i.get("serviceName", "")).lower() == service_name.lower()]
    if matches:
      candidates = matches

  if target_sku:
    exact = [i for i in candidates if str(i.get("skuName", "")).lower() == target_sku.lower()]
    if exact:
      candidates = exact

  if product_contains:
    matches = [i for i in candidates if _contains(str(i.get("productName", "")), product_contains)]
    if matches:
      candidates = matches
    elif strict_contains:
      # The caller pinned this product deliberately. Falling through to an unrelated meter would
      # silently produce a wrong number, so report no match and let the caller flag the line.
      return None

  if meter_contains:
    matches = [i for i in candidates if _contains(str(i.get("meterName", "")), meter_contains)]
    if matches:
      candidates = matches
    elif strict_contains:
      return None

  positive = [i for i in candidates if float(i.get("retailPrice", 0.0) or 0.0) > 0.0]
  if positive and not allow_zero_price:
    candidates = positive

  return min(candidates, key=lambda x: x.get("retailPrice", float("inf")))


def save_cache(cache_path: Path, key: str, result: Dict[str, Any]) -> None:
  _update_cache_entry(key, result, cache_path)


def main() -> None:
  parser = argparse.ArgumentParser(description="Query Azure Retail Prices API for a specific SKU.")
  parser.add_argument("--region", required=True)
  parser.add_argument("--currency", default="USD")
  parser.add_argument("--service-name")
  parser.add_argument("--sku-name")
  parser.add_argument("--meter-name")
  parser.add_argument("--price-type", choices=["Consumption", "Reservation"], default="Consumption")
  parser.add_argument("--reservation-term", choices=["1 Year", "3 Years"])
  parser.add_argument("--cache", default="pricing_cache.json")
  parser.add_argument("--output", default="")
  args = parser.parse_args()

  if args.price_type == "Reservation" and not args.reservation_term:
    raise SystemExit("--reservation-term is required when --price-type is Reservation")

  items = fetch_prices(
    region=args.region,
    currency_code=args.currency,
    service_name=args.service_name,
    sku_name=args.sku_name,
    meter_name=args.meter_name,
    price_type=args.price_type,
    reservation_term=args.reservation_term,
  )

  best = select_best_price(items, target_sku=args.sku_name)

  now = datetime.now(timezone.utc).isoformat()
  result: Dict[str, Any] = {
    "query": {
      "region": args.region,
      "currency": args.currency,
      "serviceName": args.service_name,
      "skuName": args.sku_name,
      "meterName": args.meter_name,
      "priceType": args.price_type,
      "reservationTerm": args.reservation_term,
    },
    "fetchedAt": now,
    "priceSource": "Azure Retail Prices API",
    "count": len(items),
    "best": best,
    "validateRequired": best is None,
    "note": "[VALIDATE] Fallback to Azure Pricing Calculator required." if best is None else "",
  }

  cache_key = json.dumps(result["query"], sort_keys=True)
  save_cache(Path(args.cache), cache_key, result)

  output = json.dumps(result, indent=2)
  if args.output:
    Path(args.output).write_text(output, encoding="utf-8")
  print(output)


if __name__ == "__main__":
  main()
