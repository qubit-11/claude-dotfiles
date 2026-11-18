#!/usr/bin/env python3
"""Grounding check: every finding's cited file, line and names exist as cited.

Usage: python3 ground_check.py <findings.json> <repository root>

For each finding in findings.json: the path of `file` ("<path>:<line>") exists under the root,
the line is within the file, and every name in backticks in `what` occurs in that file (a dotted
name by its last part; paths and text with spaces are no names). It prints one line per finding,
OK or FAIL with the reasons, and exits 1 when any finding fails. It judges no claim: a failure
flags the finding for its check (SKILL.md §4), never drops it.
"""
import json
import re
import sys
from pathlib import Path

NAME = re.compile(r'^[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)*(\(\))?$')


def names(text):
    out = []
    for tok in re.findall(r'`([^`\n]+)`', text or ''):
        tok = tok.strip()
        if NAME.match(tok):
            out.append(tok.rstrip('()').split('.')[-1])
    return sorted(set(out))


def check(finding, root):
    loc = finding.get('file') or ''
    m = re.match(r'^(.+?):(\d+)', loc)
    if not m:
        return ['no "<path>:<line>" in file: %r' % loc]
    path, line = root / m.group(1), int(m.group(2))
    if not path.is_file():
        return ['file %s does not exist' % m.group(1)]
    text = path.read_text(errors='replace')
    reasons = []
    count = text.count('\n') + (0 if text.endswith('\n') else 1)
    if line < 1 or line > count:
        reasons.append('line %d is outside %s (%d lines)' % (line, m.group(1), count))
    for n in names(finding.get('what')):
        if n not in text:
            reasons.append('name %s not in %s' % (n, m.group(1)))
    return reasons


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[2])
        return 2
    data = json.loads(Path(argv[1]).read_text())
    root = Path(argv[2])
    failed = 0
    for f in data.get('findings', []):
        reasons = check(f, root)
        if reasons:
            failed += 1
            print('FAIL %s: %s' % (f.get('id'), '; '.join(reasons)))
        else:
            print('OK   %s' % f.get('id'))
    print('%d finding(s), %d failed' % (len(data.get('findings', [])), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
