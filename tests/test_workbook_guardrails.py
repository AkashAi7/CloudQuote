import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_workbook import _lookup_live_price, _price_profile
from parse_inputs import _infer_service


class WorkbookGuardrailTests(unittest.TestCase):
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


if __name__ == "__main__":
  unittest.main()