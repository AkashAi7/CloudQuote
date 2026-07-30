from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


def _same(left: Any, right: Any) -> bool:
  return str(left or "").strip().casefold() == str(right or "").strip().casefold()


def resolve_reviewed_evidence(
  evidence_items: List[Dict[str, Any]],
  *,
  provider: str,
  region: str,
  currency: str,
  service: str,
  sku: str,
  price_type: str,
  reservation_term: str | None,
  max_age_hours: float = 168.0,
) -> Dict[str, Any] | None:
  now = datetime.now(timezone.utc)
  for evidence in evidence_items:
    if evidence.get("status") != "approved":
      continue
    if not all([
      _same(evidence.get("provider"), provider),
      _same(evidence.get("region"), region),
      _same(evidence.get("currency"), currency),
      _same(evidence.get("service"), service),
      _same(evidence.get("sku"), sku),
      _same(evidence.get("priceType"), price_type),
    ]):
      continue
    if price_type == "Reservation" and not _same(evidence.get("reservationTerm"), reservation_term):
      continue
    try:
      retrieved_at = datetime.fromisoformat(str(evidence["retrievedAt"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
      continue
    if retrieved_at.tzinfo is None or now - retrieved_at > timedelta(hours=max_age_hours):
      continue

    source_url = str(evidence.get("evidenceUrl", ""))
    source_kind = str(evidence.get("source", "manual"))
    return {
      "source": "EVIDENCE",
      "originSource": source_kind,
      "best": {
        "retailPrice": float(evidence["unitPrice"]),
        "unitOfMeasure": str(evidence["unitOfMeasure"]),
        "effectiveStartDate": retrieved_at.date().isoformat(),
        "serviceName": str(evidence["service"]),
        "skuName": str(evidence["sku"]),
        "meterName": str(evidence["meterName"]),
        "productName": "Reviewed agent pricing evidence",
        "sourceLinks": [source_url],
      },
      "links": [source_url],
      "note": f"[AGENT_EVIDENCE] Approved {source_kind} evidence retrieved {retrieved_at.isoformat()}",
    }
  return None