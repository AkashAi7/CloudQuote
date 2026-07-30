import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pricing import _cache_entry_is_fresh, _update_cache_entry, _with_cache_timestamp


class PricingCacheTests(unittest.TestCase):
  def test_timestamped_entry_is_fresh(self) -> None:
    self.assertTrue(_cache_entry_is_fresh(_with_cache_timestamp({"best": {}}), 24))

  def test_stale_entry_is_rejected(self) -> None:
    stale = {"cachedAt": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()}
    self.assertFalse(_cache_entry_is_fresh(stale, 24))

  def test_legacy_entry_without_timestamp_is_rejected(self) -> None:
    self.assertFalse(_cache_entry_is_fresh({"best": {}}, 24))

  def test_atomic_updates_preserve_existing_entries(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
      cache_path = Path(directory) / "pricing.json"
      _update_cache_entry("first", {"value": 1}, cache_path)
      _update_cache_entry("second", {"value": 2}, cache_path)

      import json
      cache = json.loads(cache_path.read_text(encoding="utf-8"))
      self.assertEqual({"first", "second"}, set(cache))


if __name__ == "__main__":
  unittest.main()