"""Behavioral integrity checks; all fixtures use isolated temporary projects."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "research_harness.py"
SPEC = importlib.util.spec_from_file_location("research_harness", SCRIPT)
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="research-harness-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def put(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data) if isinstance(data, (list, dict)) else data, encoding="utf-8")
        return path

    def initialized(self):
        harness.initialize(self.root)
        return json.loads((self.root / "research/CURRENT_STATE.json").read_text(encoding="utf-8"))

    def registered_task(self, status="frozen"):
        state = self.initialized()
        self.put("research/questions/Q1/contract.json", {"purpose": "test a bounded question"})
        digest = harness.digest_file(self.root / "research/questions/Q1/contract.json")[0]
        task = {"id": "T1", "question_id": "Q1", "status": status,
                "contract_path": "research/questions/Q1/contract.json", "contract_sha256": digest,
                "authorization": {"status": "granted", "contract_sha256": digest, "source": "Owner approved exact fixture contract"}}
        state.update(active_question_id="Q1", active_task_id="T1", task_registry=[task])
        state["next_action"] = {"id": "LAUNCH_T1", "description": "Launch the frozen test", "starts_experiment": True}
        self.put("research/CURRENT_STATE.json", state)
        return state, task

    def validate(self):
        return harness.validate_project(self.root)

    def test_init_is_valid_and_never_overwrites(self):
        receipt = harness.initialize(self.root)
        self.assertEqual([
            "research/CURRENT_STATE.json", "research/EVIDENCE_INDEX.json",
            "research/HARNESS_PROFILE.json", "research/PROJECT_SCOPE.md", "research/facts.json",
        ], receipt["created"])
        self.assertEqual(5, len(receipt["created"]))
        before = (self.root / "research/CURRENT_STATE.json").read_bytes()
        self.assertTrue(self.validate()["ok"])
        with self.assertRaises(harness.HarnessError):
            harness.initialize(self.root)
        self.assertEqual(before, (self.root / "research/CURRENT_STATE.json").read_bytes())
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_existing_empty_or_yaml_research_requires_adapter(self):
        (self.root / "research").mkdir()
        with self.assertRaises(harness.HarnessError):
            harness.initialize(self.root)
        self.put("research/CURRENT_STATE.yaml", "status: running\n")
        with self.assertRaisesRegex(harness.HarnessError, "adapter required"):
            self.validate()

    def test_manifest_detects_tamper_and_missing_file(self):
        path = self.put("results/predictions.csv", "id,prediction\na,3\n")
        harness.create_manifest(self.root, "manifest.json", ["results/predictions.csv"])
        self.assertTrue(harness.verify_manifest(self.root, "manifest.json")["ok"])
        path.write_text("id,prediction\na,4\n", encoding="utf-8")
        self.assertFalse(harness.verify_manifest(self.root, "manifest.json")["ok"])
        path.unlink()
        self.assertFalse(harness.verify_manifest(self.root, "manifest.json")["ok"])

    def test_manifest_never_overwrites(self):
        self.put("data.csv", "test")
        self.put("manifest.json", "original")
        with self.assertRaises(harness.HarnessError):
            harness.create_manifest(self.root, "manifest.json", ["data.csv"])
        self.assertEqual("original", (self.root / "manifest.json").read_text())

    def test_rejects_traversal_absolute_directory_and_sensitive_paths(self):
        self.put("model.pth", "checkpoint")
        self.put(".env", "fake-secret")
        for name in ("../outside.csv", str(self.root / "model.pth"), "research/../model.pth", "model.pth", ".env", "."):
            with self.subTest(path=name), self.assertRaises((harness.HarnessError, OSError)):
                harness.create_manifest(self.root, "manifest.json", [name])
        self.assertFalse((self.root / "manifest.json").exists())

    def test_symlink_escape_when_supported(self):
        with tempfile.TemporaryDirectory(prefix="research-harness-outside-") as outside:
            target = Path(outside) / "data.csv"
            target.write_text("outside")
            try:
                (self.root / "link.csv").symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink permission unavailable")
            with self.assertRaises(harness.HarnessError):
                harness.create_manifest(self.root, "manifest.json", ["link.csv"])

    def test_duplicate_manifest_entry_rejected_on_create_and_verify(self):
        self.put("data.csv", "data")
        with self.assertRaises(harness.HarnessError):
            harness.create_manifest(self.root, "manifest.json", ["data.csv", "./data.csv"])
        digest, size = harness.digest_file(self.root / "data.csv")
        entry = {"path": "data.csv", "sha256": digest, "bytes": size}
        self.put("manifest.json", {"schema_version": 1, "files": [entry, entry]})
        self.assertFalse(harness.verify_manifest(self.root, "manifest.json")["ok"])

    def test_verify_rejects_forged_traversal(self):
        self.put("manifest.json", {"schema_version": 1, "files": [{"path": "../data.csv", "sha256": "a" * 64, "bytes": 1}]})
        self.assertFalse(harness.verify_manifest(self.root, "manifest.json")["ok"])

    def test_authorized_frozen_contract_valid(self):
        self.registered_task()
        self.assertTrue(self.validate()["ok"])

    def test_launch_without_authorization_rejected(self):
        state, task = self.registered_task()
        task["authorization"]["status"] = "not_granted"
        self.put("research/CURRENT_STATE.json", state)
        self.assertFalse(self.validate()["ok"])

    def test_contract_change_or_stale_authorization_rejected(self):
        state, task = self.registered_task()
        self.put(task["contract_path"], {"purpose": "changed"})
        self.assertFalse(self.validate()["ok"])
        task["contract_sha256"] = harness.digest_file(self.root / task["contract_path"])[0]
        self.put("research/CURRENT_STATE.json", state)
        self.assertFalse(self.validate()["ok"])

    def test_completed_task_cannot_be_active(self):
        state, task = self.registered_task("completed")
        state["next_action"]["starts_experiment"] = False
        self.put("research/CURRENT_STATE.json", state)
        self.assertFalse(self.validate()["ok"])

    def test_completed_task_needs_archived_evidence(self):
        state, task = self.registered_task("completed")
        state["active_task_id"] = None
        state["next_action"]["starts_experiment"] = False
        task.update(summary_path="summary.md", audit_path="audit.json", evidence_ids=["E1"])
        self.put("summary.md", "Bounded result and limitations")
        self.put("audit.json", {"status": "accepted"})
        self.put("research/CURRENT_STATE.json", state)
        self.assertFalse(self.validate()["ok"])
        artifact = self.put("results/predictions.csv", "id,prediction\na,3\n")
        digest, size = harness.digest_file(artifact)
        self.put("research/EVIDENCE_INDEX.json", {"schema_version": 1, "evidence": [{"id": "E1", "path": "results/predictions.csv", "sha256": digest, "bytes": size}]})
        self.assertTrue(self.validate()["ok"])
        artifact.write_text("changed")
        self.assertFalse(self.validate()["ok"])

    def test_claim_support_needs_scoped_provenance(self):
        self.initialized()
        artifact = self.put("results/data.csv", "observed")
        self.put("research/EVIDENCE_INDEX.json", {"schema_version": 1, "evidence": [{"id": "E1", "path": "results/data.csv", "sha256": harness.digest_file(artifact)[0]}]})
        self.put("research/facts.json", {"schema_version": 1, "facts": [{"id": "F1", "promotion_role": "claim_support", "evidence_ids": ["E1"]}]})
        self.assertFalse(self.validate()["ok"])

    def test_second_live_task_and_invalid_next_action_rejected(self):
        state, task = self.registered_task()
        second = dict(task, id="T2", status="running")
        state["task_registry"].append(second)
        self.put("research/CURRENT_STATE.json", state)
        self.assertFalse(self.validate()["ok"])
        state["task_registry"].pop()
        state["next_action"] = []
        self.put("research/CURRENT_STATE.json", state)
        self.assertFalse(self.validate()["ok"])

    def test_missing_state_route_fields_are_not_accepted(self):
        state = self.initialized()
        del state["active_task_id"]
        self.put("research/CURRENT_STATE.json", state)
        self.assertFalse(self.validate()["ok"])

    def test_duplicate_json_keys_rejected_at_all_levels(self):
        for payload in ('{"sha256":"a","sha256":"b"}', '{"authorization":{"status":"not_granted","status":"granted"}}'):
            with self.subTest(payload=payload):
                path = self.put("duplicate.json", payload)
                with self.assertRaisesRegex(harness.HarnessError, "duplicate JSON key"):
                    harness.read_json(path)

    def test_nonfinite_json_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            path = self.put("invalid.json", '{"value":' + value + '}')
            with self.subTest(value=value), self.assertRaises(harness.HarnessError):
                harness.read_json(path)

    def test_profile_required_fields_have_types(self):
        self.initialized()
        profile_path = self.root / "research/HARNESS_PROFILE.json"
        original = json.loads(profile_path.read_text(encoding="utf-8"))
        for field in ("monitoring_policy", "commit_policy", "code_roots", "result_roots", "validation_commands"):
            broken = dict(original)
            broken.pop(field)
            self.put("research/HARNESS_PROFILE.json", broken)
            with self.subTest(missing=field):
                self.assertFalse(self.validate()["ok"])
        for field, value in (("monitoring_policy", []), ("commit_policy", False), ("code_roots", "src"), ("result_roots", [False]), ("validation_commands", [{}])):
            self.put("research/HARNESS_PROFILE.json", dict(original, **{field: value}))
            with self.subTest(wrong_type=field):
                self.assertFalse(self.validate()["ok"])

    def test_fact_corrections_and_counterevidence_references(self):
        self.initialized()
        artifact = self.put("results/data.csv", "observed")
        self.put("research/EVIDENCE_INDEX.json", {"schema_version": 1, "evidence": [{"id": "E1", "path": "results/data.csv", "sha256": harness.digest_file(artifact)[0]}]})
        previous = {"id": "F1", "statement": "Original bounded observation", "evidence_ids": ["E1"]}
        revised = {"id": "F2", "statement": "Revised bounded observation", "evidence_ids": ["E1"], "counterevidence_ids": ["E1"], "supersedes_id": "F1"}
        self.put("research/facts.json", {"schema_version": 1, "facts": [revised, previous]})
        self.assertTrue(self.validate()["ok"])
        for field, value in (("counterevidence_ids", ["MISSING"]), ("counterevidence_ids", "E1"), ("supersedes_id", "MISSING"), ("supersedes_id", "F2"), ("statement", "")):
            altered = dict(revised, **{field: value})
            self.put("research/facts.json", {"schema_version": 1, "facts": [previous, altered]})
            with self.subTest(field=field, value=value):
                self.assertFalse(self.validate()["ok"])

    def test_packaged_finding_template_accepts_null_supersedes(self):
        self.initialized()
        artifact = self.put("results/data.csv", "bounded observation")
        self.put("research/EVIDENCE_INDEX.json", {"schema_version": 1, "evidence": [{"id": "E1", "path": "results/data.csv", "sha256": harness.digest_file(artifact)[0]}]})
        template = SCRIPT.parent.parent / "assets/templates/finding.json"
        finding = json.loads(template.read_text(encoding="utf-8"))
        finding.update(id="F1", statement="Observed a difference in the fixed fixture", status="observation", evidence_ids=["E1"])
        self.assertIsNone(finding["supersedes_id"])
        self.put("research/facts.json", {"schema_version": 1, "facts": [finding]})
        self.assertTrue(self.validate()["ok"])

    def test_claim_support_requires_verified_status_and_completed_task(self):
        state, task = self.registered_task()
        artifact = self.put("results/data.csv", "observed")
        self.put("research/EVIDENCE_INDEX.json", {"schema_version": 1, "evidence": [{"id": "E1", "path": "results/data.csv", "sha256": harness.digest_file(artifact)[0]}]})
        fact = {"id": "F1", "statement": "Bounded verified result", "status": "verified_under_scope", "promotion_role": "claim_support", "evidence_ids": ["E1"], "scope": "fixed source and dataset", "statistical_unit": "sample", "code_ref": "commit-hash", "config_ref": task["contract_path"], "source_task_id": "T1"}
        self.put("research/facts.json", {"schema_version": 1, "facts": [fact]})
        self.assertFalse(self.validate()["ok"])
        state["active_task_id"] = None
        state["next_action"]["starts_experiment"] = False
        task.update(status="completed", summary_path="summary.md", audit_path="audit.json", evidence_ids=["E1"])
        self.put("summary.md", "Summary and limits")
        self.put("audit.json", {"status": "accepted"})
        self.put("research/CURRENT_STATE.json", state)
        self.assertTrue(self.validate()["ok"])
        fact["status"] = "observation"
        self.put("research/facts.json", {"schema_version": 1, "facts": [fact]})
        self.assertFalse(self.validate()["ok"])

    def test_cli_reports_nonzero_machine_readable_errors(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = harness.main(["verify", "--project-root", str(self.root), "--manifest", "missing.json"])
        self.assertEqual(1, code)
        self.assertFalse(json.loads(buffer.getvalue())["ok"])


if __name__ == "__main__":
    unittest.main()
