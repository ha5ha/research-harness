#!/usr/bin/env python3
"""Read-only release checks. Uses only Python 3.10+ standard library."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT_FILES = {
    '.gitattributes', '.gitignore', 'AGENTS_SNIPPET.md', 'CHANGELOG.md',
    'IMPLEMENTATION_PLAN.zh-CN.md', 'LICENSE', 'README.md', 'README.zh-CN.md', 'VERSION',
    'MARKETPLACE.md', 'plugin.json',
}
DIRECTORIES = {'skills/research-harness', 'tools', 'tests', 'evaluations', '.github/workflows', '.codex-plugin'}
GENERATED = {'MANIFEST.json', 'SHA256SUMS.txt'}
IGNORED = {'.git', '__pycache__', 'dist', '.pytest_cache'}


class ReleaseError(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory(root: Path, single: bool = False) -> dict[str, bytes]:
    files = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if any(part in IGNORED for part in relative.parts):
            continue
        if path.is_symlink():
            raise ReleaseError(f'symlink is not distributable: {relative.as_posix()}')
        if path.is_dir():
            continue
        name = relative.as_posix()
        if name in GENERATED:
            continue
        if single:
            allowed = name in {'SKILL.md', 'LICENSE'} or relative.parts[0] in {
                'agents', 'scripts', 'references', 'examples', 'tests'}
        else:
            allowed = name in ROOT_FILES or any(name.startswith(d + '/') for d in DIRECTORIES)
        if not allowed or path.suffix in {'.pyc', '.pyo'}:
            raise ReleaseError(f'unexpected release file: {name}')
        files[name] = path.read_bytes()
    return files


def json_object(raw: bytes, name: str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ReleaseError(f'duplicate JSON key in {name}: {key}')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(
                          ReleaseError(f'invalid JSON constant in {name}: {value}')))


def validate(root: Path) -> dict:
    root = root.resolve(strict=True)
    single = (root / 'SKILL.md').is_file()
    skill = root if single else root / 'skills/research-harness'
    files = inventory(root, single)
    required = {'SKILL.md', 'LICENSE', 'scripts/rh.py', 'examples/run_demo.py', 'tests/test_rh.py'}
    for name in required:
        if not (skill / name).is_file():
            raise ReleaseError(f'missing required skill resource: {name}')
    text = (skill / 'SKILL.md').read_text(encoding='utf-8')
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', text, re.S)
    if not match:
        raise ReleaseError('SKILL.md requires YAML frontmatter')
    front = match.group(1)
    if not re.search(r'^name: research-harness\s*$', front, re.M):
        raise ReleaseError('unexpected skill name')
    if not re.search(r'^description: \S.+$', front, re.M):
        raise ReleaseError('skill description is missing')
    version_match = re.search(r'^  version: [\"\']?(\d+\.\d+\.\d+)[\"\']?\s*$', front, re.M)
    if not version_match:
        raise ReleaseError('metadata.version must be a semantic version')
    version = version_match.group(1)
    cli = ast.parse((skill / 'scripts/rh.py').read_text(encoding='utf-8'))
    cli_versions = [n.value.value for n in cli.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in n.targets)
                    and isinstance(n.value, ast.Constant)]
    if cli_versions != [version]:
        raise ReleaseError('CLI and skill versions disagree')
    if not single:
        for name in ROOT_FILES | {'tools/build_release.py', 'tools/validate_release.py',
                                  'tests/test_distribution.py', 'evaluations/REPORT.zh-CN.md',
                                  '.codex-plugin/plugin.json'}:
            if name not in files:
                raise ReleaseError(f'missing release resource: {name}')
        if files['VERSION'].decode().strip() != version:
            raise ReleaseError('VERSION and skill metadata disagree')
        for name in ['plugin.json', '.codex-plugin/plugin.json']:
            plugin = json_object(files[name], name)
            if plugin.get('name') != 'research-harness' or plugin.get('version') != version:
                raise ReleaseError(f'plugin name/version disagrees with skill: {name}')
        if json_object(files['.codex-plugin/plugin.json'], '.codex-plugin/plugin.json').get('skills') != './skills/':
            raise ReleaseError('Codex adapter must point to the bundled skills directory')
    for name, raw in files.items():
        if name.endswith('.py'):
            ast.parse(raw.decode('utf-8-sig'), filename=name)
        elif name.endswith('.json'):
            json_object(raw, name)
        elif name.endswith('.md'):
            # Validate local Markdown resource links, never fetch external URLs.
            for target in re.findall(r'\]\(([^)]+)\)', raw.decode('utf-8')):
                target = target.strip().strip('<>')
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                link = unquote(parsed.path)
                if PurePosixPath(link).is_absolute() or '\\' in link:
                    raise ReleaseError(f'nonportable resource link in {name}: {target}')
                dest = (root / name).parent.joinpath(link).resolve()
                if not dest.is_relative_to(root) or not dest.exists():
                    raise ReleaseError(f'missing/outside resource linked from {name}: {target}')
    manifest_path = root / 'MANIFEST.json'
    sums_path = root / 'SHA256SUMS.txt'
    if manifest_path.exists() != sums_path.exists():
        raise ReleaseError('manifest and checksums must occur together')
    if manifest_path.exists():
        manifest = json_object(manifest_path.read_bytes(), 'MANIFEST.json')
        expected = {n: {'sha256': digest(raw), 'bytes': len(raw)} for n, raw in files.items()}
        if manifest.get('version') != version or manifest.get('files') != expected:
            raise ReleaseError('manifest does not match release content')
        actual_sums = ''.join(f'{digest(raw)}  {name}\n' for name, raw in sorted(
            {**files, 'MANIFEST.json': manifest_path.read_bytes()}.items()))
        if sums_path.read_text(encoding='utf-8') != actual_sums:
            raise ReleaseError('checksums do not match release content')
    return {'ok': True, 'version': version, 'layout': 'skill' if single else 'full',
            'file_count': len(files), 'manifest_checked': manifest_path.exists(),
            'scope': 'Static resources, syntax and optional content integrity; no host or scientific certification'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', default='.')
    args = parser.parse_args()
    try:
        result = validate(Path(args.root))
    except (ReleaseError, OSError, ValueError, SyntaxError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
