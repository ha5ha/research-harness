#!/usr/bin/env python3
"""Statically validate a Research Harness release without importing its scripts."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys
from urllib.parse import unquote


SKILL_NAME = "research-harness"
ALLOWED_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py"}
ALLOWED_NAMES = {"LICENSE", "VERSION", ".gitignore", ".gitattributes", "SHA256SUMS.txt"}
FORBIDDEN_PARTS = {"__pycache__", ".runtime", ".venv", "node_modules", "checkpoints", "raw_medical", "raw_images", "secrets", "credentials", "source_contracts", "_objects"}
LOCAL_PATH = re.compile(r"(?i)\b[A-Z]:[\\/]|/(?:home|Users|workdir[0-9]*)/")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SEMVER = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")


def read_json(path: Path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("non-finite JSON value: " + value)

    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique, parse_constant=reject_constant)


def relative_path(root: Path, value: str) -> Path:
    normalized = value.replace("\\", "/")
    parts = PurePosixPath(normalized)
    if parts.is_absolute() or PureWindowsPath(value).drive or ".." in parts.parts:
        raise ValueError("path escapes package: " + value)
    target = root.joinpath(*parts.parts).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("resolved path escapes package: " + value)
    return target


def package_files(root: Path):
    for path in sorted(root.rglob("*")):
        parts = path.relative_to(root).parts
        if ".git" in parts:
            continue
        if path.is_symlink():
            yield path
        elif path.is_file():
            yield path


def inspect_files(root: Path, errors: list[str]) -> list[Path]:
    files = list(package_files(root))
    for path in files:
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            errors.append("symlink in package: " + relative)
            continue
        parts = set(path.relative_to(root).parts)
        if parts & FORBIDDEN_PARTS or path.name == ".env" or path.name.startswith(".env."):
            errors.append("sensitive or cached artifact: " + relative)
        if path.suffix not in ALLOWED_SUFFIXES and path.name not in ALLOWED_NAMES:
            errors.append("unexpected package artifact: " + relative)
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            errors.append("unreadable text artifact: " + relative + ": " + str(exc))
            continue
        if LOCAL_PATH.search(content):
            errors.append("absolute local-machine path in " + relative)
        if PRIVATE_KEY.search(content):
            errors.append("private key content in " + relative)
        if path.suffix == ".json":
            try:
                read_json(path)
            except (ValueError, OSError) as exc:
                errors.append("invalid JSON in " + relative + ": " + str(exc))
        if path.suffix == ".py":
            try:
                ast.parse(content, filename=relative)
            except SyntaxError as exc:
                errors.append("invalid Python in " + relative + ": " + str(exc))
        if path.suffix == ".md":
            for match in LINK.finditer(content):
                value = match.group(1).strip().split(" ", 1)[0].strip("<>")
                if not value or value.startswith(("https://", "http://", "mailto:", "#")):
                    continue
                value = unquote(value.split("#", 1)[0])
                target = (path.parent / value).resolve()
                if not target.is_relative_to(root.resolve()) or not target.is_file():
                    errors.append("missing or escaping Markdown reference in " + relative + ": " + value)
    return files


def frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("SKILL.md needs YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("SKILL.md frontmatter has no closing delimiter") from exc
    values = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(" "):
            if line.strip().startswith("version:"):
                values["version"] = line.split(":", 1)[1].strip().strip('"\'')
            continue
        key, separator, value = line.partition(":")
        if not separator or key in values:
            raise ValueError("unsupported or duplicate skill frontmatter field")
        values[key] = value.strip().strip('"\'')
    if values.get("name") != SKILL_NAME or not values.get("description"):
        raise ValueError("skill name or description is invalid")
    if values.get("description") in {"|", ">", "|-", ">-"}:
        raise ValueError("release checker requires a single-line skill description")
    return values


def inspect_skill(skill: Path, version: str, errors: list[str]) -> None:
    required = ["SKILL.md", "LICENSE", "agents/openai.yaml", "scripts/research_harness.py", "tests/test_research_harness.py",
                "references/adoption.md", "references/continuity.md", "references/evidence.md", "references/experiments.md", "references/records.md",
                "assets/templates/analysis.md", "assets/templates/question.md", "assets/templates/experiment-contract.json",
                "assets/templates/attempt.json", "assets/templates/finding.json", "assets/templates/handoff.json"]
    for relative in required:
        if not (skill / relative).is_file() or (skill / relative).is_symlink():
            errors.append("missing skill file: " + relative)
    if not (skill / "SKILL.md").is_file() or (skill / "SKILL.md").is_symlink():
        return
    try:
        values = frontmatter(skill / "SKILL.md")
        if values.get("version") != version:
            errors.append("skill metadata version differs from VERSION")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    metadata = skill / "agents/openai.yaml"
    if metadata.is_file() and not metadata.is_symlink():
        text = metadata.read_text(encoding="utf-8")
        if not all(key + ":" in text for key in ("interface", "display_name", "short_description", "default_prompt")) or "$research-harness" not in text:
            errors.append("Codex UI metadata is incomplete")
        if re.search(r"[!&*][A-Za-z_]", text):
            errors.append("unsupported YAML tags or aliases in Codex UI metadata")
    templates = {
        "experiment-contract.json": {"schema_version", "status", "task_id", "question_id", "implementation", "data", "execution", "acceptance"},
        "attempt.json": {"schema_version", "attempt_id", "task_id", "contract_sha256", "execution_status", "acceptance", "retry_of"},
        "finding.json": {"id", "status", "promotion_role", "statement", "scope", "evidence_ids", "counterevidence_ids"},
        "handoff.json": {"schema_version", "canonical_state_path", "canonical_state_sha256", "next_action", "source_refs"},
    }
    for name, keys in templates.items():
        path = skill / "assets/templates" / name
        if not path.is_file() or path.is_symlink():
            continue
        try:
            record = read_json(path)
            if not isinstance(record, dict) or not keys.issubset(record):
                errors.append("template lacks required record fields: " + name)
            if not isinstance(record, dict):
                continue
            if isinstance(record, dict) and "schema_version" in record and record["schema_version"] != 1:
                errors.append("unknown template schema version: " + name)
            if name == "experiment-contract.json" and record.get("status") != "draft":
                errors.append("experiment template must start as draft")
        except (ValueError, OSError) as exc:
            errors.append("cannot validate template " + name + ": " + str(exc))
    for relative in ("scripts/research_harness.py", "tests/test_research_harness.py"):
        path = skill / relative
        if not path.is_file() or path.is_symlink():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            if relative.startswith("scripts/") and not any(isinstance(node, ast.FunctionDef) and node.name == "main" for node in tree.body):
                errors.append("helper lacks a CLI main entrypoint")
            if relative.startswith("tests/") and not any(isinstance(node, ast.FunctionDef) and node.name.startswith("test_") for node in ast.walk(tree)):
                errors.append("helper behavioral tests are missing")
        except (OSError, SyntaxError):
            pass  # inspect_files reports syntax and text failures.


def inspect_integrity(root: Path, files: list[Path], errors: list[str]) -> None:
    manifest_path = root / "MANIFEST.json"
    checksums = root / "SHA256SUMS.txt"
    if not manifest_path.exists() and not checksums.exists():
        return  # Source repository can be validated before release packaging.
    if not manifest_path.is_file() or not checksums.is_file() or manifest_path.is_symlink() or checksums.is_symlink():
        errors.append("release manifest and checksums must be present together")
        return
    try:
        manifest = read_json(manifest_path)
        entries = manifest["files"]
        if manifest.get("schema_version") != 1 or not isinstance(entries, list):
            raise ValueError("unknown release manifest schema")
        listed = set()
        for item in entries:
            name = item["path"]
            if name in listed:
                raise ValueError("duplicate release manifest path: " + name)
            listed.add(name)
            target = relative_path(root, name)
            if not target.is_file() or target.is_symlink():
                raise ValueError("missing release payload: " + name)
            content = target.read_bytes()
            if hashlib.sha256(content).hexdigest() != item["sha256"] or len(content) != item["size_bytes"]:
                raise ValueError("release payload changed: " + name)
        actual = {path.relative_to(root).as_posix() for path in files} - {"MANIFEST.json", "SHA256SUMS.txt"}
        if actual != listed:
            raise ValueError("release file inventory differs from manifest")
        checksum_entries = {}
        for line in checksums.read_text(encoding="utf-8").splitlines():
            digest, separator, name = line.partition("  ")
            if not separator or not re.fullmatch(r"[a-f0-9]{64}", digest) or name in checksum_entries:
                raise ValueError("invalid or duplicate checksum row")
            checksum_entries[name] = digest
            target = relative_path(root, name)
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError("checksum mismatch: " + name)
        if set(checksum_entries) != listed | {"MANIFEST.json"}:
            raise ValueError("checksum inventory differs from manifest")
    except (ValueError, TypeError, KeyError, OSError) as exc:
        errors.append("release integrity: " + str(exc))


def validate(root: Path) -> dict:
    root = root.resolve()
    errors: list[str] = []
    if not root.is_dir():
        return {"ok": False, "errors": ["release root is not a directory"], "scope": "static package checks only"}
    for name in ("README.md", "README.zh-CN.md", "MARKETPLACE.md", "LICENSE", "VERSION", ".gitignore", ".gitattributes", "plugin.json", ".codex-plugin/plugin.json", ".github/workflows/validate.yml", "tools/validate_release.py", "tests/test_validate_release.py"):
        if not (root / name).is_file():
            errors.append("missing release file: " + name)
    version_path = root / "VERSION"
    version = version_path.read_text(encoding="utf-8").strip() if version_path.is_file() and not version_path.is_symlink() else ""
    if not SEMVER.fullmatch(version):
        errors.append("VERSION must contain a semantic version")
    attributes = root / ".gitattributes"
    if attributes.is_file() and not attributes.is_symlink() and "* text eol=lf" not in attributes.read_text(encoding="utf-8").splitlines():
        errors.append(".gitattributes must preserve LF line endings across platforms")
    ignore = root / ".gitignore"
    if ignore.is_file() and not ignore.is_symlink():
        ignored_lines = ignore.read_text(encoding="utf-8").splitlines()
        if not all(name in ignored_lines for name in ("/MANIFEST.json", "/SHA256SUMS.txt")):
            errors.append("archive integrity files must be ignored in editable source repositories")
    files = inspect_files(root, errors)
    inspect_skill(root / "skills" / SKILL_NAME, version, errors)
    license_path = root / "LICENSE"
    if license_path.is_file() and not license_path.is_symlink():
        license_text = license_path.read_text(encoding="utf-8")
        if "MIT License" not in license_text or "Copyright (c) 2026 Research Harness contributors" not in license_text:
            errors.append("MIT license or copyright is missing")
        skill_license = root / "skills" / SKILL_NAME / "LICENSE"
        if skill_license.is_file() and not skill_license.is_symlink() and skill_license.read_bytes() != license_path.read_bytes():
            errors.append("installed skill license differs from repository license")
    for relative in ("plugin.json", ".codex-plugin/plugin.json"):
        path = root / relative
        if not path.is_file() or path.is_symlink():
            continue
        try:
            plugin = read_json(path)
            if plugin.get("name") != SKILL_NAME or plugin.get("version") != version or not plugin.get("description"):
                errors.append("plugin identity or version differs: " + relative)
            if relative == "plugin.json":
                if plugin.get("license") != "MIT" or plugin.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
                    errors.append("portable plugin schema or license is invalid")
            else:
                if plugin.get("author") != {"name": "Research Harness contributors"} or plugin.get("skills") != "./skills/":
                    errors.append("Codex author or skill path is invalid")
                target = relative_path(root, plugin.get("skills", ""))
                if not (target / SKILL_NAME / "SKILL.md").is_file():
                    errors.append("Codex manifest does not resolve to bundled skill")
            if any(key in plugin for key in ("mcpServers", "homepage", "repository")):
                errors.append("unexpected remote service or unpublished identity in plugin")
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            errors.append("cannot validate " + relative + ": " + str(exc))
    inspect_integrity(root, files, errors)
    return {"ok": not errors, "errors": errors, "file_count": len(files), "version": version, "scope": "static package checks only; no script imports, execution, authorization, or scientific assessment"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args(argv)
    report = validate(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
