from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class TargetProviderAdapter:
  name: str
  workbook_label: str

  def validate_plan(self, plan: Dict[str, Any]) -> None:
    if plan.get("targetProvider") != self.name:
      raise ValueError(f"Plan targetProvider must be {self.name!r}")


TARGET_PROVIDERS = {
  "azure": TargetProviderAdapter(name="azure", workbook_label="Azure"),
}


def require_target_provider(name: str) -> TargetProviderAdapter:
  normalized = name.strip().lower()
  adapter = TARGET_PROVIDERS.get(normalized)
  if not adapter:
    available = ", ".join(sorted(TARGET_PROVIDERS))
    raise ValueError(f"Target provider {normalized!r} is not implemented; available adapters: {available}")
  return adapter