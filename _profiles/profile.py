#!/usr/bin/env python3
"""Find the profile of the current repository and print its values (README.md in this folder).

A profile is a company folder (`<company>/config.json`, `<company>/<skill>.md`) with one
entry per repository below it (`<company>/repos/<repo>/config.json` and `repo.md`).
Run it from inside the repository or one of its worktrees, by its literal path:

  profile.py                   `<company>/<repo> <folder>`, `<company> <folder>`, or "none"
  profile.py get <key>         a value as JSON, the repository's over the company's; "null" when unset
  profile.py doc <skill>       the company's <skill>.md, then the repository's repo.md, one path
                               per line, or "none"; a section in both is reported on stderr
  profile.py secret-files      the secret file patterns, one per line
  profile.py secret-excludes   the same as git pathspec excludes, one line, starting with "--"
  profile.py related [out]     a Markdown list of the repositories the current one names in
                               `related`, with their checkouts beside it (or under `reposRoot`)

An entry matches when one of its `remotes` (`<host>/<project path>`, or a shorter prefix
of it) names any remote of the repository; the longest matching entry wins, and a
repository entry beats its company's own `remotes` at equal length. In a folder without
any git remote, `get`, `doc` and `related` use the only company when exactly one
exists, never one of its repositories; a repository whose remotes match nothing, a local
path among them, has no profile. The secret files never fall back to another profile:
they are the repository entry's `secretFiles`, else the broad set below, plus the
company's; without a matching profile the broad set alone. A review of an unknown
repository leaves out more files, never fewer.
"""
import json
import os
import re
import shlex
import subprocess
import sys

# QUBIT_PROFILES_DIR points the tests at a folder of their own profiles
HERE = os.environ.get('QUBIT_PROFILES_DIR') or os.path.dirname(os.path.abspath(__file__))
TEMPLATE = 'example'
FALLBACK_SECRETS = ['.env', '.env.*', '*.env', '*.env.j2', '.envrc', '.netrc', '.npmrc', '*.pem', '*.key',
                    '*.p12', '*.pfx', 'id_rsa*', 'id_ed25519*', 'credentials.json', 'secrets.*']


def git(*args, cwd=None):
    r = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ''


def remote_names():
    """`<host>/<project path>` of every remote, lower case, without `.git`, and whether the
    repository has any remote at all (a local path or `file://` remote names no host)."""
    names, has_remote = set(), False
    for line in git('remote', '-v').splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        has_remote = True
        url = parts[1]
        if url.startswith('file:'):
            continue
        m = (re.match(r'^[a-z+]+://(?:[^@/]+@)?([^:/]+)(?::\d+)?/(.+)$', url)
             or re.match(r'^(?:[^@]+@)?([^:/]+):(.+)$', url))
        if m:
            path = re.sub(r'\.git$', '', m.group(2).strip('/'))
            names.add('%s/%s' % (m.group(1).lower(), path.lower()))
    return names, has_remote


def matches(entry, name):
    entry = entry.lower().strip('/')
    return name == entry or name.startswith(entry + '/')


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def companies():
    out = {}
    for name in sorted(os.listdir(HERE)):
        path = os.path.join(HERE, name, 'config.json')
        if name != TEMPLATE and os.path.isfile(path):
            out[name] = load(path)
    return out


def repos(company):
    folder = os.path.join(HERE, company, 'repos')
    out = {}
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name, 'config.json')
            if os.path.isfile(path):
                out[name] = load(path)
    return out


def resolve(strict):
    """(company, company config, repo, repo config) of the current folder; None and {} for
    what is not found."""
    found = companies()
    names, has_remote = remote_names()
    best, best_rank = (None, {}, None, {}), None
    for company, cfg in found.items():
        candidates = [(None, {}, cfg)] + [(repo, rcfg, rcfg) for repo, rcfg in repos(company).items()]
        for repo, rcfg, owner in candidates:
            for entry in owner.get('remotes', []):
                if any(matches(entry, n) for n in names):
                    rank = (len(entry.strip('/')), repo is not None)
                    if best_rank is None or rank > best_rank:
                        best, best_rank = (company, cfg, repo, rcfg), rank
    if best_rank is not None:
        return best
    if not strict and not has_remote and len(found) == 1:
        company, cfg = next(iter(found.items()))
        return company, cfg, None, {}
    return None, {}, None, {}


