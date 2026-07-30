import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from unittest.mock import patch

from pricing import _cache_entry_is_fresh, _update_cache_entry, _with_cache_timestamp, flush_cache, resolve_best_price


class PricingCacheTests(unittest.TestCase):
  def test_timestamped_entry_is_fresh(self) -> None:
    self.assertTrue(_cache_entry_is_fresh(_with_cache_timestamp({"best": {}}), 24))

  def test_stale_entry_is_rejected(self) -> None:
    stale = {"cachedAt": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()}
    self.assertFalse(_cache_entry_is_fresh(stale, 24))

  def test_legacy_entry_without_timestamp_is_rejected(self) -> None:
    self.assertFalse(_cache_entry_is_fresh({"best": {}}, 24))

  def test_atomic_updates_preserve_existing_entries(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
      cache_path = Path(directory) / "pricing.json"
      _update_cache_entry("first", {"value": 1}, cache_path)
      _update_cache_entry("second", {"value": 2}, cache_path)

      import json
      cache = json.loads(cache_path.read_text(encoding="utf-8"))
      self.assertEqual({"first", "second"}, set(cache))

  def test_api_miss_without_evidence_is_flagged(self) -> None:
    with patch("pricing.load_cache", return_value={}):
      with patch("pricing.fetch_prices", return_value=[]):
        result = resolve_best_price(
          region="eastus",
          currency_code="USD",
          service_name="Unknown",
          sku_name=None,
          meter_name=None,
          price_type="Consumption",
          reservation_term=None,
        )

    self.assertEqual("NONE", result["source"])
    self.assertIn("approved pricing evidence", result["note"])

  def test_legacy_web_flag_requires_mcp_or_search_api_evidence(self) -> None:
    cached_miss = _with_cache_timestamp({"best": None, "links": [], "note": "cached miss"})
    with patch("pricing.load_cache", return_value={"cached": cached_miss}):
      with patch("pricing._resolved_cache_key", return_value="cached"):
        with patch("pricing.fetch_prices", return_value=[]):
          with patch("pricing._save_resolved_cache"):
            result = resolve_best_price(
              region="eastus",
              currency_code="USD",
              service_name="Unknown",
              sku_name=None,
              meter_name=None,
              price_type="Consumption",
              reservation_term=None,
              enable_web_search=True,
            )

    self.assertEqual("NONE", result["source"])
    self.assertIn("MCP or search-API", result["note"])

  def test_cached_web_price_preserves_origin_source(self) -> None:
    cached_web = _with_cache_timestamp({
      "source": "WEB",
      "best": {"retailPrice": 1.25, "unitOfMeasure": "Web Estimated Unit"},
      "links": ["https://azure.microsoft.com/pricing/details/example"],
    })
    with patch("pricing.load_cache", return_value={"cached": cached_web}):
      with patch("pricing._resolved_cache_key", return_value="cached"):
        result = resolve_best_price(
          region="eastus",
          currency_code="USD",
          service_name="Unknown",
          sku_name=None,
          meter_name=None,
          price_type="Consumption",
          reservation_term=None,
          enable_web_search=True,
        )

    self.assertEqual("CACHE", result["source"])
    self.assertEqual("WEB", result["originSource"])

  def test_reviewed_evidence_resolves_after_api_miss(self) -> None:
    evidence = [{
      "source": "mcp-web",
      "status": "approved",
      "provider": "azure",
      "service": "Virtual Machines",
      "sku": "Standard_D4s_v5",
      "region": "eastus",
      "currency": "USD",
      "priceType": "Consumption",
      "meterName": "D4s v5",
      "unitOfMeasure": "1 Hour",
      "unitPrice": 0.192,
      "retrievedAt": datetime.now(timezone.utc).isoformat(),
      "evidenceUrl": "https://azure.microsoft.com/pricing/details/virtual-machines/",
    }]
    with patch("pricing.load_cache", return_value={}):
      with patch("pricing.fetch_prices", return_value=[]):
        with patch("pricing._save_resolved_cache"):
          result = resolve_best_price(
            region="eastus",
            currency_code="USD",
            service_name="Virtual Machines",
            sku_name="Standard_D4s_v5",
            meter_name=None,
            price_type="Consumption",
            reservation_term=None,
            target_sku="Standard_D4s_v5",
            reviewed_evidence=evidence,
            enable_web_search=True,
          )

    self.assertEqual("EVIDENCE", result["source"])
    self.assertEqual(0.192, result["best"]["retailPrice"])
    self.assertTrue(result["fallbackAttempted"])
    self.assertTrue(result["fallbackSucceeded"])
    self.assertGreaterEqual(result["fallbackLatencyMs"], 0.0)

  @patch.dict("os.environ", {"CLOUDQUOTE_DEFER_CACHE_WRITES": "true"})
  def test_deferred_updates_flush_together(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
      cache_path = Path(directory) / "pricing.json"
      _update_cache_entry("first", {"value": 1}, cache_path)
      _update_cache_entry("second", {"value": 2}, cache_path)
      self.assertFalse(cache_path.exists())

      flush_cache(cache_path)

      import json
      cache = json.loads(cache_path.read_text(encoding="utf-8"))
      self.assertEqual({"first", "second"}, set(cache))


if __name__ == "__main__":
  unittest.main()