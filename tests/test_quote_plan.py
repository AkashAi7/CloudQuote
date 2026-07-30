import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from quote_plan import QuotePlanError, apply_quote_plan, build_quote_plan


class QuotePlanTests(unittest.TestCase):
  def setUp(self) -> None:
    self.normalized = {
      "aws_boq": [{
        "Service": "EC2",
        "Instance/SKU": "m5.xlarge",
        "Quantity": 1,
        "Capacity": "4 vCPU / 16 GB",
        "Azure Service": "Virtual Machines",
        "Azure SKU": "Standard_D4s_v5",
      }]
    }

  def test_agent_override_reaches_normalized_input(self) -> None:
    plan = build_quote_plan(self.normalized)
    plan["lines"][0]["target"]["sku"] = "Standard_D4as_v5"
    plan["lines"][0]["assumptions"] = ["AMD-compatible workload"]

    result = apply_quote_plan(self.normalized, plan)

    self.assertEqual("Standard_D4as_v5", result["aws_boq"][0]["Azure SKU"])
    self.assertEqual(["AMD-compatible workload"], result["aws_boq"][0]["Mapping Assumptions"])

  def test_invalid_schema_is_rejected(self) -> None:
    plan = build_quote_plan(self.normalized)
    plan["schemaVersion"] = "2.0"

    with self.assertRaises(QuotePlanError):
      apply_quote_plan(self.normalized, plan)

  def test_line_count_must_match_source(self) -> None:
    plan = build_quote_plan(self.normalized)
    plan["lines"].append(dict(plan["lines"][0], id="duplicate-row"))

    with self.assertRaises(QuotePlanError):
      apply_quote_plan(self.normalized, plan)

  def test_reviewed_pricing_evidence_reaches_normalized_input(self) -> None:
    plan = build_quote_plan(self.normalized)
    evidence = {
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
      "retrievedAt": "2026-07-30T12:00:00+00:00",
      "evidenceUrl": "https://azure.microsoft.com/pricing/details/virtual-machines/",
    }
    plan["lines"][0]["pricingEvidence"] = [evidence]

    result = apply_quote_plan(self.normalized, plan)

    self.assertEqual([evidence], result["aws_boq"][0]["Pricing Evidence"])

  def test_incomplete_pricing_evidence_is_rejected(self) -> None:
    plan = build_quote_plan(self.normalized)
    plan["lines"][0]["pricingEvidence"] = [{"source": "mcp-web", "status": "approved"}]

    with self.assertRaisesRegex(QuotePlanError, "pricing evidence"):
      apply_quote_plan(self.normalized, plan)


if __name__ == "__main__":
  unittest.main()