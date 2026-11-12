"""Distribution invariants, tested against temporary copies and extracted ZIPs."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_release import build
from validate_release import ReleaseError, validate


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rh-release-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        shutil.copytree(ROOT, self.source, ignore=shutil.ignore_patterns('.git', 'dist', '__pycache__'))

    def test_archives_roundtrip_deterministic_and_refuse_overwrite(self):
        first, second = self.base / 'first', self.base / 'second'
        build(self.source, first)
        build(self.source, second)
        self.assertEqual({p.name: p.read_bytes() for p in first.iterdir()},
                         {p.name: p.read_bytes() for p in second.iterdir()})
        with self.assertRaises(FileExistsError):
            build(self.source, first)
        for index, path in enumerate(sorted(first.glob('*.zip'))):
            extracted = self.base / f'extracted{index}'
            with zipfile.ZipFile(path) as archive:
                self.assertTrue(all(not n.startswith('/') and '..' not in Path(n).parts for n in archive.namelist()))
                archive.extractall(extracted)
            release = next(extracted.iterdir())
            self.assertTrue(validate(release)['manifest_checked'])
            skill = release if (release / 'SKILL.md').exists() else release / 'skills/research-harness'
            document = skill / 'references/analysis.md'
            document.write_bytes(document.read_bytes() + b'\nTamper\n')
            with self.assertRaisesRegex(ReleaseError, 'manifest'):
                validate(release)

    def test_missing_reference_rejected(self):
        (self.source / 'skills/research-harness/references/analysis.md').unlink()
        with self.assertRaisesRegex(ReleaseError, 'resource linked'):
            validate(self.source)

    def test_evaluation_attachments_preserve_raw_evidence(self):
        base=self.source/'evaluations/behavior'
        inputs=json.loads((base/'input_hashes.json').read_text(encoding='utf-8'))
        outputs=json.loads((base/'output_hashes.json').read_text(encoding='utf-8'))
        archives=[('inputs.zip',inputs)] + [(f'outputs-{lane}.zip',{n:d['sha256'] for n,d in records.items()})
                                            for lane,records in outputs.items()]
        for name,hashes in archives:
            with zipfile.ZipFile(base/name) as archive:
                self.assertEqual(set(archive.namelist()),set(hashes))
                for member,expected in hashes.items():
                    self.assertFalse(member.startswith('/') or '..' in Path(member).parts)
                    self.assertEqual(hashlib.sha256(archive.read(member)).hexdigest(),expected)

    def test_version_mismatch_rejected(self):
        (self.source / 'VERSION').write_text('9.9.9\n')
        with self.assertRaisesRegex(ReleaseError, 'versions|VERSION'):
            validate(self.source)

    def test_plugin_adapter_mismatch_rejected(self):
        path=self.source/'.codex-plugin/plugin.json'
        data=json.loads(path.read_text(encoding='utf-8'));data['version']='0.1.1'
        path.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaisesRegex(ReleaseError,'plugin name/version'):
            validate(self.source)

    def test_unexpected_payload_rejected(self):
        (self.source / 'private-notes.txt').write_text('not a release resource')
        with self.assertRaisesRegex(ReleaseError, 'unexpected release file'):
            validate(self.source)


if __name__ == '__main__':
    unittest.main()
