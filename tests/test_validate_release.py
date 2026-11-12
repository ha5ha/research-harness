"""Release checks exercised against altered copies, without executing payload scripts."""

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_validator", ROOT / "tools/validate_release.py")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class ReleaseValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="research-harness-package-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "release"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "dist"))

    def test_unchanged_package_passes(self):
        report = validator.validate(self.root)
        self.assertTrue(report["ok"], report["errors"])

    def test_missing_linked_reference_is_rejected(self):
        (self.root / "skills/research-harness/references/records.md").unlink()
        self.assertFalse(validator.validate(self.root)["ok"])

    def test_changed_release_bytes_are_rejected(self):
        if not (self.root / "MANIFEST.json").exists():
            self.skipTest("source repository has not been packaged yet")
        with (self.root / "README.md").open("a", encoding="utf-8") as stream:
            stream.write("\nChanged after packaging.\n")
        errors = validator.validate(self.root)["errors"]
        self.assertTrue(any("release payload changed" in error for error in errors), errors)

    def test_source_repository_without_archive_manifests_remains_editable(self):
        for name in ("MANIFEST.json", "SHA256SUMS.txt"):
            path = self.root / name
            if path.exists():
                path.unlink()
        report = validator.validate(self.root)
        self.assertTrue(report["ok"], report["errors"])
        with (self.root / "README.md").open("a", encoding="utf-8") as stream:
            stream.write("\nAn editable source repository can update its documentation.\n")
        report = validator.validate(self.root)
        self.assertTrue(report["ok"], report["errors"])

    def test_plugin_cannot_escape_package(self):
        path = self.root / ".codex-plugin/plugin.json"
        plugin = json.loads(path.read_text(encoding="utf-8"))
        plugin["skills"] = "../outside/"
        path.write_text(json.dumps(plugin), encoding="utf-8")
        self.assertFalse(validator.validate(self.root)["ok"])

    def test_duplicate_json_keys_are_rejected(self):
        path = self.root / "skills/research-harness/assets/templates/finding.json"
        path.write_text('{"id": null, "id": "duplicate"}', encoding="utf-8")
        errors = validator.validate(self.root)["errors"]
        self.assertTrue(any("duplicate JSON key" in error for error in errors), errors)

    def test_wrong_template_type_is_rejected_without_crashing(self):
        path = self.root / "skills/research-harness/assets/templates/experiment-contract.json"
        path.write_text("[]", encoding="utf-8")
        report = validator.validate(self.root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("template lacks required record fields" in error for error in report["errors"]))

    def test_credential_or_cache_artifact_is_rejected(self):
        (self.root / ".env").write_text("synthetic fixture", encoding="utf-8")
        cached = self.root / "__pycache__"
        cached.mkdir()
        (cached / "fixture.pyc").write_bytes(b"synthetic fixture")
        self.assertFalse(validator.validate(self.root)["ok"])

    def test_absolute_local_path_is_rejected(self):
        path = self.root / "README.md"
        with path.open("a", encoding="utf-8") as stream:
            stream.write("\n" + "/" + "home/private-user/research\n")
        errors = validator.validate(self.root)["errors"]
        self.assertTrue(any("absolute local-machine path" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
