"""Tests for ground_check.py. Run: python3 test_ground_check.py"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ground_check  # noqa: E402


class GroundCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'src').mkdir()
        (self.root / 'src/a.ts').write_text('export function loadBooking() {\n  return db.find();\n}\n')

    def tearDown(self):
        self.tmp.cleanup()

    def finding(self, file, what=''):
        return {'id': 'D1', 'file': file, 'what': what}

    def test_grounded_finding_passes(self):
        self.assertEqual(ground_check.check(self.finding('src/a.ts:2', '`loadBooking` calls `db.find()`'), self.root), [])

    def test_missing_file_fails(self):
        self.assertIn('does not exist', ground_check.check(self.finding('src/b.ts:1'), self.root)[0])

    def test_line_outside_file_fails(self):
        self.assertIn('outside', ground_check.check(self.finding('src/a.ts:9'), self.root)[0])

    def test_unknown_name_fails(self):
        self.assertIn('saveBooking', ground_check.check(self.finding('src/a.ts:1', '`saveBooking`'), self.root)[0])

    def test_paths_and_phrases_are_no_names(self):
        what = '`src/a.ts` and `a missing await`'
        self.assertEqual(ground_check.check(self.finding('src/a.ts:1', what), self.root), [])

    def test_location_without_line_fails(self):
        self.assertIn('no "<path>:<line>"', ground_check.check(self.finding('src/a.ts'), self.root)[0])

    def test_cli_exit_code(self):
        data = {'findings': [self.finding('src/a.ts:1'), self.finding('src/b.ts:1')]}
        fj = self.root / 'findings.json'
        fj.write_text(json.dumps(data))
        res = subprocess.run([sys.executable, str(HERE / 'ground_check.py'), str(fj), str(self.root)],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        self.assertIn('2 finding(s), 1 failed', res.stdout)


if __name__ == '__main__':
    unittest.main()
