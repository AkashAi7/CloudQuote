import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from providers.catalog import _github_live_prices, _load_catalogs, resolve_catalog_price
from providers.evidence import resolve_reviewed_evidence
from providers.targets import require_target_provider


class _Response:
  def __init__(self, text: str | None = None, content_type: str = "text/html") -> None:
    self.text = text if text is not None else (
      "Free $0 USD per user/month Team $4 USD per user/month Enterprise $21 USD per user/month"
    )
    self.headers = {"Content-Type": content_type}

  def raise_for_status(self) -> None:
    return None


class _Session:
  def __init__(self, response: _Response | None = None, error: Exception | None = None, fail_times: int = 0) -> None:
    self._response = response or _Response()
    self._error = error
    self._fail_times = fail_times
    self.calls = 0

  def get(self, *_args, **_kwargs) -> _Response:
    self.calls += 1
    if self._error is not None and self.calls > self._fail_times:
      raise self._error
    if self.calls <= self._fail_times:
      raise RuntimeError("transient failure")
    return self._response


class ProviderTests(unittest.TestCase):
  def _reviewed_evidence(self) -> dict:
    return {
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
    }

  def test_reviewed_evidence_requires_exact_dimensions(self) -> None:
    result = resolve_reviewed_evidence(
      [self._reviewed_evidence()],
      provider="azure",
      region="eastus",
      currency="USD",
      service="Virtual Machines",
      sku="Standard_D4s_v5",
      price_type="Consumption",
      reservation_term=None,
    )

    self.assertEqual("EVIDENCE", result["source"])
    self.assertEqual(0.192, result["best"]["retailPrice"])

  def test_reviewed_evidence_rejects_region_mismatch(self) -> None:
    result = resolve_reviewed_evidence(
      [self._reviewed_evidence()],
      provider="azure",
      region="centralindia",
      currency="USD",
      service="Virtual Machines",
      sku="Standard_D4s_v5",
      price_type="Consumption",
      reservation_term=None,
    )

    self.assertIsNone(result)

  def test_github_team_uses_official_per_user_price(self) -> None:
    result = resolve_catalog_price("github", "GitHub Team", 25, "USD", session=_Session())

    self.assertEqual(4, result["unit_price"])
    self.assertEqual(100, result["monthly"])
    self.assertFalse(result["validate"])
    self.assertEqual(["https://github.com/pricing"], result["source_links"])

  def test_fresh_verified_catalog_skips_http_refresh(self) -> None:
    catalogs = copy.deepcopy(_load_catalogs())
    catalogs["catalogs"]["github"]["verifiedAt"] = datetime.now(timezone.utc).isoformat()
    with (
      patch("providers.catalog._load_catalogs", return_value=catalogs),
      patch("providers.catalog._github_live_prices") as live_prices,
    ):
      result = resolve_catalog_price("github", "GitHub Team", 25, "USD", session=_Session())

    self.assertEqual(100, result["monthly"])
    live_prices.assert_not_called()

  def test_live_fetch_retries_transient_failures(self) -> None:
    session = _Session(fail_times=2)
    with patch("providers.catalog.time.sleep"):
      prices = _github_live_prices("https://github.com/pricing", session)

    self.assertEqual(3, session.calls)
    self.assertEqual(4, prices["team"])

  def test_live_fetch_rejects_non_https_url(self) -> None:
    with self.assertRaises(ValueError):
      _github_live_prices("http://github.com/pricing", _Session())

  def test_live_fetch_rejects_non_html_content_type(self) -> None:
    session = _Session(_Response(content_type="application/octet-stream"))
    with patch("providers.catalog.time.sleep"):
      with self.assertRaises(ValueError):
        _github_live_prices("https://github.com/pricing", session)

  def test_live_fetch_strips_scripts_and_decodes_entities(self) -> None:
    page = (
      "<script>var team = 'Team $999 USD per user/month';</script>"
      "<p>Team &#36;4 USD per user&nbsp;/ month</p>"
    )
    prices = _github_live_prices("https://github.com/pricing", _Session(_Response(page)))

    self.assertEqual(4, prices["team"])

  def test_implausible_live_price_falls_back_to_verified_catalog(self) -> None:
    with patch("providers.catalog._github_live_prices", return_value={"team": 4000.0}):
      result = resolve_catalog_price("github", "GitHub Team", 25, "USD", session=_Session())

    self.assertEqual(100, result["monthly"])
    self.assertIn("OFFICIAL_CATALOG_FALLBACK", result["source_note"])

  def test_plausible_live_price_is_used(self) -> None:
    with patch("providers.catalog._github_live_prices", return_value={"team": 5.0}):
      result = resolve_catalog_price("github", "GitHub Team", 25, "USD", session=_Session())

    self.assertEqual(125, result["monthly"])

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

  def test_aws_and_gcp_adapters_support_plan_validation_only(self) -> None:
    for provider in ["aws", "gcp"]:
      adapter = require_target_provider(provider)
      plan = {
        "targetProvider": provider,
        "lines": [{"target": {"provider": provider}}],
      }
      adapter.validate_plan(plan)
      self.assertIn("plan", adapter.capabilities)
      with self.assertRaisesRegex(ValueError, "pricing and workbook backend"):
        adapter.require_capability("compile")

  def test_unknown_target_provider_is_rejected(self) -> None:
    with self.assertRaisesRegex(ValueError, "not implemented"):
      require_target_provider("external")


if __name__ == "__main__":
  unittest.main()