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
        self.add_profile('acme', {'remotes': ['git.acme.example/shop/web'],
                                  'ticketBrowseUrl': 'https://acme.example/browse/'})
        (self.profiles / 'acme' / 'repos' / 'web').mkdir(parents=True)
        (self.profiles / 'acme' / 'repos' / 'web' / 'config.json').write_text(
            json.dumps({'remotes': ['git.acme.example/shop/web'], 'secretFiles': ['.prod.env']}))
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
                self.assertTrue(self.run_profile(repo).startswith('acme/web '))
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


class CompanyAndRepositoryTest(unittest.TestCase):
    """A company folder with repository entries below it (repos/<name>/)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.profiles = self.root / 'profiles'
        self.company = self.profiles / 'acme'
        self.write(self.company / 'config.json', {'remotes': ['git.acme.example'],
                                                  'ticketBrowseUrl': 'https://acme.example/browse/',
                                                  'ticketProjects': ['WEB', 'OPS']})
        (self.company / 'ticket.md').write_text('# acme: ticket\n\n## Tracker\n')
        self.add_repo('web', {'remotes': ['git.acme.example/shop/web'], 'productionBranches': ['stable']})
        (self.company / 'repos' / 'web' / 'repo.md').write_text('# web\n\n## Worktree\n')
        self.add_repo('api', {'remotes': ['git.acme.example/shop/api'], 'productionBranches': ['hotfix/de', 'hotfix/at']})
        self.add_repo('docs', {'role': 'the documentation'})

    def write(self, path, config):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config))

    def add_repo(self, name, config):
        self.write(self.company / 'repos' / name / 'config.json', config)

    def repo(self, name, *urls):
        path = self.root / name
        subprocess.run(['git', 'init', '-q', str(path)], check=True)
        for i, url in enumerate(urls):
            subprocess.run(['git', '-C', str(path), 'remote', 'add', 'r%d' % i, url], check=True)
        return path

    def run_full(self, cwd, *args):
        env = dict(os.environ, QUBIT_PROFILES_DIR=str(self.profiles))
        return subprocess.run([sys.executable, str(PROFILE_PY), *args], cwd=cwd, capture_output=True, text=True,
                              check=True, env=env)

    def run_profile(self, cwd, *args):
        return self.run_full(cwd, *args).stdout.strip()

    def test_a_repository_gets_its_own_values_and_the_company_values(self):
        web = self.repo('web', 'git@git.acme.example:shop/web.git')
        self.assertTrue(self.run_profile(web).startswith('acme/web '))
        self.assertEqual(json.loads(self.run_profile(web, 'get', 'productionBranches')), ['stable'])
        self.assertEqual(json.loads(self.run_profile(web, 'get', 'ticketProjects')), ['WEB', 'OPS'])
        self.assertEqual(self.run_profile(web, 'get', 'ticketBrowseUrl'), '"https://acme.example/browse/"')

    def test_two_repositories_of_one_company_keep_their_own_values(self):
        api = self.repo('api', 'https://git.acme.example/shop/api.git')
        self.assertEqual(json.loads(self.run_profile(api, 'get', 'productionBranches')), ['hotfix/de', 'hotfix/at'])

    def test_a_company_repository_without_an_entry_gets_company_values_only(self):
        other = self.repo('other', 'https://git.acme.example/other/x.git')
        self.assertTrue(self.run_profile(other).startswith('acme '))
        self.assertEqual(self.run_profile(other, 'get', 'productionBranches'), 'null')
        self.assertEqual(self.run_profile(other, 'get', 'ticketBrowseUrl'), '"https://acme.example/browse/"')
        self.assertEqual(self.run_profile(other, 'get', 'remotes'), 'null')

    def test_doc_prints_the_company_document_then_repo_md(self):
        web = self.repo('web', 'git@git.acme.example:shop/web.git')
        lines = self.run_profile(web, 'doc', 'ticket').splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].endswith('acme/ticket.md'))
        self.assertTrue(lines[1].endswith('acme/repos/web/repo.md'))
        self.assertTrue(self.run_profile(web, 'doc', 'merge-request').endswith('acme/repos/web/repo.md'))
        other = self.repo('other', 'https://git.acme.example/other/x.git')
        self.assertEqual(self.run_profile(other, 'doc', 'merge-request'), 'none')

    def test_a_section_on_both_levels_is_reported(self):
        web = self.repo('web', 'git@git.acme.example:shop/web.git')
        quiet = self.run_full(web, 'doc', 'ticket')
        self.assertEqual(quiet.stderr, '')
        (self.company / 'ticket.md').write_text('# acme: ticket\n\n## Tracker\n\n## Worktree\n')
        loud = self.run_full(web, 'doc', 'ticket')
        self.assertEqual(loud.stdout, quiet.stdout)
        self.assertIn('"Worktree"', loud.stderr)
        self.assertIn('acme/ticket.md', loud.stderr)
        self.assertIn('acme/repos/web/repo.md', loud.stderr)

    def test_the_longest_matching_remote_wins(self):
        self.add_repo('shop', {'remotes': ['git.acme.example/shop'], 'productionBranches': ['main']})
        web = self.repo('web', 'git@git.acme.example:shop/web.git')
        self.assertEqual(json.loads(self.run_profile(web, 'get', 'productionBranches')), ['stable'])
        cart = self.repo('cart', 'git@git.acme.example:shop/cart.git')
        self.assertEqual(json.loads(self.run_profile(cart, 'get', 'productionBranches')), ['main'])

    def test_the_longest_match_wins_across_companies(self):
        self.write(self.profiles / 'beta' / 'config.json', {'remotes': ['git.acme.example/shop'],
                                                            'ticketBrowseUrl': 'https://beta.example/'})
        cart = self.repo('cart', 'git@git.acme.example:shop/cart.git')
        self.assertTrue(self.run_profile(cart).startswith('beta '))
        web = self.repo('web', 'git@git.acme.example:shop/web.git')
        self.assertTrue(self.run_profile(web).startswith('acme/web '))
        other = self.repo('other', 'https://git.acme.example/other/x.git')
        self.assertTrue(self.run_profile(other).startswith('acme '))

    def test_at_equal_length_the_repository_entry_beats_a_company(self):
        self.write(self.profiles / 'beta' / 'config.json', {'remotes': ['git.acme.example/shop/web']})
        web = self.repo('web', 'git@git.acme.example:shop/web.git')
        self.assertTrue(self.run_profile(web).startswith('acme/web '))

    def test_an_entry_without_remotes_is_never_the_current_repository(self):
        docs = self.repo('docs', 'https://git.acme.example/docs.git')
        self.assertTrue(self.run_profile(docs).startswith('acme '))
        self.assertEqual(self.run_profile(docs, 'get', 'role'), 'null')

    def test_a_worktree_gets_the_profile_of_its_repository(self):
        web = self.repo('web', 'git@git.acme.example:shop/web.git')
        subprocess.run(['git', '-C', str(web), '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q',
                        '--allow-empty', '-m', 'x'], check=True)
        wt = self.root / 'web-wt'
        subprocess.run(['git', '-C', str(web), 'worktree', 'add', '-q', '--detach', str(wt)], check=True)
        self.assertEqual(json.loads(self.run_profile(wt, 'get', 'productionBranches')), ['stable'])

    def test_a_local_path_remote_gets_no_profile(self):
        for url in ['/tmp/x/origin.git', 'file:///tmp/x/origin.git', '../origin']:
            with self.subTest(url=url):
                repo = self.repo('l-%d' % abs(hash(url)), url)
                self.assertEqual(self.run_profile(repo), 'none')
                self.assertEqual(self.run_profile(repo, 'get', 'ticketBrowseUrl'), 'null')

    def test_without_a_remote_the_only_company_is_used_never_a_repository(self):
        plain = self.root / 'plain'
        plain.mkdir()
        self.assertTrue(self.run_profile(plain).startswith('acme '))
        self.assertEqual(self.run_profile(plain, 'get', 'productionBranches'), 'null')
        self.assertTrue(self.run_profile(plain, 'doc', 'ticket').endswith('acme/ticket.md'))

    def test_related_lists_the_related_entries_with_their_role(self):
        self.add_repo('web', {'remotes': ['git.acme.example/shop/web'], 'related': ['api', 'missing']})
        self.add_repo('api', {'remotes': ['git.acme.example/shop/api'], 'dir': 'api-checkout', 'role': 'the API'})
        web = self.repo('web', 'git@git.acme.example:shop/web.git')
        out = self.run_profile(web, 'related')
        self.assertTrue(out.startswith('# Related repositories (read-only, at their checked-out HEAD)'))
        self.assertIn('- api-checkout: the API (not checked out: not searched)', out)
        self.assertIn('- missing: no entry under repos/', out)
        api = self.repo('api-checkout')
        subprocess.run(['git', '-C', str(api), '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q',
                        '--allow-empty', '-m', 'x'], check=True)
        self.assertIn('- %s: the API (HEAD ' % api.resolve(), self.run_profile(web, 'related'))

    def test_related_writes_to_a_file_and_says_when_there_is_none(self):
        api = self.repo('api', 'https://git.acme.example/shop/api.git')
        out_file = self.root / 'related.md'
        self.run_profile(api, 'related', str(out_file))
        self.assertIn('- none: the profile lists no related repository', out_file.read_text())

    def test_related_uses_the_company_repos_root(self):
        self.write(self.company / 'config.json', {'remotes': ['git.acme.example'], 'reposRoot': str(self.root / 'elsewhere')})
        self.add_repo('web', {'remotes': ['git.acme.example/shop/web'], 'related': ['api']})
        self.add_repo('api', {'dir': 'api', 'role': 'the API'})
        web = self.repo('web', 'git@git.acme.example:shop/web.git')
        api = self.repo('elsewhere/api')
        subprocess.run(['git', '-C', str(api), '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q',
                        '--allow-empty', '-m', 'x'], check=True)
        self.assertIn('- %s: the API (HEAD ' % api, self.run_profile(web, 'related'))

    def test_a_repository_s_secret_files_add_the_company_s(self):
        self.write(self.company / 'config.json', {'remotes': ['git.acme.example'], 'secretFiles': ['.company.env']})
        self.add_repo('web', {'remotes': ['git.acme.example/shop/web'], 'secretFiles': ['.prod.env']})
        web = self.repo('web', 'git@git.acme.example:shop/web.git')
        self.assertEqual(self.run_profile(web, 'secret-files').splitlines(), ['.prod.env', '.company.env'])

    def test_an_unknown_repository_of_the_company_gets_the_fallback_and_the_company_s(self):
        self.write(self.company / 'config.json', {'remotes': ['git.acme.example'], 'secretFiles': ['.company.env']})
        for url in ['https://git.acme.example/other/x.git', 'https://git.acme.example/shop/api.git']:
            with self.subTest(url=url):
                repo = self.repo('s-%d' % abs(hash(url)), url)
                secrets = self.run_profile(repo, 'secret-files').splitlines()
                self.assertIn('.env', secrets)
                self.assertIn('.company.env', secrets)

    def test_a_folder_without_a_remote_gets_the_fallback_only(self):
        self.write(self.company / 'config.json', {'remotes': ['git.acme.example'], 'secretFiles': ['.company.env']})
        plain = self.root / 'plain'
        plain.mkdir()
        secrets = self.run_profile(plain, 'secret-files').splitlines()
        self.assertIn('.env', secrets)
        self.assertNotIn('.company.env', secrets)


if __name__ == '__main__':
    unittest.main()
