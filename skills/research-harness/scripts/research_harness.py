#!/usr/bin/env python3
"""Portable research ledger helpers. Hash checks do not establish scientific validity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import sys
import tempfile
from typing import Any


SCHEMA_VERSION = 1
TASK_STATUSES = {"draft", "approved", "frozen", "running", "analyzing", "completed", "blocked", "superseded"}
RUN_STATUSES = {"awaiting_local_sync", "failed", "completed", "running", "not_started"}
HASH_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")
FORBIDDEN_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".pt", ".pth", ".ckpt", ".safetensors", ".onnx", ".h5", ".hdf5", ".dcm", ".dicom", ".nii", ".mha", ".mhd", ".nrrd"}
FORBIDDEN_PARTS = {".git", ".ssh", ".aws", "credentials", "secrets", "checkpoints", "raw_medical", "raw_images"}


class HarnessError(ValueError):
    """An actionable input or ledger validation error."""


def project_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise HarnessError("project root must be an existing directory")
    return root


def relative_file(root: Path, value: Any, *, must_exist: bool = True) -> tuple[Path, str]:
    """Resolve an explicit project-relative file without following links outside root."""
    if not isinstance(value, str) or not value.strip():
        raise HarnessError("file path must be a nonempty project-relative string")
    normalized = value.replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.drive or windows.is_absolute() or ".." in posix.parts:
        raise HarnessError(f"path must stay within project root: {value}")
    if not posix.parts or any(":" in part for part in posix.parts):
        raise HarnessError(f"invalid project-relative path: {value}")
    path = (root / Path(*posix.parts)).resolve(strict=must_exist)
    try:
        canonical = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise HarnessError(f"path escapes project root: {value}") from exc
    if must_exist and not path.is_file():
        raise HarnessError(f"expected a regular file: {value}")
    return path, canonical


def guard_evidence_path(path: str) -> None:
    """Reject common sensitive artifacts; this is a heuristic, not content screening."""
    parts = PurePosixPath(path.lower()).parts
    name = parts[-1]
    if any(part in FORBIDDEN_PARTS for part in parts):
        raise HarnessError(f"sensitive artifact path is not allowed: {path}")
    if name == ".env" or name.startswith(".env.") or name in {"id_rsa", "id_ed25519", "credentials.json", "token.json", "tokens.json"}:
        raise HarnessError(f"credential-like artifact is not allowed: {path}")
    if Path(name).suffix in FORBIDDEN_SUFFIXES or name.endswith(".nii.gz"):
        raise HarnessError(f"raw medical, checkpoint or key artifact is not allowed: {path}")


def digest_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def read_json(path: Path) -> dict[str, Any]:
    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for key, value in pairs:
            if key in values:
                raise HarnessError(f"duplicate JSON key in {path.name}: {key}")
            values[key] = value
        return values

    def reject_constant(value: str) -> Any:
        raise HarnessError(f"non-finite JSON constant in {path.name}: {value}")

    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream, object_pairs_hook=unique_keys, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise HarnessError(f"expected a JSON object: {path.name}")
    return value


def write_new_json(path: Path, value: Any) -> None:
    # Exclusive creation preserves existing files, including empty files.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def initialize(root: Path) -> dict[str, Any]:
    research = root / "research"
    if research.exists() or research.is_symlink():
        raise HarnessError("research/ already exists; adapter required for an existing project; nothing was overwritten")
    # Assemble off-path; a no-clobber mkdir reserves the destination before copying.
    # Only this invocation's freshly reserved directory can be rolled back.
    with tempfile.TemporaryDirectory(prefix="research-harness-init-") as temporary:
        stage = Path(temporary)
        state = {
            "schema_version": SCHEMA_VERSION,
            "research_objective": None,
            "active_question_id": None,
            "active_task_id": None,
            "next_action": {
                "id": "DEFINE_RESEARCH_QUESTION",
                "description": "Define a bounded research question and project scope with the owner.",
                "starts_experiment": False,
            },
            "task_registry": [],
        }
        write_new_json(stage / "CURRENT_STATE.json", state)
        write_new_json(stage / "facts.json", {"schema_version": SCHEMA_VERSION, "facts": []})
        write_new_json(stage / "EVIDENCE_INDEX.json", {"schema_version": SCHEMA_VERSION, "evidence": []})
        write_new_json(stage / "HARNESS_PROFILE.json", {
            "schema_version": SCHEMA_VERSION,
            "monitoring_policy": "launch_check_then_wait",
            "commit_policy": "manual",
            "code_roots": ["src", "research_toolkit"],
            "result_roots": ["results"],
            "validation_commands": [],
        })
        (stage / "PROJECT_SCOPE.md").write_text(
            "# Project scope\n\n"
            "Status: unresolved. Define these boundaries with the owner before computation.\n\n"
            "- Research question and intended claim: unresolved.\n"
            "- Data sources, access rights, splits and prior exposure: unresolved.\n"
            "- Statistical unit, pairing, repeats and uncertainty: unresolved.\n"
            "- Allowed labels and parameter-selection boundaries: unresolved.\n"
            "- Input/model/state contracts and comparison groups: unresolved.\n"
            "- Compute budget, environment and authorization: unresolved.\n"
            "- Acceptance criteria and falsifying outcomes: unresolved.\n\n"
            "Initialization grants no compute, remote access, publication or Git permissions.\n",
            encoding="utf-8",
        )
        research.mkdir()
        created: list[Path] = []
        try:
            for source in sorted(stage.iterdir(), key=lambda item: item.name):
                destination = research / source.name
                with source.open("rb") as incoming, destination.open("xb") as outgoing:
                    created.append(destination)
                    shutil.copyfileobj(incoming, outgoing)
        except BaseException:
            for path in reversed(created):
                path.unlink()
            # Refuse to remove any concurrently created, unowned file.
            try:
                research.rmdir()
            except OSError:
                pass
            raise
    return {"ok": True, "operation": "init", "created": [f"research/{p.name}" for p in sorted(research.iterdir(), key=lambda item: item.name)], "compute_authorized": False}


def create_manifest(root: Path, output: str, files: list[str]) -> dict[str, Any]:
    target, target_name = relative_file(root, output, must_exist=False)
    guard_evidence_path(target_name)
    if target.exists() or target.is_symlink():
        raise HarnessError("manifest output already exists; choose a new path")
    if not target.parent.is_dir():
        raise HarnessError("manifest output parent must already exist")
    entries = []
    seen: set[str] = set()
    for value in files:
        path, name = relative_file(root, value)
        guard_evidence_path(name)
        if name.casefold() == target_name.casefold():
            raise HarnessError("manifest cannot include itself")
        key = name.casefold() if os.name == "nt" else name
        if key in seen:
            raise HarnessError(f"duplicate manifest path: {value}")
        seen.add(key)
        digest, size = digest_file(path)
        entries.append({"path": name, "sha256": digest, "bytes": size})
    if not entries:
        raise HarnessError("manifest requires at least one explicit file")
    write_new_json(target, {"schema_version": SCHEMA_VERSION, "files": sorted(entries, key=lambda item: item["path"])})
    return {"ok": True, "operation": "manifest", "path": target_name, "file_count": len(entries), "scientific_acceptance": "not_assessed"}


def check_hash_entry(root: Path, entry: Any, *, size_required: bool) -> tuple[str, list[str]]:
    if not isinstance(entry, dict):
        raise HarnessError("file entry must be an object")
    path, canonical = relative_file(root, entry.get("path"))
    guard_evidence_path(canonical)
    expected = entry.get("sha256")
    if not isinstance(expected, str) or not HASH_PATTERN.fullmatch(expected):
        raise HarnessError(f"invalid SHA-256: {canonical}")
    problems = []
    digest, size = digest_file(path)
    if digest != expected.lower():
        problems.append(f"SHA-256 mismatch: {canonical}")
    if size_required or "bytes" in entry:
        expected_size = entry.get("bytes")
        if not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size < 0:
            problems.append(f"invalid byte count: {canonical}")
        elif size != expected_size:
            problems.append(f"byte count mismatch: {canonical}")
    return canonical, problems


def verify_manifest(root: Path, manifest: str) -> dict[str, Any]:
    path, manifest_name = relative_file(root, manifest)
    payload = read_json(path)
    problems: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        problems.append("unsupported manifest schema_version")
    entries = payload.get("files")
    if not isinstance(entries, list) or not entries:
        raise HarnessError("manifest files must be a nonempty list")
    seen: set[str] = set()
    for entry in entries:
        try:
            name, errors = check_hash_entry(root, entry, size_required=True)
            if name.casefold() == manifest_name.casefold():
                errors.append("manifest includes itself")
            key = name.casefold() if os.name == "nt" else name
            if key in seen:
                errors.append(f"duplicate manifest path: {name}")
            seen.add(key)
            problems.extend(errors)
        except (HarnessError, OSError) as exc:
            problems.append(str(exc))
    return {"ok": not problems, "operation": "verify", "file_count": len(entries), "errors": problems, "scientific_acceptance": "not_assessed"}


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_project(root: Path) -> dict[str, Any]:
    state_path = root / "research" / "CURRENT_STATE.json"
    if (root / "research" / "CURRENT_STATE.yaml").exists() or (root / "research" / "CURRENT_STATE.yml").exists():
        raise HarnessError("adapter required: existing YAML ledger is not the portable JSON schema; use its native validators")
    if not state_path.is_file():
        raise HarnessError("adapter required: research/CURRENT_STATE.json is absent; initialize only an empty project")
    state = read_json(relative_file(root, "research/CURRENT_STATE.json")[0])
    facts_document = read_json(relative_file(root, "research/facts.json")[0])
    evidence_document = read_json(relative_file(root, "research/EVIDENCE_INDEX.json")[0])
    profile = read_json(relative_file(root, "research/HARNESS_PROFILE.json")[0])
    problems: list[str] = []
    for field in ("research_objective", "active_question_id", "active_task_id", "next_action", "task_registry"):
        if field not in state:
            problems.append(f"state is missing required field: {field}")
    for field in ("research_objective", "active_question_id", "active_task_id"):
        if state.get(field) is not None and not nonempty(state[field]):
            problems.append(f"state {field} must be null or a nonempty string")
    for label, document in [("state", state), ("facts", facts_document), ("evidence", evidence_document), ("profile", profile)]:
        if document.get("schema_version") != SCHEMA_VERSION:
            problems.append(f"{label}: unsupported schema_version")
    for field in ("monitoring_policy", "commit_policy"):
        if not nonempty(profile.get(field)):
            problems.append(f"profile {field} must be a nonempty string")
    for field in ("code_roots", "result_roots", "validation_commands"):
        values = profile.get(field)
        if not isinstance(values, list) or any(not nonempty(value) for value in values):
            problems.append(f"profile {field} must be a list of nonempty strings")
    try:
        relative_file(root, "research/PROJECT_SCOPE.md")
    except (HarnessError, OSError) as exc:
        problems.append(f"project scope: {exc}")
    next_action = state.get("next_action")
    if not isinstance(next_action, dict) or not nonempty(next_action.get("id")) or not nonempty(next_action.get("description")) or not isinstance(next_action.get("starts_experiment"), bool):
        problems.append("state requires one next_action object with id, description and boolean starts_experiment")
        next_action = {}
    registry = state.get("task_registry")
    if not isinstance(registry, list):
        problems.append("task_registry must be a list")
        registry = []
    evidence = evidence_document.get("evidence")
    if not isinstance(evidence, list):
        problems.append("evidence must be a list")
        evidence = []
    evidence_ids: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict) or not nonempty(item.get("id")):
            problems.append("each evidence entry needs an id")
            continue
        evidence_id = item["id"]
        if evidence_id in evidence_ids:
            problems.append(f"duplicate evidence id: {evidence_id}")
        evidence_ids.add(evidence_id)
        try:
            _, errors = check_hash_entry(root, item, size_required=False)
            problems.extend(f"{evidence_id}: {error}" for error in errors)
        except (HarnessError, OSError) as exc:
            problems.append(f"{evidence_id}: {exc}")
    tasks: dict[str, dict[str, Any]] = {}
    active_id = state.get("active_task_id")
    question_id = state.get("active_question_id")
    for task in registry:
        if not isinstance(task, dict) or not nonempty(task.get("id")):
            problems.append("each task needs a nonempty id")
            continue
        task_id = task["id"]
        if task_id in tasks:
            problems.append(f"duplicate task id: {task_id}")
        tasks[task_id] = task
        status = task.get("status")
        if not isinstance(status, str) or status not in TASK_STATUSES:
            problems.append(f"{task_id}: invalid task status")
        if not nonempty(task.get("question_id")):
            problems.append(f"{task_id}: question_id is required")
        if "run_status" in task and (not isinstance(task["run_status"], str) or task["run_status"] not in RUN_STATUSES):
            problems.append(f"{task_id}: invalid run_status")
        if status in {"running", "analyzing"} and task_id != active_id:
            problems.append(f"{task_id}: running/analyzing task is outside the sole active route")
        if task.get("active") is True and task_id != active_id:
            problems.append(f"{task_id}: explicit active marker disagrees with active_task_id")
        contract = task.get("contract_path")
        digest = task.get("contract_sha256")
        if contract is None and digest is None and status == "draft":
            pass
        else:
            try:
                contract_file, _ = relative_file(root, contract)
                if not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest) or digest_file(contract_file)[0] != digest.lower():
                    problems.append(f"{task_id}: missing or mismatched frozen contract SHA-256")
            except (HarnessError, OSError) as exc:
                problems.append(f"{task_id}: contract: {exc}")
        if status == "completed":
            if task_id == active_id:
                problems.append(f"{task_id}: completed task cannot be active")
            for key in ("summary_path", "audit_path"):
                try:
                    relative_file(root, task.get(key))
                except (HarnessError, OSError) as exc:
                    problems.append(f"{task_id}: {key}: {exc}")
            references = task.get("evidence_ids")
            if not isinstance(references, list) or not references:
                problems.append(f"{task_id}: completed task requires evidence_ids")
            elif any(not isinstance(ref, str) or ref not in evidence_ids for ref in references):
                problems.append(f"{task_id}: completed task references missing evidence")
            if task.get("run_status") in {"awaiting_local_sync", "failed", "running"}:
                problems.append(f"{task_id}: completed task has unclosed run_status")
    active = tasks.get(active_id) if isinstance(active_id, str) else None
    if active_id is not None and active is None:
        problems.append("active_task_id does not identify a registered task")
    if active is not None:
        if active.get("status") in {"completed", "superseded"}:
            problems.append("active task is already terminal")
        if not nonempty(question_id) or active.get("question_id") != question_id:
            problems.append("active task question_id disagrees with active_question_id")
    if next_action.get("starts_experiment") is True:
        if active is None or active.get("status") != "frozen":
            problems.append("experiment next_action requires an active frozen task")
        else:
            authorization = active.get("authorization")
            if not isinstance(authorization, dict) or authorization.get("status") != "granted" or not nonempty(authorization.get("source")) or authorization.get("contract_sha256") != active.get("contract_sha256"):
                problems.append("experiment next_action requires current authorization bound to the frozen contract SHA-256 and source")
    facts = facts_document.get("facts")
    if not isinstance(facts, list):
        problems.append("facts must be a list")
        facts = []
    fact_ids: set[str] = set()
    for fact in facts:
        if not isinstance(fact, dict) or not nonempty(fact.get("id")):
            problems.append("each fact needs an id")
            continue
        fact_id = fact["id"]
        if fact_id in fact_ids:
            problems.append(f"duplicate fact id: {fact_id}")
        fact_ids.add(fact_id)
        if not nonempty(fact.get("statement")):
            problems.append(f"{fact_id}: fact statement is required")
        references = fact.get("evidence_ids")
        if not isinstance(references, list) or not references or any(not isinstance(ref, str) or ref not in evidence_ids for ref in references):
            problems.append(f"{fact_id}: facts require existing evidence_ids")
        if "counterevidence_ids" in fact:
            counterevidence = fact["counterevidence_ids"]
            if not isinstance(counterevidence, list) or any(not isinstance(ref, str) or ref not in evidence_ids for ref in counterevidence):
                problems.append(f"{fact_id}: counterevidence_ids must reference existing evidence")
        if fact.get("promotion_role") == "claim_support":
            if fact.get("status") != "verified_under_scope":
                problems.append(f"{fact_id}: claim_support requires status verified_under_scope")
            for field in ("scope", "statistical_unit", "code_ref", "config_ref", "source_task_id"):
                if not nonempty(fact.get(field)) or str(fact[field]).strip().lower() == "unresolved":
                    problems.append(f"{fact_id}: claim_support requires resolved {field}")
            source_id = fact.get("source_task_id")
            if not isinstance(source_id, str) or source_id not in tasks:
                problems.append(f"{fact_id}: source_task_id is not registered")
            elif tasks[source_id].get("status") != "completed":
                problems.append(f"{fact_id}: claim_support source task must be completed")
    for fact in facts:
        if not isinstance(fact, dict) or fact.get("supersedes_id") is None:
            continue
        previous = fact["supersedes_id"]
        if not isinstance(previous, str) or previous not in fact_ids or previous == fact.get("id"):
            problems.append(f"{fact.get('id', 'unknown')}: supersedes_id must reference another existing fact")
    return {"ok": not problems, "operation": "validate", "schema": "portable-json-v1", "errors": problems, "task_count": len(tasks), "evidence_count": len(evidence), "fact_count": len(facts), "scientific_acceptance": "not_assessed", "authorization_authenticity": "not_assessed"}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Local portable research ledger helpers. SHA-256 integrity is not scientific acceptance; no command launches experiments or grants authorization.")
    subparsers = result.add_subparsers(dest="command", required=True)
    for command in ("init", "manifest", "verify", "validate"):
        child = subparsers.add_parser(command)
        child.add_argument("--project-root", required=True, help="Existing project directory; all artifact paths are relative to it")
        if command == "manifest":
            child.add_argument("--output", required=True, help="New project-relative JSON output; never overwritten")
            child.add_argument("--files", nargs="+", required=True, help="Explicit project-relative file whitelist; no directory recursion")
        if command == "verify":
            child.add_argument("--manifest", required=True, help="Project-relative manifest JSON")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = project_root(args.project_root)
        if args.command == "init":
            output = initialize(root)
        elif args.command == "manifest":
            output = create_manifest(root, args.output, args.files)
        elif args.command == "verify":
            output = verify_manifest(root, args.manifest)
        else:
            output = validate_project(root)
    except (HarnessError, OSError, ValueError, TypeError) as exc:
        output = {"ok": False, "operation": args.command, "errors": [str(exc)]}
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
