import argparse
import base64
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests

API_BASE = "https://prices.azure.com/api/retail/prices"
CACHE_PATH = Path(__file__).resolve().parent.parent / "pricing_cache.json"
WEB_SEARCH_ENDPOINT = "https://www.bing.com/search"
DDG_SEARCH_ENDPOINT = "https://duckduckgo.com/html/"

_CACHE_DATA: Dict[str, Any] | None = None


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
  cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
  if cache_path == CACHE_PATH:
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
  session = session or requests.Session()
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
        if cached and isinstance(cached.get("items"), list):
          return cached["items"]
      raise last_error or RuntimeError("Azure Retail Prices API request failed")
    payload = response.json()
    items.extend(payload.get("Items", []))
    url = payload.get("NextPageLink")

  cache = load_cache()
  cache[cache_key] = {"items": items}
  _write_cache(cache)

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
  }
  return "resolved::" + json.dumps(payload, sort_keys=True)


def _save_resolved_cache(key: str, value: Dict[str, Any], cache_path: Path = CACHE_PATH) -> None:
  cache = load_cache(cache_path)
  cache[key] = value
  _write_cache(cache, cache_path)


def _extract_web_price(text: str) -> float | None:
  # Price parsing from snippets and pages; prefers currency-tagged values, then per-hour style decimals.
  for match in re.finditer(r"(?:\$|USD\s*)(\d+(?:,\d{3})*(?:\.\d+)?)", text, flags=re.IGNORECASE):
    raw = match.group(1).replace(",", "")
    try:
      value = float(raw)
    except ValueError:
      continue
    if 0 < value < 100000:
      return value

  for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(?:/\s*hour|per\s*hour|hourly)\b", text, flags=re.IGNORECASE):
    try:
      value = float(match.group(1))
    except ValueError:
      continue
    if 0 < value < 100000:
      return value

  for match in re.finditer(r"\b(\d+\.\d{2,4})\b", text):
    try:
      value = float(match.group(1))
    except ValueError:
      continue
    if 0 < value < 100000:
      return value
  return None


def _decode_bing_link(link: str) -> str:
  try:
    parsed = urlparse(link)
    if "bing.com" not in parsed.netloc:
      return link
    qs = parse_qs(parsed.query)
    encoded = qs.get("u", [""])[0]
    if not encoded:
      return link
    encoded = unquote(encoded)
    if encoded.startswith("a1"):
      encoded = encoded[2:]
    padding = "=" * ((4 - len(encoded) % 4) % 4)
    decoded = base64.urlsafe_b64decode((encoded + padding).encode("utf-8")).decode("utf-8", errors="ignore")
    return decoded if decoded.startswith("http") else link
  except Exception:
    return link


def _extract_links_from_html(html: str) -> List[str]:
  links: List[str] = []

  # Primary: standard anchor extraction.
  for pattern in [r'href="([^"]+)"', r"href='([^']+)'"]:
    for raw in re.findall(pattern, html, flags=re.IGNORECASE):
      decoded = _decode_bing_link(raw)
      if decoded.startswith("http") and decoded not in links:
        links.append(decoded)

  # Fallback: plain URL extraction from script blobs or serialized payloads.
  for raw in re.findall(r"https?://[^\s\"'<>]+", html, flags=re.IGNORECASE):
    cleaned = raw.strip().rstrip(",.;)")
    if cleaned.startswith("http") and cleaned not in links:
      links.append(cleaned)

  return links