def merged(company_cfg, repo_cfg):
    """The repository's values over the company's; `remotes` belongs to neither answer."""
    out = dict(company_cfg)
    out.update(repo_cfg)
    out.pop('remotes', None)
    return out


def headings(path):
    with open(path, encoding='utf-8') as f:
        return [line[3:].strip() for line in f if line.startswith('## ')]


def docs(skill):
    """The company's <skill>.md, then the repository's repo.md, those that exist."""
    company, _, repo, _ = resolve(strict=False)
    if not company:
        return []
    paths = [os.path.join(HERE, company, skill + '.md')]
    if repo:
        paths.append(os.path.join(HERE, company, 'repos', repo, 'repo.md'))
    return [p for p in paths if os.path.isfile(p)]


def secret_files():
    """The repository entry's secret files, else the broad fallback, plus the company's;
    without a matching profile the fallback alone. Never fewer than the fallback unless a
    repository entry names its own."""
    company, cfg, _, rcfg = resolve(strict=True)
    if not company:
        return FALLBACK_SECRETS
    out = []
    for pattern in (rcfg.get('secretFiles') or FALLBACK_SECRETS) + (cfg.get('secretFiles') or []):
        if pattern not in out:
            out.append(pattern)
    return out


def related():
    """A Markdown list of the repositories the current one names in `related`."""
    company, cfg, _, rcfg = resolve(strict=False)
    entries = repos(company) if company else {}
    root = cfg.get('reposRoot')
    if root:
        root = os.path.expanduser(root)
    else:
        common = git('rev-parse', '--path-format=absolute', '--git-common-dir')
        root = os.path.dirname(os.path.dirname(common)) if common else ''
    lines = ['# Related repositories (read-only, at their checked-out HEAD)']
    for name in rcfg.get('related') or []:
        entry = entries.get(name)
        if entry is None:
            lines.append('- %s: no entry under repos/' % name)
            continue
        folder, role = entry.get('dir') or name, entry.get('role') or 'no role given'
        d = os.path.join(root, folder)
        if root and os.path.isdir(os.path.join(d, '.git')):
            lines.append('- %s: %s (HEAD %s, branch %s)' % (
                d, role, git('rev-parse', '--short', 'HEAD', cwd=d),
                git('rev-parse', '--abbrev-ref', 'HEAD', cwd=d)))
        else:
            lines.append('- %s: %s (not checked out: not searched)' % (folder, role))
    if len(lines) == 1:
        lines.append('- none: the profile lists no related repository')
    return '\n'.join(lines) + '\n'


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ''
    if cmd == '':
        company, _, repo, _ = resolve(strict=False)
        if repo:
            print('%s/%s %s' % (company, repo, os.path.join(HERE, company, 'repos', repo)))
        else:
            print('%s %s' % (company, os.path.join(HERE, company)) if company else 'none')
    elif cmd == 'get' and len(argv) == 3:
        _, cfg, _, rcfg = resolve(strict=False)
        print(json.dumps(merged(cfg, rcfg).get(argv[2])))
    elif cmd == 'doc' and len(argv) == 3:
        paths = docs(argv[2])
        print('\n'.join(paths) if paths else 'none')
        seen = {}
        for path in paths:
            for heading in headings(path):
                if heading in seen:
                    sys.stderr.write('profile.py: section "%s" is set in %s and %s; the later one applies\n'
                                     % (heading, seen[heading], path))
                seen[heading] = path
    elif cmd == 'secret-files':
        print('\n'.join(secret_files()))
    elif cmd == 'secret-excludes':
        print('-- ' + ' '.join(shlex.quote(':(exclude,glob)**/' + s) for s in secret_files()))
    elif cmd == 'related' and len(argv) in (2, 3):
        text = related()
        if len(argv) == 3:
            with open(argv[2], 'w', encoding='utf-8') as f:
                f.write(text)
        else:
            sys.stdout.write(text)
    else:
        sys.stderr.write(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
