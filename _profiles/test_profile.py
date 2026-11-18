"""Tests for profile.py: which profile a folder gets, and that the secret files fail closed."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROFILE_PY = Path(__file__).resolve().parent / 'profile.py'


class ProfileTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.profiles = self.root / 'profiles'
        self.add_profile('acme', {'remotes': ['git.acme.example/shop/web'], 'secretFiles': ['.prod.env'],
                                  'ticketBrowseUrl': 'https://acme.example/browse/',
                                  'neighbourRepos': [{'dir': 'api', 'role': 'the API'}]})
        (self.profiles / 'acme' / 'merge-request.md').write_text('# acme\n')
        (self.profiles / 'example').mkdir()
        (self.profiles / 'example' / 'config.json').write_text(json.dumps({'remotes': ['git.example.com/g/p']}))

    def add_profile(self, name, config):
        (self.profiles / name).mkdir(parents=True)
        (self.profiles / name / 'config.json').write_text(json.dumps(config))

    def repo(self, name, *urls):
        path = self.root / name
        subprocess.run(['git', 'init', '-q', str(path)], check=True)
        for i, url in enumerate(urls):
            subprocess.run(['git', '-C', str(path), 'remote', 'add', 'r%d' % i, url], check=True)
        return path

    def run_profile(self, cwd, *args):
        env = dict(os.environ, QUBIT_PROFILES_DIR=str(self.profiles))
        return subprocess.run([sys.executable, str(PROFILE_PY), *args], cwd=cwd, capture_output=True, text=True,
                              check=True, env=env).stdout.strip()

    def test_a_remote_of_the_listed_project_matches_in_every_url_form(self):
        for url in ['https://git.acme.example/shop/web.git', 'git@git.acme.example:shop/web.git',
                    'ssh://git@git.acme.example:2222/shop/web', 'https://user@git.acme.example/Shop/Web/']:
            with self.subTest(url=url):
                repo = self.repo('r-%d' % abs(hash(url)), 'https://github.com/x/y.git', url)
                self.assertTrue(self.run_profile(repo).startswith('acme '))
                self.assertEqual(self.run_profile(repo, 'secret-files'), '.prod.env')
                self.assertEqual(self.run_profile(repo, 'get', 'ticketBrowseUrl'), '"https://acme.example/browse/"')

    def test_another_project_on_the_same_host_gets_no_profile_and_the_fallback_secrets(self):
        for url in ['https://git.acme.example/shop/web-deploy.git', 'https://git.acme.example/other/web.git',
                    'https://github.com/someone/skills.git']:
            with self.subTest(url=url):
                repo = self.repo('o-%d' % abs(hash(url)), url)
                self.assertEqual(self.run_profile(repo), 'none')
                self.assertEqual(self.run_profile(repo, 'doc', 'merge-request'), 'none')
                self.assertEqual(self.run_profile(repo, 'get', 'ticketBrowseUrl'), 'null')
                secrets = self.run_profile(repo, 'secret-files').splitlines()
                self.assertIn('.env', secrets)
                self.assertNotIn('.prod.env', secrets)

    def test_a_group_prefix_matches_every_project_of_the_group(self):
        self.add_profile('beta', {'remotes': ['git.beta.example/team']})
        self.assertTrue(self.run_profile(self.repo('g1', 'https://git.beta.example/team/a.git')).startswith('beta '))
        self.assertEqual(self.run_profile(self.repo('g2', 'https://git.beta.example/teamwork/a.git')), 'none')

    def test_without_a_remote_the_only_profile_is_used_but_never_for_secrets(self):
        plain = self.root / 'plain'
        plain.mkdir()
        self.assertTrue(self.run_profile(plain).startswith('acme '))
        self.assertTrue(self.run_profile(plain, 'doc', 'merge-request').endswith('acme/merge-request.md'))
        self.assertIn('.env', self.run_profile(plain, 'secret-files').splitlines())

    def test_without_a_remote_and_several_profiles_none_is_used(self):
        self.add_profile('beta', {'remotes': ['git.beta.example/team']})
        plain = self.root / 'plain'
        plain.mkdir()
        self.assertEqual(self.run_profile(plain), 'none')

    def test_the_template_is_never_a_profile(self):
        repo = self.repo('t', 'https://git.example.com/g/p.git')
        self.assertEqual(self.run_profile(repo), 'none')

    def test_secret_excludes_are_pathspecs_of_the_secret_files(self):
        repo = self.repo('x', 'https://git.acme.example/shop/web.git')
        self.assertEqual(self.run_profile(repo, 'secret-excludes'), "-- ':(exclude,glob)**/.prod.env'")

    def test_neighbours_lists_checked_out_and_missing_repositories(self):
        repo = self.repo('web', 'https://git.acme.example/shop/web.git')
        out = self.run_profile(repo, 'neighbours')
        self.assertIn('- api: the API (not checked out: not searched)', out)
        self.repo('api')
        subprocess.run(['git', '-C', str(self.root / 'api'), '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit',
                        '-q', '--allow-empty', '-m', 'x'], check=True)
        self.assertIn('%s: the API (HEAD ' % (self.root / 'api').resolve(), self.run_profile(repo, 'neighbours'))


if __name__ == '__main__':
    unittest.main()
