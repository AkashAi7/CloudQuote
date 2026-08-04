from __future__ import annotations

import html
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict
from urllib.parse import urlparse

import yaml

if TYPE_CHECKING:
  import requests


CATALOG_PATH = Path(__file__).resolve().parents[2] / "mappings" / "public_catalogs.yaml"


def _load_catalogs() -> Dict[str, Any]:
  return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}


LIVE_FETCH_TIMEOUT_SECONDS = 20
LIVE_FETCH_ATTEMPTS = 3
LIVE_FETCH_BACKOFF_SECONDS = 0.5
# Guard against an unexpectedly large or non-HTML response being regex-scanned.
LIVE_FETCH_MAX_BYTES = 4 * 1024 * 1024
# A live price that deviates this far from the verified catalog price is treated
# as a parsing artefact rather than a genuine change, and is discarded.
LIVE_PRICE_MAX_DEVIATION = 5.0
ALLOWED_LIVE_SCHEMES = {"https"}


def _new_session():
  import requests

  return requests.Session()


def _fetch_live_page(url: str, session: requests.Session) -> str:
  """Fetch a public pricing page with retries, scheme and size validation."""
  parsed = urlparse(url)
  if parsed.scheme not in ALLOWED_LIVE_SCHEMES or not parsed.netloc:
    raise ValueError(f"Refusing to fetch pricing page over unsupported URL: {url}")

  last_error: Exception | None = None
  for attempt in range(LIVE_FETCH_ATTEMPTS):
    try:
      response = session.get(
        url,
        timeout=LIVE_FETCH_TIMEOUT_SECONDS,
        headers={"User-Agent": "CloudQuote/1.0", "Accept": "text/html"},
      )
      response.raise_for_status()
      content_type = str(getattr(response, "headers", {}).get("Content-Type", "") or "")
      text = response.text or ""
      if content_type:
        if "html" not in content_type.lower() and "text" not in content_type.lower():
          raise ValueError(f"Unexpected content type for pricing page: {content_type}")
      elif not re.search(r"(?i)<(!doctype|html|body|div|p|span)\b", text[:4096]):
        # No Content-Type header, so fall back to sniffing for markup rather than
        # regex-scanning an arbitrary binary or JSON body.
        raise ValueError("Pricing page response did not declare or resemble HTML")
      if len(text) > LIVE_FETCH_MAX_BYTES:
        raise ValueError("Pricing page response exceeded the maximum supported size")
      if not text.strip():
        raise ValueError("Pricing page response was empty")
      return text
    except ValueError:
      # Deterministic rejection of the response itself; retrying cannot help.
      raise
    except Exception as error:  # transient; retried below, then the caller degrades to the fallback
      last_error = error
      if attempt + 1 < LIVE_FETCH_ATTEMPTS:
        time.sleep(LIVE_FETCH_BACKOFF_SECONDS * (2**attempt))
  raise last_error if last_error else RuntimeError("Pricing page fetch failed")


def _github_live_prices(url: str, session: requests.Session) -> Dict[str, float]:
  raw = _fetch_live_page(url, session)
  text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
  text = re.sub(r"<[^>]+>", " ", text)
  text = html.unescape(text)
  text = re.sub(r"\s+", " ", text)
  prices: Dict[str, float] = {}
  for plan in ["Free", "Team", "Enterprise"]:
    match = re.search(
      rf"\b{plan}\b.{{0,500}}?\$\s*([0-9]+(?:\.[0-9]+)?)\s*USD\s*per user\s*/\s*month",
      text,
      flags=re.IGNORECASE,
    )
    if not match:
      continue
    try:
      value = float(match.group(1))
    except ValueError:
      continue
    if value < 0:
      continue
    prices[plan.lower()] = value
  return prices


