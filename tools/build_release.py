#!/usr/bin/env python3
"""Build deterministic full and single-skill ZIPs; never overwrite outputs."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import sys
import zipfile

from validate_release import ReleaseError, digest, inventory, validate


def archive(files: dict[str, bytes], prefix: str, version: str, layout: str) -> bytes:
    files = dict(files)
    manifest = {'schema_version': 1, 'name': 'research-harness', 'version': version,
                'layout': layout, 'files': {name: {'sha256': digest(raw), 'bytes': len(raw)}
                                          for name, raw in sorted(files.items())}}
    files['MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    files['SHA256SUMS.txt'] = ''.join(f'{digest(raw)}  {name}\n'
                                    for name, raw in sorted(files.items())).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(f'{prefix}/{name}', date_time=(2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, raw, compresslevel=9)
    return output.getvalue()


def build(root: Path, destination: Path) -> dict:
    result = validate(root)
    if result['layout'] != 'full':
        raise ReleaseError('build from the full source repository')
    version = result['version']
    payloads = {
        f'research-harness-v{version}-full.zip': archive(inventory(root), f'research-harness-v{version}', version, 'full'),
        f'research-harness-v{version}-skill.zip': archive(inventory(root / 'skills/research-harness', True),
                                                      'research-harness', version, 'skill'),
    }
    payloads['SHA256SUMS.txt'] = ''.join(f'{digest(raw)}  {name}\n' for name, raw in sorted(payloads.items())).encode()
    # Reserve a fresh directory atomically; a partial build is retained on error.
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads.items():
        with (destination / name).open('xb') as target:
            target.write(raw)
    return {'ok': True, 'version': version, 'artifacts': [
        {'name': name, 'bytes': len(raw), 'sha256': digest(raw)} for name, raw in payloads.items()]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output-dir', type=Path, required=True, help='New directory; existing directories are refused')
    args = parser.parse_args()
    try:
        result = build(args.root.resolve(strict=True), args.output_dir.resolve())
    except (ReleaseError, OSError, ValueError, SyntaxError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