def _search_ddg_links(query: str, session: requests.Session) -> List[str]:
  try:
    response = session.get(
      DDG_SEARCH_ENDPOINT,
      params={"q": query},
      timeout=20,
      headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    html = response.text
  except Exception:
    return []

  links: List[str] = []
  for raw in re.findall(r'href="([^"]+)"', html, flags=re.IGNORECASE):
    decoded = unquote(raw)
    match = re.search(r"uddg=([^&]+)", decoded)
    if match:
      decoded = unquote(match.group(1))
    if decoded.startswith("http") and decoded not in links:
      links.append(decoded)
  return links


def _search_web_price(
  region: str,
  currency_code: str,
  service_name: str | None,
  sku_name: str | None,
  meter_name: str | None,
  price_type: str,
  reservation_term: str | None,
  search_hint: str | None = None,
  session: requests.Session | None = None,
) -> Dict[str, Any]:
  session = session or requests.Session()
  service_token = service_name or "Azure service"
  sku_token = sku_name or meter_name or "SKU"
  term_token = reservation_term or price_type
  hint = f" {search_hint}" if search_hint else ""
  query = f"site:azure.microsoft.com/pricing/details Azure {service_token} {sku_token}{hint} {region} {currency_code} price {term_token}"
  search_url = f"{WEB_SEARCH_ENDPOINT}?q={quote(query)}"
  try:
    response = session.get(
      WEB_SEARCH_ENDPOINT,
      params={"q": query},
      timeout=20,
      headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    html = response.text
  except Exception:
    return {
      "best": None,
      "links": [search_url],
      "query": query,
    }

  links = _extract_links_from_html(html)

  # If Bing returned challenge/minimal markup, try DDG as backup index.
  looks_challenged = any(tok in html.lower() for tok in ["captcha", "challenge", "automated", "verify you are"])
  if looks_challenged or not links:
    for link in _search_ddg_links(query, session):
      if link not in links:
        links.append(link)

  snippets = re.findall(r'<div class="b_caption"[^>]*>.*?<p>(.*?)</p>', html, flags=re.DOTALL)

  cleaned_snippets = [re.sub(r"<[^>]+>", " ", s) for s in snippets]
  combined_text = "\n".join(cleaned_snippets)
  price = _extract_web_price(combined_text)

  if price is None and links:
    candidate_links = [l for l in links if "azure.microsoft.com/pricing" in l.lower()]
    if not candidate_links:
      candidate_links = links
    for link in candidate_links[:5]:
      try:
        page = session.get(link, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if page.status_code >= 400:
          continue
        text = re.sub(r"<[^>]+>", " ", page.text)
        price = _extract_web_price(text)
        if price is not None:
          break
      except Exception:
        continue

  evidence_links: List[str] = [search_url]
  for link in links[:5]:
    if link not in evidence_links:
      evidence_links.append(link)

  if price is None:
    return {
      "best": None,
      "links": evidence_links,
      "query": query,
    }

  return {
    "best": {
      "retailPrice": price,
      "unitOfMeasure": "Web Estimated Unit",
      "effectiveStartDate": datetime.now(timezone.utc).date().isoformat(),
      "serviceName": service_name or "",
      "skuName": sku_name or "",
      "meterName": meter_name or "",
      "productName": "Web search estimate",
      "sourceLinks": evidence_links,
    },
    "links": evidence_links,
    "query": query,
  }


def _search_web_price_relaxed(
  region: str,
  currency_code: str,
  service_name: str | None,
  search_hint: str | None = None,
  session: requests.Session | None = None,
) -> Dict[str, Any]:
  # Relaxed pass used when strict API/SKU/product mapping misses.
  normalized_hint = re.sub(r"\b\d+\b", " ", search_hint or "")
  normalized_hint = re.sub(r"\s+", " ", normalized_hint).strip()
  return _search_web_price(
    region=region,
    currency_code=currency_code,
    service_name=service_name,
    sku_name=None,
    meter_name=None,
    price_type="Consumption",
    reservation_term=None,
    search_hint=normalized_hint or None,
    session=session,
  )


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
  )
  cache = load_cache()

  cached = cache.get(resolved_key)
  if isinstance(cached, dict):
    cached_best = cached.get("best")
    cached_note = str(cached.get("note", ""))
    return {
      "source": "CACHE" if cached_best else "NONE",
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

  web_attempt_links: List[str] = []

  # 2) Web search (strict)
  web_attempt = _search_web_price(
    region=region,
    currency_code=currency_code,
    service_name=service_name,
    sku_name=sku_name,
    meter_name=meter_name,
    price_type=price_type,
    reservation_term=reservation_term,
    search_hint=search_hint,
  )
  for link in web_attempt.get("links", []):
    if link not in web_attempt_links:
      web_attempt_links.append(link)
  web_best = web_attempt.get("best")
  if web_best:
    resolved = {
      "source": "WEB",
      "best": web_best,
      "links": web_attempt.get("links", web_best.get("sourceLinks", [])),
      "note": "[WEB_ESTIMATE] Verify before final quote",
    }
    _save_resolved_cache(resolved_key, resolved)
    return resolved

  # 2b) Web search (relaxed): trigger when SKU/product mapping appears incomplete.
  if any([sku_name, target_sku, meter_contains, product_contains]):
    relaxed_hint = " ".join(
      [
        search_hint or "",
        sku_name or "",
        target_sku or "",
        meter_contains or "",
        product_contains or "",
      ]
    ).strip()
    web_relaxed_attempt = _search_web_price_relaxed(
      region=region,
      currency_code=currency_code,
      service_name=service_name,
      search_hint=relaxed_hint or None,
    )
    for link in web_relaxed_attempt.get("links", []):
      if link not in web_attempt_links:
        web_attempt_links.append(link)
    web_relaxed = web_relaxed_attempt.get("best")
    if web_relaxed:
      resolved = {
        "source": "WEB",
        "best": web_relaxed,
        "links": web_relaxed_attempt.get("links", web_relaxed.get("sourceLinks", [])),
        "note": "[WEB_ESTIMATE_RELAXED] API filters missed; verify before final quote",
      }
      _save_resolved_cache(resolved_key, resolved)
      return resolved

  resolved = {
    "source": "NONE",
    "best": None,
    "links": web_attempt_links,
    "note": "[VALIDATE] Price not resolved via API, web (strict/relaxed), or cache; [WEB_ATTEMPTED]",
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

  if meter_contains:
    matches = [i for i in candidates if _contains(str(i.get("meterName", "")), meter_contains)]
    if matches:
      candidates = matches

  positive = [i for i in candidates if float(i.get("retailPrice", 0.0) or 0.0) > 0.0]
  if positive and not allow_zero_price:
    candidates = positive

  return min(candidates, key=lambda x: x.get("retailPrice", float("inf")))


def save_cache(cache_path: Path, key: str, result: Dict[str, Any]) -> None:
  cache: Dict[str, Any] = {}
  if cache_path.exists():
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
  cache[key] = result
  cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")


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
