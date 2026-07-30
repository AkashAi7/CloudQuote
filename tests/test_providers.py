import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from providers.catalog import resolve_catalog_price
from providers.targets import require_target_provider


class _Response:
  text = "Free $0 USD per user/month Team $4 USD per user/month Enterprise $21 USD per user/month"

  def raise_for_status(self) -> None:
    return None


class _Session:
  def get(self, *_args, **_kwargs) -> _Response:
    return _Response()


class ProviderTests(unittest.TestCase):
  def test_github_team_uses_official_per_user_price(self) -> None:
    result = resolve_catalog_price("github", "GitHub Team", 25, "USD", session=_Session())

    self.assertEqual(4, result["unit_price"])
    self.assertEqual(100, result["monthly"])
    self.assertFalse(result["validate"])
    self.assertEqual(["https://github.com/pricing"], result["source_links"])

  def test_fresh_verified_catalog_skips_http_refresh(self) -> None:
    with patch("providers.catalog._github_live_prices") as live_prices:
      result = resolve_catalog_price("github", "GitHub Team", 25, "USD", session=_Session())

    self.assertEqual(100, result["monthly"])
    live_prices.assert_not_called()

  def test_catalog_currency_mismatch_is_flagged(self) -> None:
    result = resolve_catalog_price("github", "Team", 25, "INR", session=_Session())

    self.assertTrue(result["validate"])
    self.assertEqual(0, result["monthly"])
    self.assertIn("FX conversion", result["note"])

  def test_github_enterprise_starting_price_is_flagged(self) -> None:
    result = resolve_catalog_price("github", "Enterprise", 25, "USD", session=_Session())

    self.assertEqual(21, result["unit_price"])
    self.assertTrue(result["validate"])
    self.assertIn("starting-at", result["note"])

  def test_stale_offline_fallback_is_flagged(self) -> None:
    catalog = {
      "catalogs": {
        "github": {
          "pricingUrl": "https://github.com/pricing",
          "currency": "USD",
          "unitOfMeasure": "1 User/Month",
          "verifiedAt": "2020-01-01T00:00:00+00:00",
          "maxFallbackAgeHours": 1,
          "plans": {"team": {"displayName": "GitHub Team", "unitPrice": 4}},
        }
      }
    }
    with patch("providers.catalog._load_catalogs", return_value=catalog):
      with patch("providers.catalog._github_live_prices", side_effect=RuntimeError("offline")):
        result = resolve_catalog_price("github", "Team", 5, "USD")

    self.assertTrue(result["validate"])
    self.assertIn("stale", result["note"])

  def test_unimplemented_target_provider_is_rejected(self) -> None:
    with self.assertRaisesRegex(ValueError, "not implemented"):
      require_target_provider("gcp")


if __name__ == "__main__":
  unittest.main()