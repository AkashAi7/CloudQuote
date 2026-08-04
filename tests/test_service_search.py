import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from service_search import (
  describe_line_equivalence,
  load_catalog,
  resolve_equivalents,
  reverse_lookup,
  search_services,
  to_csv,
)


class ServiceSearchTests(unittest.TestCase):
  def test_catalog_loads(self) -> None:
    self.assertTrue(load_catalog())

  def test_search_matches_alias_and_capability_keyword(self) -> None:
    self.assertEqual("Microsoft Fabric", search_services("fabric")[0]["name"])
    self.assertIn("Microsoft Fabric", [match["name"] for match in search_services("lakehouse analytics")])

  def test_fabric_resolves_to_composite_aws_products(self) -> None:
    resolution = resolve_equivalents("fabric", "aws")

    self.assertEqual("composite", resolution["type"])
    names = [component["name"] for component in resolution["components"]]
    self.assertIn("Amazon Redshift", names)
    self.assertIn("AWS Glue", names)
    self.assertTrue(any("no single aws equivalent" in item.lower() for item in resolution["validations"]))

  def test_direct_equivalence_has_no_composite_blocker(self) -> None:
    resolution = resolve_equivalents("Azure Virtual Machines", "aws")

    self.assertEqual("direct", resolution["type"])
    self.assertEqual(["Amazon EC2"], [component["name"] for component in resolution["components"]])
    self.assertEqual([], resolution["validations"])

  def test_unknown_service_is_flagged_for_research(self) -> None:
    resolution = resolve_equivalents("completely unknown widget service", "aws")

    self.assertFalse(resolution["matched"])
    self.assertTrue(resolution["validations"])

  def test_reverse_lookup_finds_azure_products_covering_an_aws_product(self) -> None:
    matches = reverse_lookup("Amazon Redshift", source_provider="azure")
    services = [match["service"] for match in matches]

    self.assertIn("Azure Synapse Analytics", services)
    self.assertIn("Microsoft Fabric", services)

  def test_aws_line_resolves_direct_azure_target_first(self) -> None:
    resolution = describe_line_equivalence("Amazon Redshift", "aws", "azure")

    self.assertEqual("direct", resolution["type"])
    self.assertEqual("Azure Synapse Analytics", resolution["service"])

  def test_azure_sourced_line_converts_to_aws(self) -> None:
    resolution = describe_line_equivalence("Microsoft Fabric", "azure", "aws")

    self.assertEqual("composite", resolution["type"])
    self.assertIn("Amazon QuickSight", [component["name"] for component in resolution["components"]])

  def test_typo_still_resolves_to_the_right_product(self) -> None:
    self.assertEqual("Microsoft Fabric", search_services("fabrik")[0]["name"])

  def test_plural_and_spacing_variants_rank_the_same_product_first(self) -> None:
    for query in ["virtual machine", "virtual machines", "  Virtual   Machines  "]:
      with self.subTest(query=query):
        self.assertEqual("Azure Virtual Machines", search_services(query)[0]["name"])

  def test_low_signal_queries_match_nothing(self) -> None:
    for query in ["", "   ", "a", "the cloud service"]:
      with self.subTest(query=query):
        self.assertEqual([], search_services(query))

  def test_non_positive_limit_returns_no_matches(self) -> None:
    self.assertEqual([], search_services("fabric", limit=0))

  def test_capability_keyword_prefers_the_specialised_product(self) -> None:
    self.assertEqual("Microsoft Purview", search_services("data governance")[0]["name"])

  def test_malformed_catalog_entries_do_not_break_search(self) -> None:
    catalog = [
      {"name": "Broken", "provider": "azure", "equivalents": {"aws": {"components": [None, "junk"]}}},
      {"name": "Azure Widget", "provider": "azure", "aliases": ["widget"], "equivalents": None},
    ]

    self.assertEqual("Azure Widget", search_services("widget", catalog=catalog)[0]["name"])
    self.assertEqual([], reverse_lookup("anything", source_provider="azure", catalog=catalog))


  def test_csv_export_emits_one_row_per_component(self) -> None:
    resolution = resolve_equivalents("fabric", "aws")
    rendered = to_csv([resolution])
    body = [line for line in rendered.strip().splitlines() if line]

    self.assertIn("Target component", body[0])
    self.assertEqual(len(resolution["components"]) + 1, len(body))


if __name__ == "__main__":
  unittest.main()
