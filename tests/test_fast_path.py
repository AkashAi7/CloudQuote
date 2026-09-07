import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FastPathTests(unittest.TestCase):
  def instructions(self, relative_path: str) -> str:
    return " ".join((ROOT / relative_path).read_text(encoding="utf-8").lower().split())

  def test_entrypoints_do_not_hide_material_blockers_or_require_links_only(self) -> None:
    paths = [
      ".github/agents/cloudquote.agent.md", ".github/prompts/cloudquote.prompt.md",
      ".github/skills/cloudquote-boq/SKILL.md", ".github/skills/cloudquote-rfp/SKILL.md",
      ".github/skills/cloudquote-pricing-guardrails/SKILL.md",
      ".github/skills/cloudquote-artifact-delivery/SKILL.md",
    ]
    for path in paths:
      with self.subTest(path=path):
        text = self.instructions(path)
        self.assertNotRegex(text, r"(?:return|output|respond with) (?:only )?(?:artifact )?links only")
        self.assertNotIn("links-only", text)
        self.assertNotRegex(text, r"do not (?:mention|show|surface) (?:material )?blockers")
    delivery = self.instructions(".github/skills/cloudquote-artifact-delivery/SKILL.md")
    self.assertIn("do not suppress material blockers", delivery)
    self.assertIn("partial/internal", delivery)

  def test_rfp_quotes_always_use_reviewed_plan_path(self) -> None:
    boq = self.instructions(".github/skills/cloudquote-boq/SKILL.md")
    self.assertIn("required for any rfp-derived quote", boq)
    self.assertIn("opportunityreview", boq)
    agent = self.instructions(".github/agents/cloudquote.agent.md")
    self.assertRegex(agent, r"rfp-derived inputs.*require the reviewed-plan path")
    prompt = self.instructions(".github/prompts/cloudquote.prompt.md")
    self.assertIn("require a reviewed plan for rfp-derived inputs", prompt)

  def test_seller_triage_is_available_without_compilation(self) -> None:
    rfp = self.instructions(".github/skills/cloudquote-rfp/SKILL.md")
    for mode in ("quick-triage", "working-estimate", "submission-ready"):
      self.assertIn(mode, rfp)
    self.assertIn("no compiler or workbook required", rfp)
    self.assertIn("requesting this mode is not approval", rfp)
    agent = self.instructions(".github/agents/cloudquote.agent.md")
    self.assertIn("triage does not require a compiler", agent)
    prompt = self.instructions(".github/prompts/cloudquote.prompt.md")
    self.assertIn("do not require specs, a source bill or an output workbook for quick triage", prompt)

  def test_azure_only_quotes_keep_universal_controls(self) -> None:
    rfp = self.instructions(".github/skills/cloudquote-rfp/SKILL.md")
    self.assertIn("no mode or single-cloud fast path waives qualification", rfp)
    self.assertIn("even for azure-only work", rfp)
    guardrails = self.instructions(".github/skills/cloudquote-pricing-guardrails/SKILL.md")
    self.assertIn("every priced mode and every cloud", guardrails)
    self.assertIn("mandatory qualification and human release approvals", guardrails)
    agent = self.instructions(".github/agents/cloudquote.agent.md")
    self.assertIn("including azure-only quotes", agent)
    self.assertIn("reject compilation", agent)

  def test_scout_routes_preserve_m365_and_sharing_boundaries(self) -> None:
    boq = self.instructions(".github/skills/cloudquote-boq/SKILL.md")
    for required in ("workspace_read_file", "workspace_search_files", "workiq ask", "--file-urls",
                     "m_get_skill", "m_ask_user", "explicit confirmation"):
      self.assertIn(required, boq)
    self.assertIn("never download, unzip, parse xml or use a synced local office copy", boq)
    self.assertIn("do not silently switch to filesystem storage", boq)

  def test_amendments_and_versions_invalidate_approvals(self) -> None:
    rfp = self.instructions(".github/skills/cloudquote-rfp/SKILL.md")
    for required in ("stable requirement id", "authoritative amendment relationship",
                     "old-to-new requirement", "not automatically authoritative",
                     "current structured baseline and pricing context", "assumption version",
                     "approvals stale"):
      self.assertIn(required, rfp)

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