def _live_price_is_plausible(live_price: float, catalog_price: float) -> bool:
  """Reject scraped prices that differ implausibly from the verified catalog.

  A parsing artefact (matching the wrong plan block, or a marketing figure) shows
  up as an order-of-magnitude jump, so those are discarded in favour of the
  verified fallback price rather than silently quoted.
  """
  if live_price < 0:
    return False
  if catalog_price <= 0:
    return live_price == 0
  ratio = live_price / catalog_price
  return 1.0 / LIVE_PRICE_MAX_DEVIATION <= ratio <= LIVE_PRICE_MAX_DEVIATION


def resolve_catalog_price(
  catalog_name: str,
  sku: str,
  quantity: float,
  currency: str,
  session: requests.Session | None = None,
) -> Dict[str, Any]:
  catalogs = _load_catalogs()
  catalog = catalogs.get("catalogs", {}).get(catalog_name.lower())
  if not catalog:
    return {"matched": False, "validate": True, "note": f"[VALIDATE] Unknown official catalog: {catalog_name}"}

  aliases = {str(key).lower(): str(value).lower() for key, value in catalog.get("aliases", {}).items()}
  normalized_sku = aliases.get(sku.strip().lower(), sku.strip().lower())
  plans = catalog.get("plans", {})
  plan = plans.get(normalized_sku)
  evidence_url = str(catalog.get("pricingUrl", ""))
  if not plan:
    return {
      "matched": False,
      "validate": True,
      "note": f"[VALIDATE] {catalog_name} SKU/add-on is not in the verified public catalog: {sku or 'unspecified'}",
      "source": "WEB",
      "source_links": [evidence_url] if evidence_url else [],
    }

  unit_price = float(plan["unitPrice"])
  catalog_price = unit_price
  retrieved_at = str(catalog.get("verifiedAt", ""))
  source_note = "[OFFICIAL_CATALOG_FALLBACK]"
  live_resolved = False
  try:
    verified_at = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    refresh_due = datetime.now(timezone.utc) - verified_at > timedelta(
      hours=float(catalog.get("liveRefreshHours", 24))
    )
  except ValueError:
    refresh_due = True
  if catalog_name.lower() == "github" and evidence_url and refresh_due:
    try:
      live_prices = _github_live_prices(evidence_url, session or _new_session())
      live_price = live_prices.get(normalized_sku)
      if live_price is not None and _live_price_is_plausible(live_price, catalog_price):
        unit_price = live_price
        retrieved_at = datetime.now(timezone.utc).isoformat()
        source_note = "[OFFICIAL_CATALOG_LIVE]"
        live_resolved = True
    except Exception:
      pass

  catalog_currency = str(catalog.get("currency", "USD")).upper()
  unit = str(catalog.get("unitOfMeasure", "1 User/Month"))
  currency_mismatch = currency.upper() != catalog_currency
  starting_at = bool(plan.get("startingAt", False))
  fallback_stale = False
  if not live_resolved:
    try:
      verified_at = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
      fallback_stale = datetime.now(timezone.utc) - verified_at > timedelta(
        hours=float(catalog.get("maxFallbackAgeHours", 168))
      )
    except ValueError:
      fallback_stale = True
  validate = currency_mismatch or fallback_stale or starting_at
  if currency_mismatch:
    note = f"[VALIDATE] Official catalog is {catalog_currency}; FX conversion to {currency.upper()} is required"
  elif fallback_stale:
    note = "[VALIDATE] Official catalog fallback is stale and the live pricing page could not be refreshed"
  elif starting_at:
    note = "[VALIDATE] Official price is a starting-at rate; contract terms and add-ons require confirmation"
  else:
    note = "official_catalog_per_user_month"
  return {
    "matched": True,
    "unit_price": unit_price,
    "monthly": 0.0 if validate else unit_price * quantity,
    "annual": 0.0 if validate else unit_price * quantity * 12.0,
    "uom": unit,
    "price_date": retrieved_at,
    "note": note,
    "validate": validate,
    "resolved_sku": str(plan.get("displayName", normalized_sku.title())),
    "source": "WEB",
    "source_links": [evidence_url] if evidence_url else [],
    "source_note": f"{source_note} Retrieved {retrieved_at}",
  }