import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_workbook import _build_pricing_metrics, _lookup_live_price, _price_profile
from parse_inputs import _infer_service


class WorkbookGuardrailTests(unittest.TestCase):
  def test_pricing_metrics_track_coverage_fallbacks_and_latency(self) -> None:
    telemetry = _build_pricing_metrics([
      {"source": "API", "fallback_attempted": False},
      {"source": "EVIDENCE", "fallback_attempted": True, "fallback_succeeded": True, "fallback_latency_ms": 12.0},
      {"source": "NONE", "fallback_attempted": True, "fallback_succeeded": False, "fallback_latency_ms": 8.0},
      {"source": "CACHE", "fallback_attempted": False},
    ])

    metrics = telemetry["pricingMetrics"]
    self.assertEqual(0.25, metrics["unresolvedRate"])
    self.assertEqual(0.25, metrics["sourceCoverage"]["EVIDENCE"]["rate"])
    self.assertEqual(2, metrics["fallbackAttempts"])
    self.assertEqual(0.5, metrics["fallbackSuccessRate"])
    self.assertEqual(10.0, metrics["fallbackLatencyMsAverage"])

  def test_composite_services_have_executable_validation(self) -> None:
    cases = [
      ("EBS", "Azure Managed Disks", "Premium SSD v2"),
      ("S3", "Azure Blob Storage", "Hot LRS"),
      ("RDS", "Azure Database for PostgreSQL", "General Purpose"),
      ("Lambda", "Azure Functions", "Consumption"),
      ("EKS", "Azure Kubernetes Service", "Standard"),
      ("Redshift", "Azure Synapse Analytics", "Dedicated SQL Pool"),
    ]
    for service, target_service, target_sku in cases:
      with self.subTest(service=service):
        profile = _price_profile(service, target_service, target_sku, "", "")
        self.assertTrue(profile.get("conversion_validation") or profile.get("force_validate"))

  def test_github_routes_to_official_catalog(self) -> None:
    profile = _price_profile("GitHub", "GitHub", "GitHub Team", "25 users", "GitHub Team")

    self.assertEqual("official_catalog", profile["pricing_provider"])
    self.assertEqual("github", profile["catalog_name"])

  def test_github_is_inferred_from_raw_boq_text(self) -> None:
    self.assertEqual("github", _infer_service("25 developer seats", "GitHub Team", ""))

  def test_validation_only_line_skips_network_pricing(self) -> None:
    profile = _price_profile("EKS", "Azure Kubernetes Service", "Standard", "2 clusters", "Managed Cluster")
    with patch("build_workbook.resolve_best_price") as resolve:
      result = _lookup_live_price("eastus", "USD", profile, "moderate", 2)

    self.assertTrue(result["validate"])
    self.assertIn("lookup skipped", result["source_note"].lower())
    resolve.assert_not_called()

  def test_web_estimate_is_evidence_not_authoritative_total(self) -> None:
    profile = _price_profile("EC2", "Virtual Machines", "D2s v5", "", "")
    web_result = {
      "source": "WEB",
      "best": {
        "retailPrice": 0.25,
        "unitOfMeasure": "Web Estimated Unit",
        "effectiveStartDate": "2026-07-30",
      },
      "links": ["https://azure.microsoft.com/pricing/details/virtual-machines"],
      "note": "[WEB_ESTIMATE] Verify before final quote",
    }
    with patch("build_workbook.resolve_best_price", return_value=web_result):
      result = _lookup_live_price("eastus", "USD", profile, "moderate", 730, source_unit="Hours")

    self.assertTrue(result["validate"])
    self.assertEqual(0.25, result["unit_price"])
    self.assertEqual(0.0, result["monthly"])
    self.assertEqual("WEB", result["source"])
    self.assertIn("Verify", result["source_note"])

  def test_cached_web_estimate_remains_validation_only(self) -> None:
    profile = _price_profile("EC2", "Virtual Machines", "D2s v5", "", "")
    cached_web_result = {
      "source": "CACHE",
      "originSource": "WEB",
      "best": {
        "retailPrice": 0.25,
        "unitOfMeasure": "Web Estimated Unit",
        "effectiveStartDate": "2026-07-30",
      },
      "links": ["https://azure.microsoft.com/pricing/details/virtual-machines"],
      "note": "[CACHE_HIT] Using previously resolved price",
    }
    with patch("build_workbook.resolve_best_price", return_value=cached_web_result):
      result = _lookup_live_price("eastus", "USD", profile, "moderate", 730, source_unit="Hours")

    self.assertTrue(result["validate"])
    self.assertEqual(0.0, result["monthly"])

  def test_reviewed_evidence_is_forwarded_to_pricing(self) -> None:
    evidence = [{"source": "mcp-web", "status": "approved"}]
    profile = _price_profile("EC2", "Virtual Machines", "D2s v5", "", "")
    profile["pricing_evidence"] = evidence
    resolved = {
      "source": "EVIDENCE",
      "best": {
        "retailPrice": 0.25,
        "unitOfMeasure": "1 Hour",
        "effectiveStartDate": "2026-07-30",
      },
      "links": ["https://azure.microsoft.com/pricing/details/virtual-machines"],
      "note": "[AGENT_EVIDENCE] approved",
    }
    with patch("build_workbook.resolve_best_price", return_value=resolved) as resolve:
      result = _lookup_live_price("eastus", "USD", profile, "conservative", 730, source_unit="Hours")

    self.assertFalse(result["validate"])
    self.assertEqual(182.5, result["monthly"])
    self.assertEqual("EVIDENCE", result["source"])
    self.assertEqual(evidence, resolve.call_args.kwargs["reviewed_evidence"])


if __name__ == "__main__":
  unittest.main()