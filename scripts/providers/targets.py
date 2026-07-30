from dataclasses import dataclass
from typing import Any, Dict, FrozenSet


@dataclass(frozen=True)
class TargetProviderAdapter:
  name: str
  workbook_label: str
  capabilities: FrozenSet[str]
  pricing_backend: str | None = None

  def validate_plan(self, plan: Dict[str, Any]) -> None:
    if plan.get("targetProvider") != self.name:
      raise ValueError(f"Plan targetProvider must be {self.name!r}")
    for line in plan.get("lines", []):
      if line.get("target", {}).get("provider") != self.name:
        raise ValueError(f"Every target line must use provider {self.name!r}")

  def require_capability(self, capability: str) -> None:
    if capability not in self.capabilities:
      raise ValueError(
        f"Target provider {self.name!r} supports plan validation but not {capability!r}; "
        "a provider-specific pricing and workbook backend is required"
      )


TARGET_PROVIDERS = {
  "aws": TargetProviderAdapter(
    name="aws",
    workbook_label="AWS",
    capabilities=frozenset({"plan"}),
  ),
  "azure": TargetProviderAdapter(
    name="azure",
    workbook_label="Azure",
    capabilities=frozenset({"plan", "compile", "live-pricing"}),
    pricing_backend="azure-retail-prices",
  ),
  "gcp": TargetProviderAdapter(
    name="gcp",
    workbook_label="Google Cloud",
    capabilities=frozenset({"plan"}),
  ),
}


def require_target_provider(name: str) -> TargetProviderAdapter:
  normalized = name.strip().lower()
  adapter = TARGET_PROVIDERS.get(normalized)
  if not adapter:
    available = ", ".join(sorted(TARGET_PROVIDERS))
    raise ValueError(f"Target provider {normalized!r} is not implemented; available adapters: {available}")
  return adapter