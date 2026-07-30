import os
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pricing import fetch_prices


@unittest.skipUnless(
  os.getenv("CLOUDQUOTE_LIVE_PRICING_CANARY", "").lower() in {"1", "true", "yes"},
  "Set CLOUDQUOTE_LIVE_PRICING_CANARY=true to run live Azure pricing checks",
)
class LivePricingCanaryTests(unittest.TestCase):
  def test_azure_retail_prices_returns_positive_vm_meter(self) -> None:
    prices = fetch_prices(
      region="centralindia",
      currency_code="USD",
      service_name="Virtual Machines",
      sku_name="E8s v5",
      meter_name=None,
      price_type="Consumption",
      reservation_term=None,
      fallback_to_cache=False,
    )

    self.assertTrue(prices)
    self.assertTrue(any(float(item.get("retailPrice", 0.0)) > 0 for item in prices))


if __name__ == "__main__":
  unittest.main()
