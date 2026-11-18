#!/usr/bin/env python3
"""Find the profile of the current repository and print its values (README.md in this folder).

Run it from inside the repository or one of its worktrees, by its literal path:

  profile.py                   the profile's name and folder, or "none"
  profile.py get <key>         a value of config.json as JSON; "null" when unset or without a profile
  profile.py doc <skill>       the path of the profile's <skill>.md, or "none"
  profile.py secret-files      the secret file patterns, one per line
  profile.py secret-excludes   the same as git pathspec excludes, one line, starting with "--"
  profile.py neighbours [out]  a Markdown list of the neighbour repositories checked out locally

A profile matches when one of its `remotes` (`<host>/<project path>`, or a shorter
prefix of it) names any remote of the repository. In a folder without any git remote,
`get`, `doc` and `neighbours` use the only profile when exactly one exists; a
repository whose remotes match no profile has none. The secret files never fall back:
without a matching profile they are the broad set below, so a review of an unknown
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
    """`<host>/<project path>` of every remote, lower case, without `.git`."""
    names = set()
    for line in git('remote', '-v').splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        url = parts[1]
        m = (re.match(r'^[a-z+]+://(?:[^@/]+@)?([^:/]+)(?::\d+)?/(.+)$', url)
             or re.match(r'^(?:[^@]+@)?([^:/]+):(.+)$', url))
        if m:
            path = re.sub(r'\.git$', '', m.group(2).strip('/'))
            names.add('%s/%s' % (m.group(1).lower(), path.lower()))
    return names


def matches(entry, name):
    entry = entry.lower().strip('/')
    return name == entry or name.startswith(entry + '/')


def profiles():
    out = {}
    for name in sorted(os.listdir(HERE)):
        path = os.path.join(HERE, name, 'config.json')
        if name != TEMPLATE and os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                out[name] = json.load(f)
    return out


def resolve(strict):
    found = profiles()
    names = remote_names()
    for name, cfg in found.items():
        if any(matches(e, n) for e in cfg.get('remotes', []) for n in names):
            return name, cfg
    if not strict and not names and len(found) == 1:
        return next(iter(found.items()))
    return None, {}


def secret_files():
    name, cfg = resolve(strict=True)
    files = cfg.get('secretFiles') if name else None
    return files or FALLBACK_SECRETS


def neighbours():
    _, cfg = resolve(strict=False)
    repos = cfg.get('neighbourRepos') or []
    root = cfg.get('reposRoot')
    if root:
        root = os.path.expanduser(root)
    else:
        common = git('rev-parse', '--path-format=absolute', '--git-common-dir')
        root = os.path.dirname(os.path.dirname(common)) if common else ''
    lines = ['# Neighbour repositories (read-only, at their checked-out HEAD)']
    for repo in repos:
        d = os.path.join(root, repo['dir'])
        if root and os.path.isdir(os.path.join(d, '.git')):
            lines.append('- %s: %s (HEAD %s, branch %s)' % (
                d, repo['role'], git('rev-parse', '--short', 'HEAD', cwd=d),
                git('rev-parse', '--abbrev-ref', 'HEAD', cwd=d)))
        else:
            lines.append('- %s: %s (not checked out: not searched)' % (repo['dir'], repo['role']))
    if len(lines) == 1:
        lines.append('- none: the profile lists no neighbour repository')
    return '\n'.join(lines) + '\n'


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ''
    if cmd == '':
        name, _ = resolve(strict=False)
        print('%s %s' % (name, os.path.join(HERE, name)) if name else 'none')
    elif cmd == 'get' and len(argv) == 3:
        _, cfg = resolve(strict=False)
        print(json.dumps(cfg.get(argv[2])))
    elif cmd == 'doc' and len(argv) == 3:
        name, _ = resolve(strict=False)
        path = os.path.join(HERE, name, argv[2] + '.md') if name else ''
        print(path if path and os.path.isfile(path) else 'none')
    elif cmd == 'secret-files':
        print('\n'.join(secret_files()))
    elif cmd == 'secret-excludes':
        print('-- ' + ' '.join(shlex.quote(':(exclude,glob)**/' + s) for s in secret_files()))
    elif cmd == 'neighbours' and len(argv) in (2, 3):
        text = neighbours()
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
