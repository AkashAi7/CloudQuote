import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_pipeline import _artifacts_are_valid, _file_sha256


class PipelineIntegrityTests(unittest.TestCase):
  def test_hash_and_format_validation_detects_corruption(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
      root = Path(directory)
      workbook = root / "quote.xlsx"
      with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("content.txt", "workbook")
      artifacts = {"workbook": str(workbook)}
      manifest = {"artifactHashes": {"workbook": _file_sha256(workbook)}}

      self.assertTrue(_artifacts_are_valid(manifest, artifacts))
      workbook.write_text("corrupt", encoding="utf-8")
      self.assertFalse(_artifacts_are_valid(manifest, artifacts))

  def test_invalid_json_artifact_is_rejected(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
      summary = Path(directory) / "quote.summary.json"
      summary.write_text("{broken", encoding="utf-8")
      artifacts = {"summary": str(summary)}
      manifest = {"artifactHashes": {"summary": _file_sha256(summary)}}

      self.assertFalse(_artifacts_are_valid(manifest, artifacts))


if __name__ == "__main__":
  unittest.main()