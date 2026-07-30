import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FastPathTests(unittest.TestCase):
  def test_cloudquote_agent_has_guarded_web_fallback(self) -> None:
    agent = (ROOT / ".github" / "agents" / "cloudquote.agent.md").read_text(encoding="utf-8")
    skill = (ROOT / ".github" / "skills" / "cloudquote-boq" / "SKILL.md").read_text(encoding="utf-8")

    self.assertIn("tools: [read, search, execute, web]", agent)
    self.assertIn("--enable-web-search", skill)

  def test_csv_normalization_does_not_import_pandas(self) -> None:
    code = (
      "import sys; "
      f"sys.path.insert(0, {str(ROOT / 'scripts')!r}); "
      "from pathlib import Path; "
      "from parse_inputs import _read_aws_boq; "
      f"rows=_read_aws_boq(Path({str(ROOT / 'samples' / 'aws_boq.csv')!r})); "
      "assert rows and 'pandas' not in sys.modules"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    self.assertEqual(0, result.returncode, result.stderr)

  def test_pricing_import_does_not_import_requests(self) -> None:
    code = (
      "import sys; "
      f"sys.path.insert(0, {str(ROOT / 'scripts')!r}); "
      "import pricing; "
      "assert 'requests' not in sys.modules"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
  unittest.main()