"""Tests for statusline.sh: what it shows, and that a missing jq neither fakes values nor
breaks the limits cache. Every run gets its own HOME and config folder, so the real
~/.claude is never touched."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

STATUSLINE = Path(__file__).resolve().parent / 'statusline.sh'
CACHE_LINE = '30\t1900000000\t80\t1900000000\n'
INPUT = {
    'model': {'display_name': 'Opus 5.5'},
    'effort': {'level': 'high'},
    'workspace': {'current_dir': str(STATUSLINE.parent)},
    'context_window': {'used_percentage': 42},
    'rate_limits': {'five_hour': {'used_percentage': 23, 'resets_at': 1900000000},
                    'seven_day': {'used_percentage': 85, 'resets_at': 1900000000}},
}


def strip_colours(text):
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


class StatuslineTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.config = self.root / 'config'
        self.config.mkdir()
        self.cache = self.config / 'statusline-limits.tsv'
        self.cache.write_text(CACHE_LINE)

    def path_without_jq(self):
        """A PATH with every command of the current PATH except jq."""
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        for folder in os.environ['PATH'].split(os.pathsep):
            if not os.path.isdir(folder):
                continue
            for name in os.listdir(folder):
                target = os.path.join(folder, name)
                if name != 'jq' and not (bin_dir / name).exists() and os.access(target, os.X_OK):
                    (bin_dir / name).symlink_to(target)
        return str(bin_dir)

    def run_statusline(self, path=None):
        env = {'HOME': str(self.root), 'CLAUDE_CONFIG_DIR': str(self.config),
               'PATH': path or os.environ['PATH'], 'COLUMNS': '200'}
        bash = shutil.which('bash')
        return subprocess.run([bash, str(STATUSLINE)], input=json.dumps(INPUT), env=env,
                              capture_output=True, text=True, timeout=30)

    def test_with_jq_it_shows_the_model_and_the_values(self):
        out = strip_colours(self.run_statusline().stdout)
        self.assertIn('Opus 5.5 high', out)
        self.assertIn('ctx 42%', out)
        self.assertIn('5h 23%', out)
        self.assertIn('7d 85%', out)

    def test_without_jq_it_says_so_instead_of_showing_values(self):
        result = self.run_statusline(self.path_without_jq())
        out = strip_colours(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertIn('jq', out)
        self.assertNotIn('0%', out)

    def test_without_jq_the_limits_cache_stays_as_it_was(self):
        self.run_statusline(self.path_without_jq())
        self.assertEqual(self.cache.read_text(), CACHE_LINE)
        self.assertEqual(sorted(p.name for p in self.config.iterdir()), ['statusline-limits.tsv'])


if __name__ == '__main__':
    unittest.main()
