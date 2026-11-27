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

    def run_statusline(self, path=None, workspace=None, profiles=None):
        env = {'HOME': str(self.root), 'CLAUDE_CONFIG_DIR': str(self.config),
               'PATH': path or os.environ['PATH'], 'COLUMNS': '200',
               'QUBIT_PROFILES_DIR': str(profiles or self.root / 'no-profiles')}
        data = dict(INPUT, workspace={'current_dir': str(workspace or STATUSLINE.parent)})
        bash = shutil.which('bash')
        return subprocess.run([bash, str(STATUSLINE)], input=json.dumps(data), env=env,
                              capture_output=True, text=True, timeout=30)

    def ticket_repo(self, folder, branch):
        """A repository of company acme (tracker keys WEB and OPS) in `folder`, on `branch`."""
        profiles = self.root / 'profiles'
        (profiles / 'acme').mkdir(parents=True, exist_ok=True)
        (profiles / 'acme' / 'config.json').write_text(json.dumps(
            {'remotes': ['git.acme.example'], 'ticketBrowseUrl': 'https://tracker.example/issue/',
             'ticketProjects': ['WEB', 'OPS']}))
        repo = self.root / folder
        subprocess.run(['git', 'init', '-q', '-b', branch, str(repo)], check=True)
        subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin', 'https://git.acme.example/shop/web.git'],
                       check=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q',
                        '--allow-empty', '-m', 'x'], check=True)
        return repo, profiles

    def test_ticket_keys_of_the_profile_link_to_its_tracker(self):
        repo, profiles = self.ticket_repo('DEV-web-12-login', 'AbCd/WEB-12-login')
        out = self.run_statusline(workspace=repo, profiles=profiles).stdout
        link = '\x1b]8;;https://tracker.example/issue/WEB-12\x1b\\'
        self.assertIn(link + 'web-12', out)
        self.assertIn(link + 'WEB-12', out)

    def test_a_key_inside_a_longer_key_is_no_link(self):
        repo, profiles = self.ticket_repo('DEV-xweb-3-other', 'XWEB-3-other')
        out = self.run_statusline(workspace=repo, profiles=profiles).stdout
        self.assertNotIn('tracker.example', out)

    def test_without_a_profile_names_stay_plain(self):
        repo, _ = self.ticket_repo('DEV-web-12-login', 'WEB-12-login')
        out = self.run_statusline(workspace=repo).stdout
        self.assertNotIn('tracker.example', out)

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
