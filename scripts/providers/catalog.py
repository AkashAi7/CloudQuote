import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import requests
import yaml


CATALOG_PATH = Path(__file__).resolve().parents[2] / "mappings" / "public_catalogs.yaml"


def _load_catalogs() -> Dict[str, Any]:
  return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}


def _github_live_prices(url: str, session: requests.Session) -> Dict[str, float]:
  response = session.get(url, timeout=20, headers={"User-Agent": "CloudQuote/1.0"})
  response.raise_for_status()
  text = re.sub(r"<[^>]+>", " ", response.text)
  text = re.sub(r"\s+", " ", text)
  prices: Dict[str, float] = {}
  for plan in ["Free", "Team", "Enterprise"]:
    match = re.search(
      rf"\b{plan}\b.{{0,500}}?\$\s*([0-9]+(?:\.[0-9]+)?)\s*USD\s*per user/month",
      text,
      flags=re.IGNORECASE,
    )
    if match:
      prices[plan.lower()] = float(match.group(1))
  return prices


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
  retrieved_at = str(catalog.get("verifiedAt", ""))
  source_note = "[OFFICIAL_CATALOG_FALLBACK]"
  live_resolved = False
  if catalog_name.lower() == "github" and evidence_url:
    try:
      live_prices = _github_live_prices(evidence_url, session or requests.Session())
      if normalized_sku in live_prices:
        unit_price = live_prices[normalized_sku]
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