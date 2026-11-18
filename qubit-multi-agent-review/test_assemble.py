#!/usr/bin/env python3
"""Tests for assemble.py. Run: python3 test_assemble.py

Each test builds a small valid report directory, changes one thing and runs assemble.py on it.
"""
import contextlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
NODE = shutil.which('node')
sys.path.insert(0, str(HERE))
EXPLAIN = HERE.parent / 'qubit-explanation-page'
sys.path.insert(0, str(EXPLAIN))
import assemble  # noqa: E402
import render_check  # noqa: E402
import save_output  # noqa: E402

CARD_FIELDS = ['what', 'why', 'fix', 'verify']


def at_end(page):
    """Where a probe goes: before </body>, or at the very end, since the template has no body tags."""
    i = page.rfind('</body>')
    return i if i >= 0 else len(page)


def twin(en, de, tag='div'):
    return '<%s data-lang="en">%s</%s><%s data-lang="de">%s</%s>' % (tag, en, tag, tag, de, tag)


def para(en='…', de='…'):
    """A visible paragraph without details: an EN/DE pair of <p>."""
    return '<p data-lang="en">%s</p><p data-lang="de">%s</p>\n' % (en, de)


def disclosure(en='…', de='…', more_en='… <code>src/a.ts:11</code>', more_de='… <code>src/a.ts:11</code>'):
    """A paragraph with details: the paragraph is the summary, the details one EN/DE pair in the .more-body."""
    return ('<details class="pt"><summary><span data-lang="en" class="ptxt">%s</span><span data-lang="de" class="ptxt">%s</span>'
            '<span class="chev" aria-hidden="true"></span></summary><div class="more-body">%s</div></details>\n'
            % (en, de, para(more_en, more_de).strip()))


def text_body(en='…', de='…'):
    """A subsection's default text: a paragraph, and one with details that cite src/a.ts:11."""
    return para(en, de) + disclosure(en, de)


def subsec(sid, en='Title', de='Titel', body=None):
    return '<div id="%s" class="subsec">\n<h3>%s</h3>\n%s</div>\n' % (sid, twin(en, de, 'span'), body or text_body())


def verdict(word_en='not mergeable', word_de='nicht mergebar', ids=('F1',)):
    named = ', '.join(ids)
    return para('Text %s.' % named, 'Text %s.' % named)


def finding(fid='F1', sev='blocker', **kw):
    f = {'id': fid, 'sev': sev, 'category': 'functionality', 'package': 'server', 'file': 'src/a.ts:11',
         'what': 'What happens.', 'why': 'Why it matters.', 'fix': 'The fix.', 'verify': 'Checked inline.',
         'sources': ['core'], 'check': 'inline' if sev == 'nit' else 'investigator'}
    if sev == 'nit':
        f['category'] = 'style'
    if sev in ('optional', 'fyi'):
        f['followUp'] = {'title': 'Follow-up title', 'key': None}
    f.update(kw)
    return f


def card(f, gitlab=None):
    """The findings writer's card for a finding: every field a visible text; what and verify with their details, as a
    Blocker needs them, why and fix without, so both render paths run."""
    fields = {k: {'text': ['Card %s.' % k, 'Karte %s.' % k], 'more': None} for k in CARD_FIELDS}
    fields['what']['more'] = ['The path runs through `src/a.ts:11`.', 'Der Weg führt durch `src/a.ts:11`.']
    fields['verify']['more'] = ['Read `src/a.ts:11` again.', '`src/a.ts:11` erneut gelesen.']
    if isinstance(f.get('principle'), str) and f['principle'].strip():
        fields['what']['text'] = ['Card what, against %s.' % f['principle'], 'Karte what, gegen %s.' % f['principle']]
    c = {'id': f['id'], 'sev': f['sev'], 'category': f['category'], 'package': f['package'], 'file': f['file'],
         't': ['Title', 'Titel'], 'fields': fields}
    if 'followUp' in f:
        c['followUp'] = dict(f['followUp'])
    if gitlab is not None:
        c['gitlab'] = gitlab
    return c


def comment(path='src/a.ts', startLine=11, anchor='line', en='`x` resets the counter. The loop never ends.\n\nSuggestion: increment `x`.',
            de='`x` setzt den Zähler zurück. Die Schleife endet nie.\n\nVorschlag: `x` erhöhen.', **kw):
    c = {'path': path, 'startLine': startLine, 'anchor': anchor, 'text': [en, de]}
    c.update(kw)
    return {k: v for k, v in c.items() if v is not None}


def cold_read(comments, rounds=1, ref=0, calque=0, mismatch=0, fixed=None, left=()):
    items = {'ref': ref, 'calque': calque, 'mismatch': mismatch}
    return {'comments': comments, 'rounds': rounds, 'items': items,
            'fixed': sum(items.values()) - len(left) if fixed is None else fixed, 'left': list(left)}


def cold_read_paragraph(cr, en=True, de=True):
    """The method section's sentence on a cold read: its comments, its fixed items and the findings left."""
    left = ' '.join(str(w).split(' ', 1)[0] for w in cr.get('left') or [])
    return twin('<p>Cold read: %s comments, %s fixed. Left: %s.</p>' % (cr.get('comments'), cr.get('fixed'), left)
                if en else '<p>Cold read.</p>',
                '<p>Kalt-Lesen: %s Kommentare, %s behoben. Offen: %s.</p>' % (cr.get('comments'), cr.get('fixed'), left)
                if de else '<p>Kalt-Lesen.</p>')


def manual_step(mid, do='Open the admin login and sign in.', expect='The dashboard opens.'):
    return {'id': mid, 'do': do, 'expect': expect, 'flow': 'login'}


def manual_json(spec_manual):
    """The translator's manual.json for a findings.json manual block."""
    de = lambda en: 'DE ' + en
    return {'setup': [spec_manual['setup'], de(spec_manual['setup'])],
            'steps': [{'id': s['id'], 'do': [s['do'], de(s['do'])], 'expect': [s['expect'], de(s['expect'])]}
                      for s in spec_manual['steps']]}


def pushed_items(pub, tags):
    """The items a run of <script src> tags pushes, in load order (assemble.pushed_files)."""
    items = []
    for name in re.findall(r'<script src="([^"]+)"></script>', tags):
        js = (pub / name).read_text()
        items += json.loads('[' + js[js.index('.push(\n') + len('.push(\n'):js.index('\n);\n')] + ']')
    return items


def restore_split(pub):
    """The single-file report rebuilt from a publish folder: every external file put back where the page loads it."""
    page = (pub / 'index.html').read_text()
    page = page.replace('<link rel="stylesheet" href="report.css">', '<style>' + (pub / 'report.css').read_text() + '</style>')
    m = re.search(r'((?:<script src="findings(?:-\d+)?\.js"></script>)+)\n<script src="manual.js"></script>\n'
                  r'<script src="report.js"></script>', page)
    findings = assemble.script_json_lines(pushed_items(pub, m.group(1)))
    page = page[:m.start()] + '<script>' + (pub / 'report.js').read_text() + '</script>' + page[m.end():]
    page = re.sub(r'(?:<script src="slots/\w+(?:-\d+)?\.js"></script>)+', lambda m: '\n'.join(pushed_items(pub, m.group(0))), page)
    page = page.replace('var findings = window.REPORT_FINDINGS;', 'var findings = %s;' % findings)
    js = (pub / 'manual.js').read_text()
    page = page.replace('var manual = window.REPORT_MANUAL;', 'var manual = %s;' % js[js.index('= ') + 2:js.rstrip().rindex(';')])
    return page


DIFF = """diff --git a/src/a.ts b/src/a.ts
index 1..2 100644
--- a/src/a.ts
+++ b/src/a.ts
@@ -10,3 +10,4 @@
 a
+b
 c
 d
"""


class Report:
    """A valid report directory under a temporary scratchpad."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sp = Path(self.tmp.name)
        self.dir = self.sp / 'report'
        self.dir.mkdir()
        (self.sp / 'inputs').mkdir()
        (self.sp / 'inputs' / 'change.diff').write_text(DIFF)
        self.findings = [finding()]
        self.cards = None
        self.spec = {
            'meta': {'title': 'Review MR !1', 'key': 'review-mr-1', 'subject': 'MR !1', 'subjectLine': 'b → master, MR !1',
                     'state': 'abc123', 'author': 'A', 'reference': 'master', 'depth': 'medium', 'date': '2026-10-19',
                     'sources': 3, 'lines': 10, 'worktree': '/w', 'runDir': '/w/review-runs/', 'resume': 'claude --resume x',
                     'ticketBrowseUrl': 'https://example.atlassian.net/browse/'},
            'gitlab': True, 'verdict': {'word': 'not mergeable', 'openBlockers': ['F1']},
            'concepts': [], 'notes': {},
            'manual': {'setup': 'Start the stack.', 'steps': [manual_step('M1')]}}
        self.manual = None  # manual.json; None builds it from spec['manual'], False leaves the file out
        self.frags = {
            'verdict': None,  # built in run() from the open Blockers
            'summary': None,  # built in run() from the open Blockers
            'background': subsec('today'),
            'subject': subsec('goal') + subsec('approach') + subsec('flow'),
            'questions': twin('<p>No open questions.</p>', '<p>Keine offenen Fragen.</p>'),
            'good': twin('<ul><li>Good.</li></ul>', '<ul><li>Gut.</li></ul>'),
            'checks': twin('<p>Checks.</p>', '<p>Prüfungen.</p>'),
            'method': twin('<p>Method.</p>', '<p>Methode.</p>'),
            'glossary': twin('<dl><dt>A</dt><dd>B</dd></dl>', '<dl><dt>A</dt><dd>B</dd></dl>'),
        }
        self.data = None  # raw data.json text, to test what the parser does with it
        self.cold_read = True  # True: a clean cold read of every comment unless notes set one; False: none
        self.method_cold_read = True  # True: method.html gets a paragraph naming the run's notes.coldRead
        self.method_withdrawn = True  # True: method.html gets a paragraph naming the ids in notes.withdrawn

    def run(self):
        if not NODE:
            raise unittest.SkipTest('node not installed: assemble.py checks the inline scripts with node --check')
        self.spec['findings'] = self.findings
        if self.data is None:
            cards = self.cards if self.cards is not None else [
                card(f, [comment()] if self.spec.get('gitlab') else None) for f in self.findings]
            raw = json.dumps(cards, ensure_ascii=False)
        else:
            raw = self.data
        spec = self.spec
        if self.cold_read and isinstance(spec.get('notes'), dict) and 'coldRead' not in spec['notes']:
            # a clean cold read of the comments this run writes, kept out of self.spec so a second run counts again
            try:
                n = sum(len(c.get('gitlab') or []) for c in json.loads(raw) if isinstance(c, dict))
            except (ValueError, TypeError, AttributeError):
                n = 0
            spec = dict(spec, notes=dict(spec['notes'], coldRead=cold_read(n)))
        (self.dir / 'findings.json').write_text(json.dumps(spec, ensure_ascii=False))
        cr = spec['notes'].get('coldRead') if isinstance(spec.get('notes'), dict) else None
        for k, v in self.frags.items():
            if v is None and k in ('verdict', 'summary'):
                v = verdict(ids=(self.spec.get('verdict') or {}).get('openBlockers') or ())
            if k == 'method' and self.method_cold_read and isinstance(cr, dict):
                v += cold_read_paragraph(cr)
            withdrawn = (spec.get('notes') or {}).get('withdrawn') if isinstance(spec.get('notes'), dict) else None
            if k == 'method' and self.method_withdrawn and withdrawn:
                ids = ' '.join(str(w).split(':', 1)[0] for w in withdrawn)
                v += twin('<p>Withdrawn: %s.</p>' % ids, '<p>Zurückgezogen: %s.</p>' % ids)
            (self.dir / (k + '.html')).write_text(v)
        (self.dir / 'data.json').write_text(raw)
        if self.manual is None and self.spec.get('manual'):
            self.manual = manual_json(self.spec['manual'])
        if self.manual:
            (self.dir / 'manual.json').write_text(json.dumps(self.manual, ensure_ascii=False))
        out = subprocess.run([sys.executable, str(HERE / 'assemble.py'), str(self.dir)], capture_output=True, text=True)
        self.out = out.stdout + out.stderr
        self.page = (self.dir / 'review.html').read_text() if (self.dir / 'review.html').exists() else ''
        return out.returncode


class AssembleTest(unittest.TestCase):
    def setUp(self):
        self.p = Report()

    def tearDown(self):
        self.p.tmp.cleanup()

    def ok(self):
        rc = self.p.run()
        self.assertEqual(rc, 0, self.p.out)

    def fails(self, text):
        rc = self.p.run()
        self.assertEqual(rc, 1, self.p.out)
        self.assertIn(text, self.p.out)

    def test_valid_report_passes(self):
        self.ok()

    # placeholders in writer content stay as written
    def test_quoted_interpolation_is_not_replaced(self):
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.p.cards[0]['fields']['what']['text'] = ['The template binds `{{title}}` and `{{customerName}}`.',
                                                     'Die Vorlage bindet `{{title}}` und `{{customerName}}`.']
        self.ok()
        self.assertIn('{{title}}', self.p.page)
        self.assertIn('{{customerName}}', self.p.page)

    def test_interpolation_in_fragment_survives(self):
        self.p.frags['good'] = twin('<p>Binds {{date}}.</p>', '<p>Bindet {{date}}.</p>')
        self.ok()
        self.assertIn('Binds {{date}}.', self.p.page)

    # split publish: the page plus data files; a republish sends only what changed
    PUBLISH_FILES = ['findings.js', 'index.html', 'manual.js', 'report.css', 'report.js'] + sorted(
        'slots/%s.js' % s for s in ['verdict', 'summary', 'background', 'subject', 'questions', 'good', 'checks', 'method', 'glossary'])

    def publish_files(self):
        pub = self.p.dir / 'publish'
        return sorted(str(f.relative_to(pub)) for f in pub.rglob('*') if f.is_file() and f.name != 'manifest.json')

    def test_publish_folder_has_expected_files(self):
        self.ok()
        self.assertEqual(self.publish_files(), sorted(self.PUBLISH_FILES))

    def test_publish_folder_restores_the_single_file(self):
        self.ok()
        self.assertEqual(restore_split(self.p.dir / 'publish'), self.p.page)

    def test_first_publish_lists_every_file(self):
        self.ok()
        line = next(l for l in self.p.out.splitlines() if l.startswith('changed since last publish: '))
        self.assertEqual(line.split(': ', 1)[1].split(', '), sorted(self.PUBLISH_FILES))

    def test_changed_files_after_mark_published(self):
        self.ok()
        mark = subprocess.run([sys.executable, str(HERE / 'assemble.py'), '--mark-published', str(self.p.dir)], capture_output=True, text=True)
        self.assertEqual(mark.returncode, 0, mark.stdout)
        self.p.frags['good'] = twin('<ul><li>Better.</li></ul>', '<ul><li>Besser.</li></ul>')
        self.ok()
        self.assertIn('changed since last publish: index.html, slots/good.js', self.p.out)
        self.assertIn('publish batches: 1', self.p.out)
        self.assertRegex(self.p.out, r'batch 1: index\.html 1-\d+(, \d+-\d+)*; slots/good\.js 1-\d+')

    def test_first_batch_starts_with_style_script_and_manual(self):
        self.ok()
        line = next(l for l in self.p.out.splitlines() if l.startswith('batch 1: '))
        self.assertEqual([p.split(' ')[0] for p in line[len('batch 1: '):].split('; ')][:4],
                         ['index.html', 'report.css', 'report.js', 'manual.js'])

    def test_mark_published_with_files_records_only_those(self):
        self.ok()
        mark = subprocess.run([sys.executable, str(HERE / 'assemble.py'), '--mark-published', str(self.p.dir),
                               'index.html', 'report.css'], capture_output=True, text=True)
        self.assertEqual(mark.returncode, 0, mark.stdout)
        self.assertEqual(sorted(json.loads((self.p.dir / 'publish' / 'manifest.json').read_text())), ['index.html', 'report.css'])
        self.ok()
        line = next(l for l in self.p.out.splitlines() if l.startswith('changed since last publish: '))
        self.assertEqual(line.split(': ', 1)[1].split(', '), [f for f in sorted(self.PUBLISH_FILES) if f != 'report.css'])

    def test_mark_published_unknown_file_fails(self):
        self.ok()
        mark = subprocess.run([sys.executable, str(HERE / 'assemble.py'), '--mark-published', str(self.p.dir),
                               'findings-9.js'], capture_output=True, text=True)
        self.assertEqual(mark.returncode, 1, mark.stdout)
        self.assertIn('not in the publish folder: findings-9.js', mark.stdout + mark.stderr)

    def test_stale_publish_file_is_removed(self):
        self.ok()
        (self.p.dir / 'publish' / 'findings-9.js').write_text('stale')
        self.ok()
        self.assertEqual(self.publish_files(), sorted(self.PUBLISH_FILES))

    def test_slot_over_a_part_is_cut_and_restores(self):
        big = '<ul>\n%s\n</ul>' % '\n'.join('<li>Item %d %s.</li>' % (i, 'word ' * 40) for i in range(1000))
        self.p.frags['good'] = twin(big, '<ul><li>Gut.</li></ul>')
        self.ok()
        files = self.publish_files()
        self.assertIn('slots/good-1.js', files)
        self.assertIn('slots/good-2.js', files)
        self.assertNotIn('slots/good.js', files)
        self.assertEqual(restore_split(self.p.dir / 'publish'), self.p.page)
        pub = self.p.dir / 'publish'
        for f in files:
            self.assertLessEqual(len((pub / f).read_bytes()), assemble.CHUNK_BYTES + 1000, f)
        # the parts run in order and insert the whole slot once, at the last part
        probe = ("var inserted = []; global.window = global; global.document = {currentScript: {insertAdjacentHTML: "
                 "function (w, h) { inserted.push(h); }}};\n")
        js = probe + ''.join((pub / f).read_text() for f in ['slots/good-1.js', 'slots/good-2.js']) + \
            '\nprocess.stdout.write(JSON.stringify(inserted));'
        run = subprocess.run([NODE, '-e', js], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(len(json.loads(run.stdout)), 1)
        self.assertIn('Item 999', json.loads(run.stdout)[0])

    # title: name, subject, ticket
    def test_title_has_name_and_ticket(self):
        self.p.spec['meta'].update(name='Login rework', ticket='PROJ-1')
        self.ok()
        self.assertIn('<title>Login rework · MR !1 · PROJ-1</title>', self.p.page)
        self.assertIn('<div class="brand">Login rework · MR !1 · PROJ-1</div>', self.p.page)
        self.assertIn('<h1><span data-lang="en">Login rework</span><span data-lang="de">Login rework</span></h1>', self.p.page)
        key = '<a href="https://example.atlassian.net/browse/PROJ-1" target="_blank" rel="noopener noreferrer">PROJ-1</a>'
        self.assertIn('<div><dt>Ticket</dt><dd>%s</dd></div>' % key, self.p.page)
        self.assertNotIn('class="subtitle"', self.p.page)

    def test_title_with_ticket_without_name(self):
        self.p.spec['meta']['ticket'] = 'PROJ-1'
        self.ok()
        self.assertIn('<title>Review MR !1 · PROJ-1</title>', self.p.page)
        self.assertIn('<h1><span data-lang="en">Review of MR !1</span><span data-lang="de">Review von MR !1</span></h1>', self.p.page)

    def test_no_ticket_no_ticket_row(self):
        self.ok()
        self.assertNotIn('<dt>Ticket</dt>', self.p.page)

    # header rows: each fact once, labels per subject type
    def test_header_labels_follow_the_subject_type(self):
        for st, eyebrow, label, state in [
                ('mr', 'Merge request review', 'Merge request', 'Reviewed up to'),
                ('branch', 'Branch review', 'Branch', 'Reviewed up to'),
                ('patch', 'Patch review', 'Patch', 'Applied to'),
                ('document', 'Document review', 'Document', 'Version')]:
            with self.subTest(st=st):
                self.p.spec['meta']['subjectType'] = st
                self.p.spec['verdict']['word'] = assemble.SUBJECT_TYPES[st][0] if st != 'mr' else 'not mergeable'
                if st in ('patch', 'document'):
                    self.p.spec['verdict']['word'] = 'not applicable' if st == 'patch' else 'needs revision'
                    self.p.spec.pop('gitlab', None)
                    for f in self.p.findings:
                        f.pop('gitlab', None)
                self.p.run()
                self.assertIn('<p class="eyebrow" id="overview"><span data-lang="en">%s</span>' % eyebrow, self.p.page)
                self.assertIn('<dt><span data-lang="en">%s</span>' % label, self.p.page)
                self.assertIn('<dt><span data-lang="en">%s</span>' % state, self.p.page)
        for old in ['>Author<', '>Autor<', '>State<', '>Subject<', '>Gegenstand<']:
            self.assertNotIn(old, self.p.page)

    def test_reviewed_up_to_shows_short_head_linked_to_its_commit(self):
        sha = 'abc1234def0123456789abc1234def0123456789'
        self.p.spec['meta'].update(subjectType='mr', state=sha)
        self.p.spec['mrUrl'] = 'https://git.example/g/p/-/merge_requests/1'
        self.ok()
        self.assertIn('<dd><a href="https://git.example/g/p/-/commit/%s" target="_blank" rel="noopener noreferrer">abc1234def</a>'
                      ' (<span data-lang="en">branch head</span><span data-lang="de">Branch-Head</span>)' % sha, self.p.page)

    def test_repeated_header_facts_are_notes(self):
        self.p.spec['meta'].update(subjectType='mr', ticket='PROJ-1', state='abc1234def',
                                   subjectLine='ab/PROJ-1-x → master, MR !1, PROJ-1, HEAD abc1234def', reference='MR !1, ADR')
        self.p.spec['mrUrl'] = 'https://git.example/g/p/-/merge_requests/1'
        self.ok()
        for text in ['meta.subjectLine names the ticket', 'meta.subjectLine names the head sha',
                     'meta.reference names the MR or the ticket']:
            self.assertIn(text, self.p.out)

    def test_clean_header_has_no_repeat_notes(self):
        self.p.spec['meta'].update(subjectType='mr', ticket='PROJ-1', state='abc1234def',
                                   subjectLine='!1 · ab/PROJ-1-x → master', reference='ADR, CLAUDE.md')
        self.p.spec['meta']['lines'] = 0
        self.p.spec['mrUrl'] = 'https://git.example/g/p/-/merge_requests/1'
        self.ok()
        self.assertNotIn('names the', self.p.out)
        self.assertIn('<dd><a href="https://git.example/g/p/-/merge_requests/1" target="_blank" rel="noopener noreferrer">!1</a>'
                      ' · ab/PROJ-1-x → master</dd>', self.p.page)

    def test_title_without_ticket_and_name_unchanged(self):
        self.ok()
        self.assertIn('<title>Review MR !1</title>', self.p.page)
        self.assertIn('<span data-lang="en">Review of MR !1</span>', self.p.page)

    def test_name_missing_is_note(self):
        self.ok()
        self.assertIn('note: meta.name missing: the title shows no name', self.p.out)

    def test_ticket_format_checked(self):
        self.p.spec['meta']['ticket'] = 'proj-1'
        self.fails("meta.ticket 'proj-1' is no ticket key")

    def test_name_too_long(self):
        self.p.spec['meta']['name'] = 'x' * 41
        self.fails('meta.name is 41 characters, at most 40')

    def test_no_intro_note_under_heading(self):
        self.ok()
        head = self.p.page[self.p.page.index('<h1>'):self.p.page.index('<dl class="meta">')]
        self.assertNotIn('class="note"', head)

    def test_run_copy_name(self):
        self.p.spec['meta'].update(name='Login-Überarbeitung', ticket='PROJ-1', run='abcd1234', state='abc1234def5678')
        self.ok()
        self.assertIn('run copy name: review-mr-1-proj-1-login-ueberarbeitung-2026-10-19-abc1234def-abcd1234', self.p.out)

    def test_run_name_option_prints_only_the_name(self):
        self.p.spec['meta'].update(name='Login rework', ticket='PROJ-1', run='abcd1234', state='abc1234def5678')
        self.p.spec['findings'] = self.p.findings
        (self.p.dir / 'findings.json').write_text(json.dumps(self.p.spec, ensure_ascii=False))
        out = subprocess.run([sys.executable, str(HERE / 'assemble.py'), '--run-name', str(self.p.dir)], capture_output=True, text=True)
        self.assertEqual((out.returncode, out.stdout), (0, 'review-mr-1-proj-1-login-rework-2026-10-19-abc1234def-abcd1234\n'))

    def test_run_name_option_needs_run(self):
        self.p.spec['findings'] = self.p.findings
        (self.p.dir / 'findings.json').write_text(json.dumps(self.p.spec, ensure_ascii=False))
        out = subprocess.run([sys.executable, str(HERE / 'assemble.py'), '--run-name', str(self.p.dir)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        self.assertIn('meta.run is not set', out.stdout)

    def test_run_copy_name_for_files(self):
        self.p.spec['meta'].update(run='abcd1234', subjectType='files', worktree='')
        self.p.spec['gitlab'] = False
        del self.p.spec['manual']
        self.p.spec['verdict'] = {'word': 'not yet', 'openBlockers': ['F1']}
        self.p.frags['verdict'] = verdict('not yet', 'noch nicht')
        self.ok()
        self.assertIn('run copy name: review-mr-1-2026-10-19-files-abcd1234', self.p.out)

    # manual tests
    def test_manual_ids_must_match_pattern(self):
        self.p.spec['manual']['steps'] = [manual_step('S1')]
        self.fails("manual test step id 'S1' is not M<n>")

    def test_manual_ids_unique(self):
        self.p.spec['manual']['steps'] = [manual_step('M1'), manual_step('M1')]
        self.fails('manual test step id M1 occurs twice')

    def test_manual_json_ids_match_findings_json(self):
        self.p.spec['manual']['steps'] = [manual_step('M1'), manual_step('M2')]
        self.p.manual = manual_json({'setup': 'Start the stack.', 'steps': [manual_step('M1')]})
        self.fails("manual test ids differ: findings.json ['M1', 'M2'], manual.json ['M1']")

    def test_manual_json_missing(self):
        self.p.manual = False
        self.fails('missing manual.json')

    def test_manual_published_id_dropped_needs_withdrawn(self):
        self.p.spec['meta']['published'] = True
        self.p.spec['notes']['manualPublished'] = ['M1', 'M2']
        self.fails('M2 was published and is missing; list it in manual.withdrawn')

    def test_manual_published_id_withdrawn_passes(self):
        self.p.spec['meta']['published'] = True
        self.p.spec['notes']['manualPublished'] = ['M1', 'M2']
        self.p.spec['manual']['withdrawn'] = ['M2: the flow was removed']
        self.ok()

    def test_manual_withdrawn_id_not_reused(self):
        self.p.spec['manual']['withdrawn'] = ['M1: replaced']
        self.fails('M1 is withdrawn and cannot be reused')

    def test_manual_missing_for_runnable_subject(self):
        del self.p.spec['manual']
        self.p.spec['meta']['subjectType'] = 'mr'
        self.fails('manual missing: every branch, mr, pr or patch review lists its manual test steps')

    def test_manual_absent_for_document_ok(self):
        del self.p.spec['manual']
        self.p.spec['meta']['subjectType'] = 'document'
        self.p.spec['gitlab'] = False
        self.p.findings = [finding(sev='nit')]
        self.p.spec['verdict'] = {'word': 'accepted', 'openBlockers': []}
        self.p.frags['verdict'] = verdict('accepted', 'angenommen', ids=())
        self.ok()

    def test_manual_null_allowed_for_runnable_subject(self):
        self.p.spec['manual'] = None
        self.p.spec['meta']['subjectType'] = 'mr'
        self.ok()
        self.assertIn('var manual = null;', self.p.page)
        self.assertIn('No manual tests for this subject.', self.p.page)

    def test_manual_missing_in_report_published_before_manual_tests_is_note(self):
        del self.p.spec['manual']
        self.p.spec['meta']['published'] = True
        self.ok()
        self.assertIn('note: manual missing: published before manual tests existed', self.p.out)

    def test_withdrawn_finding_id_not_reused(self):
        self.p.spec['meta']['published'] = True
        self.p.spec['notes']['withdrawn'] = ['F1: fixed in abc1234']
        self.fails('F1 is withdrawn and cannot be reused')

    def test_run_name_stored_wins(self):
        self.p.spec['meta'].update(run='abcd1234', state='abc1234def5678', runName='review-mr-1-2026-10-01-0000000000-11112222')
        self.p.spec['findings'] = self.p.findings
        (self.p.dir / 'findings.json').write_text(json.dumps(self.p.spec, ensure_ascii=False))
        out = subprocess.run([sys.executable, str(HERE / 'assemble.py'), '--run-name', str(self.p.dir)], capture_output=True, text=True)
        self.assertEqual(out.stdout, 'review-mr-1-2026-10-01-0000000000-11112222\n')

    def test_index_over_what_a_batch_leaves_fails(self):
        self.p.spec['meta']['subjectLine'] = 'x' * (assemble.BATCH_BYTES - assemble.CHUNK_BYTES)
        self.fails('publish/index.html is')

    def test_publish_file_line_over_read_part_fails(self):
        self.p.frags['good'] = twin('<ul><li>%s</li></ul>' % ('<b class="x">"q"</b>' * 2200), '<ul><li>Gut.</li></ul>')
        self.fails('publish/slots/good.js line')

    def test_manual_twins_required(self):
        self.p.manual = manual_json(self.p.spec['manual'])
        self.p.manual['steps'][0]['do'] = [self.p.manual['steps'][0]['do'][0], '']
        self.fails('manual.json M1: do is no [en, de] pair')

    def test_manual_untranslated(self):
        self.p.manual = manual_json(self.p.spec['manual'])
        self.p.manual['steps'][0]['expect'] = ['The dashboard opens for you.'] * 2
        self.fails('manual.json M1: expect is not translated')

    def test_manual_english_matches_findings_json(self):
        self.p.manual = manual_json(self.p.spec['manual'])
        self.p.manual['steps'][0]['do'][0] = 'Something else.'
        self.fails('manual.json M1: the English do differs from findings.json')

    def test_manual_data_reaches_page(self):
        self.ok()
        self.assertIn('var manual = ', self.p.page)
        self.assertIn('Open the admin login and sign in.', self.p.page)

    def test_manual_is_first_subsection_of_assessment(self):
        self.ok()
        root = assemble.parse_html(self.p.page)
        sec = next(n for n in assemble.walk(root) if n['tag'] == 'section' and n['attrs'].get('id') == 'assessment')
        subs = [n['attrs']['id'] for n in assemble.walk(sec) if assemble.is_listed_subsec(n)]
        self.assertEqual(subs, ['manual', 'findings', 'questions', 'good', 'gitlab'])

    def test_toc_lists_manual_first(self):
        self.ok()
        toc = re.search(r'<a href="#assessment">.*?</ol>', self.p.page, re.S).group(0)
        self.assertEqual(re.findall(r'href="#(\w+)"', toc)[1:3], ['manual', 'findings'])

    def test_manual_empty_line_for_document(self):
        del self.p.spec['manual']
        self.p.spec['meta']['subjectType'] = 'document'
        self.p.spec['gitlab'] = False
        self.p.findings = [finding(sev='nit')]
        self.p.spec['verdict'] = {'word': 'accepted', 'openBlockers': []}
        self.p.frags['verdict'] = verdict('accepted', 'angenommen', ids=())
        self.ok()
        self.assertIn('var manual = null;', self.p.page)
        self.assertIn('No manual tests for this subject.', self.p.page)
        self.assertIn('Keine manuellen Tests für diesen Gegenstand.', self.p.page)

    # data.json
    def test_data_json_error_never_echoes_source(self):
        self.p.data = '[{"id": "F1", "note": "Error handling", "pw": "Xk9fakevalue123" oops}]'
        self.fails('data.json is not valid JSON')
        self.assertNotIn('Xk9fakevalue123', self.p.out)
        self.assertNotIn('Error handling', self.p.out)

    def test_data_json_is_never_executed(self):
        self.p.data = 'var findings = [];'
        self.fails('data.json is not valid JSON')

    def test_report_carries_the_checked_array_with_script_tags_escaped(self):
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.p.cards[0]['fields']['why']['text'] = ['The text closes </script> early.', 'Der Text schließt </script> zu früh.']
        self.ok()
        self.assertNotIn('closes </script>', self.p.page)
        self.assertIn('closes \\u003c/script>', self.p.page)

    # no single-language mode in the review template
    def test_no_single_language_switch(self):
        self.ok()
        self.assertNotIn('ONLY', self.p.page)
        self.assertIn('data-set-lang="en"', self.p.page)
        self.assertIn('data-set-lang="de"', self.p.page)

    # card fields: what, why, fix and verify, each a visible text and its details (more) or null
    def test_field_not_an_object_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.p.cards[0]['fields']['why'] = ['Why.', 'Warum.']
        self.fails('F1: fields.why must be {"text": [en, de], "more": [en, de] or null}')

    def test_fields_missing_one_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment()])]
        del self.p.cards[0]['fields']['verify']
        self.fails('F1: fields must hold exactly what, why, fix, verify')

    def test_more_not_a_pair_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.p.cards[0]['fields']['fix']['more'] = ['Only English.']
        self.fails('F1: fields.fix.more is neither a complete [en, de] pair nor null')

    def test_old_card_shape_fails(self):
        # a card with plain and tech, or without fields, comes from an older skill version; its report is edited in its own HTML
        for change in ['plain', 'tech', 'no fields']:
            with self.subTest(change=change):
                self.p.cards = [card(self.p.findings[0], [comment()])]
                if change == 'no fields':
                    del self.p.cards[0]['fields']
                else:
                    self.p.cards[0][change] = {k: ['X.', 'Y.'] for k in CARD_FIELDS}
                self.fails('F1: data.json has the card shape of an older skill version (%s)' % change)
                self.assertIn('changed in its own HTML (report-sections.md)', self.p.out)
                self.assertIn('FAILED, 1 problem(s)', self.p.out)

    def test_consolidated_text_in_data_fails(self):
        # the consolidated what stays in findings.json, the record; the card shows the writer's fields
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.p.cards[0]['what'] = ['What happens.', 'Was passiert.']
        self.fails('F1: data.json carries the consolidated what; it stays in findings.json')

    def test_file_line_in_card_text_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.p.cards[0]['fields']['why']['text'] = ['The loop in `src/a.ts:11` never ends.', 'Die Schleife in `src/a.ts:11` endet nie.']
        self.fails('F1: the English fields.why.text names src/a.ts:11; file:line belongs in its more')
        self.p.cards[0]['fields']['why'] = {'text': ['The loop never ends.', 'Die Schleife endet nie.'],
                                            'more': ['It loops at `src/a.ts:11`, `src/a.ts:12`, `src/b.ts:3` and `src/c.ts:4`.',
                                                     'Sie kreist bei `src/a.ts:11`, `src/a.ts:12`, `src/b.ts:3` und `src/c.ts:4`.']}
        self.ok()  # a card's details may cite more than three places: the evidence path needs them

    def test_card_text_starting_with_its_label_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.p.cards[0]['fields']['fix']['text'] = ['Fix: increment `x`.', '`x` erhöhen.']
        self.fails("F1: the English fields.fix.text starts with its label 'Fix'")
        self.p.cards[0]['fields']['fix']['text'] = ['Increment `x`.', '**Lösung:** `x` erhöhen.']
        self.fails("F1: the German fields.fix.text starts with its label 'Lösung'")

    def test_card_text_paragraph_over_the_visible_limit_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment()])]
        n = assemble.VISIBLE_PARAGRAPH_MAX
        self.p.cards[0]['fields']['why']['text'] = [' '.join(['word'] * n) + '.', ' '.join(['Wort'] * n) + '.']
        self.ok()
        self.p.cards[0]['fields']['why']['text'] = [' '.join(['word'] * (n + 1)) + '.', ' '.join(['Wort'] * n) + '.']
        self.fails('F1: a paragraph of the English fields.why.text has %d words, at most %d' % (n + 1, n))
        # each list item is a paragraph of its own
        item = '- ' + ' '.join(['word'] * 30)
        self.p.cards[0]['fields']['why']['text'] = ['Three cases.\n\n' + '\n'.join([item] * 3), 'Drei Fälle.\n\n' + '\n'.join([item] * 3)]
        self.ok()

    def test_card_more_paragraph_over_the_detail_limit_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment()])]
        n = assemble.DETAIL_PARAGRAPH_MAX
        long = ' '.join(['word'] * (n + 1)) + '.'
        self.p.cards[0]['fields']['fix']['more'] = ['Short. `src/a.ts:11`\n\n' + long, 'Kurz. `src/a.ts:11`']
        self.fails('F1: a paragraph of the English fields.fix.more has %d words, at most %d' % (n + 1, n))

    def test_blocker_needs_evidence_and_verify_details(self):
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.p.cards[0]['fields']['what']['more'] = None
        self.fails('F1: a Blocker needs the evidence path in fields.what.more, with at least one file:line (English)')
        self.p.cards[0]['fields']['what']['more'] = ['The path runs through `src/a.ts:11`.', 'Der Weg führt durch den Zähler.']
        self.fails('F1: a Blocker needs the evidence path in fields.what.more, with at least one file:line (German)')
        self.p.cards[0]['fields']['what']['more'] = ['The path runs through `src/a.ts:11`.', 'Der Weg führt durch `src/a.ts:11`.']
        self.p.cards[0]['fields']['verify']['more'] = None
        self.fails('F1: a Blocker needs fields.verify.more')

    def test_non_blocker_needs_no_details(self):
        self.p.findings = [finding(sev='nit')]
        self.p.spec['verdict'] = {'word': 'mergeable', 'openBlockers': []}
        self.p.frags['verdict'] = verdict('mergeable', 'mergebar', ids=())
        self.p.cards = [card(self.p.findings[0], [comment()])]
        for k in CARD_FIELDS:
            self.p.cards[0]['fields'][k]['more'] = None
        self.ok()

    def test_principle_stands_in_the_what_text(self):
        self.p.spec['meta']['date'] = '2026-11-05'
        self.p.findings = [finding(category='design', principle='DRY, KISS')]
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.ok()
        self.p.cards[0]['fields']['what']['text'] = ['The mapping is written twice (DRY).', 'Die Zuordnung steht doppelt (DRY).']
        self.fails('F1: the English fields.what.text does not name the principle KISS')

    def test_removes_named_on_both_cards(self):
        self.p.findings = [finding('F1', removes=['F2']), finding('F2')]
        self.p.spec['verdict']['openBlockers'] = ['F1', 'F2']
        self.p.frags['verdict'] = verdict(ids=('F1', 'F2'))
        self.p.cards = [card(f, [comment()]) for f in self.p.findings]
        self.fails('F1: the English fields.fix.text does not name F2, which its fix also removes')
        self.p.cards[0]['fields']['fix']['text'] = ['Drop the timer; this also removes F2.', 'Den Timer entfernen; das behebt auch F2.']
        self.fails('F2: the English fields.fix.text does not name F1, whose fix also removes it')
        self.p.cards[1]['fields']['fix']['text'] = ['Fix the offset, or drop the timer (F1).', 'Den Versatz beheben, oder den Timer entfernen (F1).']
        self.ok()
        self.p.findings[0]['removes'] = ['F9']
        self.fails('F1: removes names F9, which is no other finding')

    # no reason field: a Blocker's verify states the proof
    def test_reason_field_fails(self):
        self.p.findings[0]['reason'] = 'a'
        self.fails("F1: findings carry no reason; a Blocker's verify states the proof")

    def test_no_trigger_left(self):
        for doc in ['SKILL.md', 'reviewer-prompt.md', 'report-sections.md', 'tooling.md', 'review-report-template.html', 'assemble.py']:
            with self.subTest(doc=doc):
                text = (HERE / doc).read_text()
                self.assertNotIn('Becomes a Blocker', text)
                self.assertNotIn('Wird zum Blocker', text)
                # the Optional's old `trigger` field (when it becomes a Blocker) is gone; the `triggers` list of a merged finding is another field
                for use in ["get('trigger')", "['trigger']", "'trigger' in", "'trigger':"]:
                    self.assertNotIn(use, text)

    def test_done_box_has_no_visible_text(self):
        self.ok()
        self.assertIn('aria-label="Done / Erledigt"', self.p.page)
        self.assertNotIn("pair(['Done', 'Erledigt'])", self.p.page)

    def test_field_labels_and_expand_all(self):
        self.ok()
        for word in ['Simple', 'Technical', 'Detailed', 'Einfach', 'Technisch', 'Detailliert']:
            self.assertNotIn('>%s</span>' % word, self.p.page)
        self.assertNotIn('data-set-level', self.p.page)
        self.assertNotIn('data-level', self.p.page)
        self.assertIn('id="toggle-all"', self.p.page)
        self.assertIn('<span data-lang="en">Expand all details</span><span data-lang="de">Alle Details aufklappen</span>', self.p.page)
        self.assertIn("['why', ['Impact', 'Auswirkung']]", self.p.page)

    # verdict: the line from verdict.word, one text, every open Blocker named
    def test_verdict_banner_comes_from_the_word(self):
        self.ok()
        self.assertIn('<p class="verdict-label"><span data-lang="en">Verdict</span><span data-lang="de">Urteil</span></p>', self.p.page)
        self.assertIn('<div class="verdict fail">', self.p.page)
        self.assertIn('<p class="verdict-word"><span class="verdict-icon" aria-hidden="true">✕</span><strong>'
                      '<span data-lang="en">Not mergeable</span><span data-lang="de">Nicht mergebar</span></strong></p>', self.p.page)

    def test_verdict_banner_texts(self):
        for word, icon, en, de in [('mergeable', '✓', 'Mergeable', 'Mergebar'),
                                   ('not yet', '✕', 'Not yet fit for use', 'Noch nicht einsatzbereit'),
                                   ('needs revision', '✕', 'Needs revision', 'Überarbeitung nötig'),
                                   ('fit for use', '✓', 'Fit for use', 'Einsatzbereit')]:
            with self.subTest(word=word):
                self.assertEqual(assemble.verdict_line(word), '<span class="verdict-icon" aria-hidden="true">%s</span><strong>'
                                 '<span data-lang="en">%s</span><span data-lang="de">%s</span></strong>' % (icon, en, de))

    def test_old_lead_word_is_dropped(self):
        self.p.frags['verdict'] = para('<strong>not mergeable</strong>. The approach holds; F1 breaks.',
                                       '<strong>Urteil: nicht mergebar.</strong> Der Ansatz trägt; F1 bricht.')
        self.ok()
        self.assertIn('<p data-lang="en">The approach holds; <a href="#F1">F1</a> breaks.</p>', self.p.page)
        self.assertIn('<p data-lang="de">Der Ansatz trägt; <a href="#F1">F1</a> bricht.</p>', self.p.page)

    def test_lead_word_against_the_verdict_fails(self):
        self.p.frags['verdict'] = para('<strong>Verdict: mergeable.</strong> F1 is not mergeable.', '<strong>Urteil: nicht mergebar.</strong> F1.')
        self.fails("verdict.html: the en lead says 'mergeable', verdict.word gives 'not mergeable'")

    def test_short_verdict_passes(self):
        self.p.spec['meta']['date'] = '2026-11-06'
        self.p.frags['verdict'] = para('The MR lets customers book again. It does not work yet: the booking is lost on iOS.',
                                       'Der MR lässt Kunden erneut buchen. Er funktioniert noch nicht: Die Buchung geht auf iOS verloren.')
        self.ok()
        self.assertIn('<p data-lang="en">The MR lets customers book again.', self.p.page)

    def test_positive_verdict_needs_its_abstract_too(self):
        self.p.findings = [finding(sev='nit')]
        self.p.spec['verdict'] = {'word': 'mergeable', 'openBlockers': []}
        self.p.frags['verdict'] = ''
        self.fails('verdict.html is empty')

    def test_negative_verdict_needs_its_summary(self):
        self.p.frags['verdict'] = ''
        self.fails('verdict.html is empty')

    def test_summary_restating_the_banner_fails(self):
        self.p.spec['meta']['date'] = '2026-11-06'
        for en, de, text in [('No Blocker is open; the cache breaks (F1).', 'Der Cache bricht (F1).', "restates 'No Blocker'"),
                             ('The cache breaks (F1), so not mergeable.', 'Der Cache bricht (F1).', "restates 'not mergeable'"),
                             ('The cache breaks (F1).', 'Kein offener Blocker; der Cache bricht (F1).', "restates 'Kein offener Blocker'")]:
            with self.subTest(text=text):
                self.p.frags['verdict'] = para(en, de)
                self.fails(text)

    def test_lines_changed_stand_in_the_subject_row(self):
        self.p.spec['meta']['lines'] = 1428
        self.ok()
        self.assertIn('b → master, MR !1 · <span data-lang="en" title="without lockfiles and generated code">1,428 lines changed</span>'
                      '<span data-lang="de" title="ohne Lockfiles und generierten Code">1.428 geänderte Zeilen</span></dd>', self.p.page)
        self.assertNotIn('<b>1428</b>', self.p.page)

    def test_stats_row_has_no_sources(self):
        self.ok()
        stats = self.p.page[self.p.page.index('<div class="stats">'):]
        stats = stats[:stats.index('</div>\n  </div>') if '</div>\n  </div>' in stats else 600]
        self.assertNotIn('>Sources<', stats)

    def test_abstract_with_an_id_fails(self):
        self.p.spec['meta']['date'] = '2026-11-06'
        self.p.frags['verdict'] = para('The booking is lost on iOS (F1).', 'Die Buchung geht auf iOS verloren.')
        self.fails('verdict.html: the en abstract names F1; finding ids belong in the findings summary (3.2)')

    def test_abstract_with_code_fails(self):
        self.p.spec['meta']['date'] = '2026-11-06'
        self.p.frags['verdict'] = para('The <code>LANG</code> cookie is lost.', 'Das Cookie geht verloren.')
        self.fails('verdict.html: the abstract names code')

    def test_summary_without_blocker_ids_passes(self):
        self.p.spec['meta']['date'] = '2026-11-06'
        self.p.frags['verdict'] = para('The MR does not work yet.', 'Der MR funktioniert noch nicht.')
        self.p.frags['summary'] = twin('<ul><li>Blocker: the booking is lost.</li></ul>', '<ul><li>Blocker: die Buchung geht verloren.</li></ul>')
        self.ok()

    def test_summary_id_range_fails(self):
        self.p.spec['meta']['date'] = '2026-11-06'
        self.p.frags['verdict'] = para('The MR does not work yet.', 'Der MR funktioniert noch nicht.')
        self.p.frags['summary'] = para('Blocker: the booking is lost (F1–F1).', 'Blocker: die Buchung geht verloren.')
        self.fails('summary.html: the en text has an id range')

    def test_summary_line_with_many_ids_fails(self):
        self.p.findings = [finding()] + [finding('F%d' % i, sev='nit') for i in range(2, 6)]
        self.p.spec['meta']['date'] = '2026-11-06'
        self.p.frags['verdict'] = para('The MR does not work yet.', 'Der MR funktioniert noch nicht.')
        self.p.frags['summary'] = twin('<ul><li>Nit: wording (F2, F3, F4, F5).</li></ul>', '<ul><li>Nit: Wortlaut.</li></ul>')
        self.fails('summary.html: a severity line names 4 ids, at most 3')

    def test_summary_is_required_from_its_date(self):
        del self.p.frags['summary']
        self.ok()   # a run before the summary builds without it
        self.p.spec['meta']['date'] = '2026-11-06'
        self.p.frags['verdict'] = para('The MR does not work yet.', 'Der MR funktioniert noch nicht.')
        self.fails('missing fragment summary.html')

    def test_long_summary_fails_from_its_date(self):
        self.p.spec['meta']['date'] = '2026-11-06'
        self.p.frags['verdict'] = para('The MR does not work yet.', 'Der MR funktioniert noch nicht.')
        self.p.frags['summary'] = para(' '.join(['word'] * 120) + ' F1.', 'Blocker: F1.')
        self.fails('summary.html: the en text has 121 words, at most 120')

    def test_unchecked_findings_are_named_under_the_summary(self):
        self.p.findings = [finding(check='unchecked')]
        self.ok()
        self.assertIn('<p class="note"><span data-lang="en">Not fully checked: <a href="#F1">F1</a></span>'
                      '<span data-lang="de">Nicht vollständig geprüft: <a href="#F1">F1</a></span></p>', self.p.page)

    def test_checked_findings_add_no_unchecked_line(self):
        self.ok()
        self.assertNotIn('Not fully checked', self.p.page)

    def test_legend_is_a_closed_reference_with_categories(self):
        self.ok()
        self.assertIn('<details class="legend"><summary><span data-lang="en">What severities and categories mean</span>', self.p.page)
        self.assertIn('<dt><span data-lang="en">Architecture</span><span data-lang="de">Architektur</span></dt><dd><span data-lang="en">'
                      'fit with the rest of the system', self.p.page)
        self.assertNotIn('One consolidated list', self.p.page)

    def test_fragments_link_ids_and_jira_keys_outside_code(self):
        self.p.spec['meta']['ticket'] = 'PROJ-1'
        self.p.frags['verdict'] = para('Waits for PROJ-736 (F1); see <code>F1</code> and <code>PROJ-9</code>, branch x/PROJ-2-y.',
                                       'Wartet auf PROJ-736 (F1).')
        self.ok()
        self.assertIn('<p data-lang="en">Waits for <a href="https://example.atlassian.net/browse/PROJ-736" target="_blank" '
                      'rel="noopener noreferrer">PROJ-736</a> (<a href="#F1">F1</a>); see <code>F1</code> and <code>PROJ-9</code>, '
                      'branch x/PROJ-2-y.</p>', self.p.page)

    def test_card_text_links_jira_keys(self):
        self.p.spec['meta']['ticket'] = 'PROJ-1'
        self.ok()
        self.assertIn('var JIRA = {"base": "https://example.atlassian.net/browse/", "project": "PROJ"};', self.p.page)
        self.assertIn('jira(esc(ticketKey(f)))', self.p.page)

    def test_no_ticket_no_jira_config(self):
        self.ok()
        self.assertIn('var JIRA = null;', self.p.page)

    def test_long_verdict_fails_from_its_date(self):
        long_en, long_de = ' '.join(['word'] * 70) + ' F1.', ' '.join(['Wort'] * 70) + ' F1.'
        self.p.frags['verdict'] = para(long_en, long_de)
        self.ok()   # a review before 2026-11-06 builds unchanged
        self.p.spec['meta']['date'] = '2026-11-06'
        self.fails('verdict.html: the en text has 71 words, at most 70')

    def test_verdict_details_fail_from_its_date(self):
        self.p.spec['meta']['date'] = '2026-11-06'
        self.p.frags['verdict'] = verdict() + disclosure('Fix F1.', 'F1 beheben.', 'More.', 'Mehr.')
        self.fails('verdict.html: the verdict is an abstract without details')

    def test_reviewed_row_and_wide_sources(self):
        self.ok()
        self.assertIn('<div><dt><span data-lang="en">Reviewed</span><span data-lang="de">Geprüft am</span></dt>'
                      '<dd><span data-lang="en">2026-10-19 · depth medium</span><span data-lang="de">2026-10-19 · Tiefe medium</span></dd></div>',
                      self.p.page)
        self.assertNotIn('<div class="wide"><dt><span data-lang="en">Further sources</span>', self.p.page)
        method = self.p.page[self.p.page.index('<div id="method"'):]
        self.assertIn('<p class="further"><span data-lang="en">Further sources</span><span data-lang="de">Weitere Quellen</span>: master</p>', method)
        for old in ['consolidated 2026', 'konsolidiert am', 'Claude (orchestrator)']:
            self.assertNotIn(old, self.p.page)

    def test_empty_reference_drops_the_further_line(self):
        self.p.spec['meta']['reference'] = ''
        self.ok()
        self.assertNotIn('class="further"', self.p.page)

    def test_toc_starts_with_unnumbered_overview(self):
        self.ok()
        toc = self.p.page[self.p.page.index('<nav class="toc"'):self.p.page.index('</nav>')]
        self.assertIn('<li class="toc-top"><a href="#overview"><span data-lang="en">Overview</span><span data-lang="de">Überblick</span></a></li>', toc)
        self.assertIn('<p class="eyebrow" id="overview">', self.p.page)
        self.assertIn('.toc li.toc-top > a::before { content: none; }', self.p.page)

    def test_bold_key_term_stays(self):
        self.p.frags['verdict'] = para('<strong>The cache</strong> breaks, F1.', '<strong>Der Cache</strong> bricht, F1.')
        self.ok()
        self.assertIn('<p data-lang="en"><strong>The cache</strong> breaks, <a href="#F1">F1</a>.</p>', self.p.page)

    def test_verdict_with_details_passes(self):
        self.p.frags['verdict'] = verdict() + disclosure('Fix: increment `x` (F1).', 'Lösung: `x` erhöhen (F1).',
                                                         'The loop ends after one pass.', 'Die Schleife endet nach einem Durchlauf.')
        self.ok()

    def test_open_blockers_must_match_ids(self):
        self.p.spec['verdict']['openBlockers'] = ['F99']
        self.fails('openBlockers')

    def test_positive_verdict_with_blocker_fails(self):
        self.p.spec['verdict']['word'] = 'mergeable'
        self.p.frags['verdict'] = verdict('mergeable', 'mergebar')
        self.fails('verdict')

    def test_positive_verdict_without_blocker_passes(self):
        self.p.findings = [finding(sev='nit')]
        self.p.spec['verdict'] = {'word': 'mergeable', 'openBlockers': []}
        self.p.frags['verdict'] = verdict('mergeable', 'mergebar')
        self.ok()

    def test_positive_verdict_with_negative_phrase_elsewhere_passes(self):
        self.p.findings = [finding(sev='nit')]
        self.p.spec['meta']['subjectType'] = 'files'
        self.p.spec['gitlab'] = False
        self.p.cards = [card(self.p.findings[0])]
        self.p.spec['verdict'] = {'word': 'fit for use', 'openBlockers': []}
        self.p.frags['verdict'] = para('The cache is not yet warm.', 'Text.')
        self.ok()

    # GitLab anchors and limits
    def test_line_anchor_outside_hunk_fails_without_mr(self):
        self.p.cards = [card(self.p.findings[0], [comment(startLine=200)])]
        self.fails('outside')

    def test_file_anchor_outside_hunk_passes(self):
        self.p.cards = [card(self.p.findings[0], [comment(startLine=200, anchor='file')])]
        self.ok()

    def test_three_comments_fail(self):
        self.p.cards = [card(self.p.findings[0], [comment(), comment(startLine=12), comment(startLine=13)])]
        self.fails('two at most')

    def test_line_range_inside_the_hunk_passes_and_shows_the_hint(self):
        self.p.cards = [card(self.p.findings[0], [comment(endLine=13)])]
        self.ok()
        self.assertIn("'multi-line comment: select ' + (old ? 'old ' : '') + 'lines ' + lines", self.p.page)
        self.assertIn('"endLine": 13', self.p.page)

    def test_line_range_past_the_hunk_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment(endLine=14)])]
        self.fails('line range src/a.ts:11–14 leaves the diff hunk at line 14')

    def test_old_side_range_counts_old_lines(self):
        self.p.cards = [card(self.p.findings[0], [comment(startLine=10, endLine=12, side='old')])]
        self.ok()
        self.p.cards = [card(self.p.findings[0], [comment(startLine=10, endLine=13, side='old')])]
        self.fails('leaves the diff hunk at line 13')

    def test_end_line_not_after_start_fails(self):
        for end in (11, 10, '13', True):
            with self.subTest(end=end):
                self.p.cards = [card(self.p.findings[0], [comment(endLine=end)])]
                self.fails('is not a line number after startLine')

    def test_end_line_only_on_a_line_comment(self):
        self.p.cards = [card(self.p.findings[0], [comment(startLine=200, endLine=210, anchor='file')])]
        self.fails('a range only on a line comment')

    def test_place_fields_by_anchor(self):
        self.p.cards = [card(self.p.findings[0], [comment(startLine=None)])]
        self.fails('needs a startLine')
        self.p.cards = [card(self.p.findings[0], [comment(path=None, startLine=None, anchor='file')])]
        self.fails('a file comment needs a path')
        self.p.cards = [card(self.p.findings[0], [comment(path=None, startLine=3, anchor='mr')])]
        self.fails('startLine 3 without a path')
        self.p.cards = [card(self.p.findings[0], [comment(startLine=0)])]
        self.fails('startLine 0 at src/a.ts:0 is not a line number')
        # a general MR comment may name no file at all, or a file outside the diff
        self.p.cards = [card(self.p.findings[0], [comment(path=None, startLine=None, anchor='mr')])]
        self.ok()
        self.p.cards = [card(self.p.findings[0], [comment(path='server/guard.ts', startLine=42, anchor='mr')])]
        self.ok()

    def test_old_at_field_fails(self):
        self.p.cards = [card(self.p.findings[0], [{'at': 'src/a.ts:11', 'anchor': 'line', 'text': comment()['text']}])]
        self.fails('GitLab comment has "at"')

    def test_tool_name_or_id_in_comment_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment(en='`x` resets, as codex found in F1. It loops.\n\nSuggestion: fix `x`.')])]
        self.fails('tool name or finding id')

    def test_long_comment_fails(self):
        long = ' '.join(['word'] * 98) + '.\n\nSuggestion: fix `x`.'
        self.p.cards = [card(self.p.findings[0], [comment(en=long)])]
        self.fails('over the word limit (100 words, a list line 20)')

    def test_comment_at_the_word_limit_passes(self):
        full = ' '.join(['word'] * 97) + '.\n\nSuggestion: fix `x`.'
        self.p.cards = [card(self.p.findings[0], [comment(en=full)])]
        self.ok()

    # an Architecture or Design finding names the principle it breaks (SKILL.md §4, step 9)
    def principle_run(self, date='2026-11-04', category='architecture', **kw):
        self.p.spec['meta']['date'] = date
        self.p.findings = [finding(category=category, **kw)]

    def test_architecture_finding_without_principle_fails(self):
        self.principle_run()
        self.fails('F1: category architecture needs principle')

    def test_design_finding_without_principle_fails(self):
        self.principle_run(category='design')
        self.fails('F1: category design needs principle')

    def test_architecture_finding_with_principle_passes(self):
        self.principle_run(principle='A stored derived value breaks the single source of truth.')
        self.ok()

    def test_null_principle_passes(self):
        # the check answered NONE: the field is there, the comment has no principle sentence
        self.principle_run(principle=None)
        self.ok()

    def test_empty_principle_fails(self):
        self.principle_run(principle='  ')
        self.fails('F1: principle must name the principles or be null')

    def test_other_category_needs_no_principle(self):
        self.principle_run(category='functionality')
        self.ok()

    def test_other_category_with_principle_fails(self):
        self.principle_run(date='2026-11-05', category='tests', principle='Test via public APIs.')
        self.fails('F1: only Architecture and Design findings carry a principle')

    def test_other_category_with_null_principle_passes(self):
        self.principle_run(date='2026-11-05', category='tests', principle=None)
        self.ok()

    def test_run_before_the_rule_keeps_principle_on_other_category(self):
        # a principle elsewhere was allowed until 2026-11-04; such a run still republishes
        self.principle_run(date='2026-11-04', category='usability', principle='Least astonishment.')
        self.ok()

    def test_old_run_without_principle_passes(self):
        # a run dated before the field existed still republishes
        self.principle_run(date='2026-11-03')
        self.ok()

    def test_old_run_that_uses_principle_needs_it_everywhere(self):
        self.principle_run(date='2026-11-03')
        self.p.findings.append(finding('F2', category='functionality', principle='Dependencies point inwards.'))
        self.p.spec['verdict']['openBlockers'] = ['F1', 'F2']
        self.p.frags['verdict'] = verdict(ids=('F1', 'F2'))
        self.fails('F1: category architecture needs principle')

    def test_comment_on_non_branch_subject_fails(self):
        self.p.spec['meta']['subjectType'] = 'files'
        del self.p.spec['gitlab']
        self.p.spec['verdict']['word'] = 'not yet'
        self.p.frags['verdict'] = verdict('not yet', 'noch nicht')
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.fails("F1: GitLab comment on a 'files' subject")

    def test_gitlab_flag_follows_the_subject_type(self):
        self.p.spec['meta']['subjectType'] = 'files'
        del self.p.spec['gitlab']
        self.p.spec['verdict']['word'] = 'not yet'
        self.p.frags['verdict'] = verdict('not yet', 'noch nicht')
        self.p.cards = [card(self.p.findings[0])]
        self.ok()
        self.assertIn('No GitLab comments for this subject type.', self.p.page)
        self.p.spec['gitlab'] = True
        self.fails("gitlab is true, but subjectType 'files' has no GitLab comments")
        self.p.spec['meta']['subjectType'] = 'mr'
        self.p.spec['gitlab'] = False
        self.p.spec['verdict']['word'] = 'not mergeable'
        self.p.frags['verdict'] = None
        self.fails("gitlab is false, but subjectType 'mr' has GitLab comments")
        # the root error only, no follow-up error per finding
        self.assertNotIn('no GitLab comment', self.p.out)
        self.assertIn('FAILED, 1 problem(s)', self.p.out)

    # language twins and required structure
    def test_unpaired_language_blocks_fail_even_when_counts_match(self):
        self.p.frags['questions'] = '<div data-lang="en"><p>Only English.</p></div>'
        self.p.frags['good'] = '<div data-lang="de"><p>Nur Deutsch.</p></div>'
        self.fails('twin')

    def test_empty_fragment_fails(self):
        self.p.frags['background'] = '\n'
        self.fails('background')

    def test_missing_today_subsection_fails(self):
        self.p.frags['background'] = subsec('basics-x')
        self.fails('today')

    def test_line_over_one_read_part_fails(self):
        self.p.frags['good'] = twin('<ul><li>%s</li></ul>' % ('word ' * 10000), '<ul><li>%s</li></ul>' % ('Wort ' * 10000))
        self.fails('over the 45 KB one Read part holds')

    def test_fixed_subsections_come_first(self):
        # 1.1 and 2.1 to 2.3 keep their numbers only when they lead their section
        self.p.frags['background'] = subsec('basics-x') + subsec('today')
        self.fails('the fixed ones (#today) come first')
        self.p.frags['background'] = subsec('today')
        self.p.frags['subject'] = subsec('flow') + subsec('goal') + subsec('approach')
        self.fails('the fixed ones (#goal, #approach, #flow) come first')

    def test_approach_is_required(self):
        # 2.2 Approach is a fixed subsection of every report
        self.p.frags['subject'] = subsec('goal') + subsec('flow')
        self.fails('subsection #approach missing')
        self.p.frags['subject'] = subsec('goal') + subsec('flow') + subsec('approach')
        self.fails('the fixed ones (#goal, #approach, #flow) come first')
        self.p.frags['subject'] = subsec('goal') + subsec('approach') + subsec('flow')
        self.ok()

    def test_figure_or_table_inside_details_fails(self):
        # figures and tables stand in the visible text: a reader who never opens anything still sees them
        fig = '<figure><svg viewBox="0 0 10 10"><rect x="0" y="0" width="5" height="5"/></svg>%s</figure>' % (
            twin('Figure.', 'Abbildung.', 'figcaption'))
        self.p.frags['subject'] = subsec('goal', body=para() + fig + disclosure()) + subsec('approach') + subsec('flow')
        self.ok()
        inside = disclosure().replace('</div></details>', fig + '</div></details>', 1)
        self.p.frags['subject'] = subsec('goal', body=para() + inside) + subsec('approach') + subsec('flow')
        self.fails('subject.html: a figure or table inside a details.pt in #goal')
        table = '<div class="tbl"><table><tr data-lang="en"><td>A</td></tr><tr data-lang="de"><td>B</td></tr></table></div>'
        self.p.frags['subject'] = subsec('goal', body=para() + disclosure().replace('</div></details>', table + '</div></details>', 1)) + \
            subsec('approach') + subsec('flow')
        self.fails('subject.html: a figure or table inside a details.pt in #goal')

    def test_level_block_fails(self):
        # the report has no reading levels; a fragment of the old shape names the new one
        body = ''.join('<div data-level="%s">%s</div>\n' % (lv, twin('<p>x <code>src/a.ts:1</code></p>', '<p>x <code>src/a.ts:1</code></p>'))
                       for lv in ['plain', 'mechanics', 'detail'])
        self.p.frags['subject'] = subsec('goal', body=body) + subsec('approach') + subsec('flow')
        self.fails('subject.html: a data-level block; the report has no reading levels')

    def test_disclosure_shape_is_checked(self):
        # the summary holds the paragraph in both languages; details open one level, never nested
        self.p.frags['subject'] = subsec('goal', body=disclosure().replace('<span data-lang="de" class="ptxt">…</span>', '', 1)) + \
            subsec('approach') + subsec('flow')
        self.fails('subject.html: a details.pt summary in #goal needs the paragraph as one EN and one DE .ptxt, has en')
        nested = disclosure().replace('</div></details>', disclosure() + '</div></details>', 1)
        self.p.frags['subject'] = subsec('goal', body=nested) + subsec('approach') + subsec('flow')
        self.fails('subject.html: a details.pt in #goal holds another one')

    def test_file_line_in_visible_fragment_text_fails(self):
        self.p.frags['background'] = subsec('today', body=para('See <code>src/a.ts:11</code>.', 'Siehe <code>src/a.ts:11</code>.') + disclosure())
        self.fails('background.html: the en visible text of #today names src/a.ts:11; file:line belongs in the details')

    def test_details_cite_at_most_three_places(self):
        refs = ' '.join('<code>src/a.ts:%d</code>' % n for n in range(1, 5))
        self.p.frags['background'] = subsec('today', body=para() + disclosure(more_en='See %s.' % refs, more_de='Siehe %s.' % refs))
        self.fails('background.html: the en details of a paragraph in #today name 4 source references, at most 3')

    def test_visible_paragraph_over_the_limit_fails(self):
        n = assemble.VISIBLE_PARAGRAPH_MAX
        self.p.frags['background'] = subsec('today', body=para(' '.join(['word'] * (n + 1)), ' '.join(['Wort'] * n)) + disclosure())
        self.fails('background.html: a en visible paragraph of #today has %d words, at most %d' % (n + 1, n))

    # enums and order
    def test_capitalised_severity_fails(self):
        self.p.findings = [finding(sev='Blocker')]
        self.fails('sev')

    def test_unknown_anchor_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment(anchor='lines')])]
        self.fails('anchor')

    def test_id_gap_fails(self):
        self.p.findings = [finding('F1'), finding('F3', sev='nit')]
        self.fails('F1..F')

    def test_withdrawn_gap_after_publish(self):
        self.p.findings = [finding('F1'), finding('F3', sev='nit')]
        self.p.spec['meta']['published'] = True
        self.fails('F2 is missing')
        self.p.spec['notes']['withdrawn'] = ['F2: refuted by the author after publish']
        self.ok()

    def test_severity_order_fails(self):
        self.p.findings = [finding('F1', sev='nit'), finding('F2')]
        self.p.spec['verdict']['openBlockers'] = ['F2']
        self.fails('order')

    def test_regrade_after_publish_keeps_id_and_place(self):
        self.p.findings = [finding('F1'), finding('F2', sev='nit'), finding('F3')]
        self.p.spec['verdict']['openBlockers'] = ['F1', 'F3']
        self.p.spec['meta']['published'] = True
        self.ok()

    def test_running_check_fails(self):
        self.p.findings = [finding(check='running')]
        self.fails('running')

    # forbidden words
    def test_sentence_initial_german_forbidden_word_fails(self):
        for de in ['Bitte `x` erhöhen.', 'Wir setzen `x` zurück.', 'Du solltest `x` erhöhen.']:
            with self.subTest(de=de):
                self.p.cards = [card(self.p.findings[0], [comment(de=de)])]
                self.fails('addresses a person')

    def test_correct_text_is_not_flagged(self):
        cases = [('The loop over `i` never ends. It blocks.\n\nSuggestion: bound `i`.', '`x` setzt zurück.'),
                 ('The value, i.e. `retryCount`, resets. It loops.\n\nSuggestion: keep it.', '`x` setzt zurück.'),
                 ('The I/O call blocks the queue. It stalls.\n\nSuggestion: make it async.', '`x` setzt zurück.'),
                 ('`f` throws. It returns null.\n\nSuggestion: catch it.', 'Die Funktion `f` wirft. Sie gibt dann `null` zurück.')]
        for en, de in cases:
            with self.subTest(en=en):
                self.p.cards = [card(self.p.findings[0], [comment(en=en, de=de)])]
                self.ok()

    def test_english_I_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment(en='I think `x` resets. It loops.\n\nSuggestion: fix.')])]
        self.fails('addresses a person')

    # active content in fragments
    def test_script_in_fragment_fails(self):
        self.p.frags['good'] = twin('<p>x</p><script src="https://e.example/w.js"></script>', '<p>x</p>')
        self.fails('active content')

    def test_event_handler_in_fragment_fails(self):
        self.p.frags['good'] = twin('<img src="x" onerror="alert(1)">', '<p>x</p>')
        self.fails('active content')

    def test_javascript_in_prose_passes(self):
        self.p.frags['good'] = twin('<p><code>javascript:</code> URLs are rejected.</p>', '<p><code>javascript:</code>-URLs werden abgelehnt.</p>')
        self.ok()

    def test_javascript_word_in_plain_attributes_passes(self):
        self.p.frags['glossary'] = twin('<dl><dt><abbr title="JavaScript Object Notation">JSON</abbr></dt><dd>x</dd></dl>',
                                        '<dl><dt><abbr title="JavaScript Object Notation">JSON</abbr></dt><dd>x</dd></dl>')
        self.p.frags['good'] = twin('<p data-term="javascript-bundle">x</p>', '<p data-term="javascript-bundle">x</p>')
        self.ok()

    def test_encoded_javascript_link_fails(self):
        self.p.frags['good'] = twin('<a href="java&#115;cript:alert(1)">x</a>', '<p>x</p>')
        self.fails('active content')

    def test_style_import_fails(self):
        self.p.frags['good'] = twin('<style>@import url(https://e.example/x.css);</style><p>x</p>', '<p>x</p>')
        self.fails('active content')

    def test_escaped_or_other_css_url_functions_fail(self):
        for frag in ['<p style="background:u\\72l(https://e.example/x.png)">x</p>',
                     '<p style="background:\\75rl(//e.example/x.png)">x</p>',
                     '<p style="background:\\000075rl(https://e.example/x.png)">x</p>',
                     '<p style="background-image:image-set(\'x.png\' 1x)">x</p>',
                     '<p style="background-image:-webkit-image-set(\'x.png\' 1x)">x</p>',
                     '<p style="background:cross-fade(url(a.png), url(b.png))">x</p>',
                     '<p style="background:url(x.png)">x</p>',
                     '<style>p { background: u\\72 l(https://e.example/x.png) }</style><p>x</p>',
                     '<style>@\\69mport "x.css";</style><p>x</p>',
                     '<svg><rect fill="url(https://e.example/x.svg#g)"/></svg><p>x</p>',
                     '<svg><style>rect{fill:&#117;rl(https://e.example/x.svg#g)}</style><rect/></svg><p>x</p>',
                     '<svg><style>&#64;import "https://e.example/x.css";</style></svg><p>x</p>']:
            with self.subTest(frag=frag):
                self.p.frags['good'] = twin(frag, '<p>x</p>')
                self.fails('active content')

    def test_css_fragment_reference_and_plain_style_pass(self):
        self.p.frags['good'] = twin('<svg><path d="M0 0" style="marker-end:url(#arrow)" fill="url(#g)"/></svg><p style="color:red">x</p>'
                                    '<style>p { fill: url( "#grad" ) }</style>', '<p>x</p>')
        self.ok()

    def test_both_twins_empty_fails(self):
        self.p.frags['questions'] = twin('<p></p>', '<p></p>')
        self.fails('empty')

    def test_list_comment_for_several_places_passes(self):
        en = ('Stale names in three places:\n- `a.md:3` says `foo`.\n- `b.md:9` says `foo`.\n- `c.md:1` says `foo`.'
              '\n\nSuggestion: rename `foo` to `bar` in all three.')
        de = ('Veraltete Namen an drei Stellen:\n- `a.md:3` nennt `foo`.\n- `b.md:9` nennt `foo`.\n- `c.md:1` nennt `foo`.'
              '\n\nVorschlag: `foo` überall in `bar` umbenennen.')
        self.p.cards = [card(self.p.findings[0], [comment(en=en, de=de)])]
        self.ok()

    def test_empty_german_twin_fails(self):
        self.p.frags['questions'] = twin('<p>One open question.</p>', '')
        self.fails('empty')

    def test_german_verdict_must_match(self):
        self.p.frags['verdict'] = para('<strong>Verdict: not mergeable.</strong> F1.', '<strong>Urteil: mergebar.</strong> F1.')
        self.fails("the de lead says 'mergebar'")

    def test_comment_limit_is_the_total_not_per_sentence(self):
        first = ' '.join(['word'] * 40) + '.'
        self.p.cards = [card(self.p.findings[0], [comment(en=first + ' It loops. It blocks.\n\nSuggestion: fix `x`.')])]
        self.ok()

    def test_list_line_over_its_limit_fails(self):
        en = '`a` is stale in two places:\n- `a.md:1` ' + ' '.join(['word'] * 22) + '\n- `b.md:2` old name\n\nSuggestion: fix them.'
        self.p.cards = [card(self.p.findings[0], [comment(en=en)])]
        self.fails('words')

    def test_suggestion_block_code_is_exempt(self):
        code = '\n'.join(['    let x = 1;'] * 30)
        en = '`x` resets. The loop never ends.\n\n```suggestion\n%s\n```' % code
        de = '`x` setzt zurück. Die Schleife endet nie.\n\n```suggestion\n%s\n```' % code
        self.p.cards = [card(self.p.findings[0], [comment(en=en, de=de)])]
        self.ok()

    def test_inline_svg_passes(self):
        svg = '<figure><svg viewBox="0 0 10 10"><defs><marker id="ar-a"><path d="M0 0L5 5"/></marker></defs><line x1="0" y1="0" x2="5" y2="5" marker-end="url(#ar-a)"/></svg>%s</figure>' % twin('Cap', 'Bild', 'figcaption')
        self.p.frags['background'] = subsec('today', body=text_body()) + svg
        self.ok()

    # follow-up is copied, key included
    def test_follow_up_key_must_match(self):
        self.p.findings = [finding(), finding('F2', sev='fyi', followUp={'title': 'T', 'key': 'PROJ-1'})]
        cards = [card(self.p.findings[0], [comment()]), card(self.p.findings[1], [comment()])]
        cards[1]['followUp'] = {'title': 'T', 'key': None}
        self.p.cards = cards
        self.fails('followUp')

    # script-safe values
    def test_key_must_be_a_slug(self):
        self.p.spec['meta']['key'] = "x';alert(1);//"
        self.fails('key')

    def test_package_opens_location_line_escaped(self):
        self.p.findings[0]['package'] = 'a</SCRIPT><img src=x onerror=alert(1)>'
        self.ok()
        self.assertNotIn('a</SCRIPT>', self.p.page)
        self.assertNotIn('<img src=x', self.p.page)

    def test_unknown_category_fails(self):
        self.p.findings[0]['category'] = 'bug'
        self.fails("F1: category 'bug' is not one of")

    def test_old_area_finding_fails_without_traceback(self):
        del self.p.findings[0]['category']
        self.p.findings[0]['area'] = 'server'
        self.p.cards = [card(dict(self.p.findings[0], category='functionality'), [comment()])]
        self.fails('every finding needs an id, a sev, a category and a package')
        self.assertNotIn('Traceback', self.p.out)

    def test_category_chips_only_used_in_fixed_order(self):
        self.p.findings = [finding('F1', category='tests'), finding('F2', 'optional', category='functionality')]
        self.ok()
        chips = re.findall(r'data-filter="category" data-value="(\w+)"', self.p.page)
        self.assertEqual(chips, ['all', 'functionality', 'tests'])

    def test_package_pair_passes(self):
        self.p.findings[0]['package'] = ['Docs chapter', 'Doku-Kapitel']
        self.ok()


    # footer without a worktree
    def test_footer_without_worktree(self):
        self.p.spec['meta']['worktree'] = ''
        self.ok()
        self.assertNotIn('Worktree: <code></code>', self.p.page)

    # subsection attributes in any order
    def test_toc_finds_class_before_id(self):
        self.p.frags['background'] = subsec('today') + '<div class="subsec" id="basics-y">\n<h3>%s</h3>\n%s</div>\n' % (twin('Y', 'Y', 'span'), text_body())
        self.ok()
        self.assertIn('href="#basics-y"', self.p.page)


    # one failing case per check of data.json against findings.json
    def test_sev_category_package_file_mismatch_fails(self):
        for k, v in [('sev', 'nit'), ('category', 'documentation'), ('package', 'other'), ('file', 'src/b.ts:1')]:
            with self.subTest(k=k):
                self.p.cards = [card(self.p.findings[0], [comment()])]
                self.p.cards[0][k] = v
                self.fails('%s is %r' % (k, v))

    def test_ids_or_order_differ_fails(self):
        self.p.findings = [finding('F1'), finding('F2')]
        self.p.spec['verdict']['openBlockers'] = ['F1', 'F2']
        self.p.cards = [card(f, [comment()]) for f in reversed(self.p.findings)]
        self.fails('ids or order differ')

    def test_sources_in_data_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.p.cards[0]['sources'] = ['core']
        self.fails('carries sources or check')

    def test_follow_up_missing_in_findings_fails(self):
        self.p.findings = [finding(), finding('F2', sev='fyi')]
        del self.p.findings[1]['followUp']
        self.fails('followUp must be {title, key}')

    def test_missing_meta_key_fails(self):
        del self.p.spec['meta']['resume']
        self.fails('meta lacks resume')

    # GitLab comment rules
    def test_nit_without_comment_fails(self):
        self.p.findings = [finding(sev='nit')]
        self.p.spec['verdict'] = {'word': 'mergeable', 'openBlockers': []}
        self.p.frags['verdict'] = verdict('mergeable', 'mergebar', ids=())
        self.p.cards = [card(self.p.findings[0], [])]
        self.fails('F1: no GitLab comment')

    def test_blocker_without_comment_fails(self):
        self.p.cards = [card(self.p.findings[0], [])]
        self.fails('no GitLab comment')

    def test_invalid_side_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment(side='new')])]
        self.fails('side')

    def test_comment_text_not_a_pair_fails(self):
        c = comment()
        c['text'] = ['Only English.']
        self.p.cards = [card(self.p.findings[0], [c])]
        self.fails('is not a complete [en, de] pair')

    # verdict ids
    def test_verdict_must_name_every_open_blocker(self):
        self.p.findings = [finding('F1'), finding('F2')]
        self.p.spec['verdict']['openBlockers'] = ['F1', 'F2']
        self.p.frags['verdict'] = verdict(ids=('F2',))
        self.fails('does not name the open Blocker(s) F1')

    def test_verdict_german_omits_a_blocker_fails(self):
        self.p.frags['verdict'] = para('F1 breaks.', 'Ein Fehler.')
        self.fails('verdict.html: the de text does not name the open Blocker(s) F1')

    def test_verdict_invented_id_fails(self):
        self.p.frags['verdict'] = verdict(ids=('F1', 'F99'))
        self.fails('names F99, which is no finding')

    def test_verdict_blockers_out_of_order_fail(self):
        self.p.findings = [finding('F1'), finding('F2')]
        self.p.spec['verdict']['openBlockers'] = ['F1', 'F2']
        self.p.frags['verdict'] = verdict(ids=('F2', 'F1'))
        self.fails('out of id order')

    # fragment shape
    def test_section_in_fragment_fails(self):
        self.p.frags['background'] = '<section id="background">%s</section>' % subsec('today')
        self.fails('contains a <section>')

    def test_h2_in_background_fails(self):
        self.p.frags['background'] = '<h2>%s</h2>\n%s' % (twin('Background', 'Hintergrund', 'span'), subsec('today'))
        self.fails('background.html: 1 <h2>, needs 0')

    def test_report_labels_name_what_they_hold(self):
        self.ok()
        for en, de in [('Tests and checks', 'Tests und Prüfungen'),
                       ('Further sources', 'Weitere Quellen')]:
            self.assertIn('<span data-lang="en">%s</span><span data-lang="de">%s</span>' % (en, de), self.p.page)
        doc = ' '.join((HERE / 'report-sections.md').read_text().split())
        self.assertIn('Found by no other source / Von keiner anderen Quelle gefunden', doc)
        template = (HERE / 'review-report-template.html').read_text()
        self.assertIn('<th>Found by no other source</th>', template)
        self.assertIn('<th>Von keiner anderen Quelle gefunden</th>', template)
        for old in ['What was checked', 'Was geprüft wurde', 'inflators', 'Inflatoren', '>Reference<', '>Only here<', '>Nur hier<', 'The flow']:
            self.assertNotIn(old, self.p.page)

    def test_h2_in_subject_fails(self):
        self.p.frags['subject'] = '<h2>%s</h2>\n%s%s%s' % (twin('The MR', 'Der MR', 'span'), subsec('goal'), subsec('approach'), subsec('flow'))
        self.fails('subject.html: 1 <h2>, needs 0')

    def test_subject_heading_follows_the_subject_type(self):
        for st, en, de in [('branch', 'The branch', 'Der Branch'), ('mr', 'The MR', 'Der MR'), ('pr', 'The PR', 'Der PR'),
                           ('patch', 'The patch', 'Der Patch'), ('files', 'The code', 'Der Code'),
                           ('document', 'The document', 'Das Dokument')]:
            with self.subTest(st=st):
                self.p.spec['meta']['subjectType'] = st
                self.p.spec['gitlab'] = st in ('branch', 'mr', 'pr')
                word = {'branch': 'not mergeable', 'mr': 'not mergeable', 'pr': 'not mergeable', 'patch': 'not applicable',
                        'files': 'not yet', 'document': 'needs revision'}[st]
                self.p.spec['verdict'] = dict(self.p.spec['verdict'], word=word)
                self.p.frags['verdict'] = verdict(word, assemble.VERDICTS_DE[word], ids=tuple(self.p.spec['verdict']['openBlockers']))
                self.ok()
                self.assertIn('<section id="subject">', self.p.page)
                head = self.p.page.split('<section id="subject">', 1)[1].split('</h2>', 1)[0]
                self.assertIn('<span data-lang="en">%s</span><span data-lang="de">%s</span>' % (en, de), head)

    def test_duplicate_id_fails(self):
        self.p.frags['background'] = subsec('today') + subsec('goal')
        self.fails('id "goal" occurs more than once')

    def test_untagged_prose_fails(self):
        self.p.frags['questions'] = '<p>No open questions.</p>'
        self.fails('text outside a language block')

    def test_diagram_and_code_text_need_no_language(self):
        svg = '<figure><svg viewBox="0 0 10 10"><text x="1" y="5">db-sync</text></svg>%s</figure>' % twin('Cap', 'Bild', 'figcaption')
        self.p.frags['background'] = subsec('today') + svg + '<p><code>npm run x</code></p>'
        self.ok()

    def test_detail_without_citation_fails(self):
        self.p.frags['background'] = subsec('today', body=para() + disclosure(more_en='From memory.', more_de='Aus dem Gedächtnis.'))
        self.fails('#today cites no source in the en view')

    def test_german_detail_without_citation_fails(self):
        self.p.frags['background'] = subsec('today', body=para() + disclosure(more_en='See <code>src/a.ts:11</code>.', more_de='Siehe den Code.'))
        self.fails('#today cites no source in the de view')

    def test_neutral_citation_counts_for_both_languages(self):
        neutral = disclosure(more_en='Steps.', more_de='Schritte.').replace('<div class="more-body">', '<div class="more-body"><p><code>src/a.ts:11</code></p>', 1)
        self.p.frags['background'] = subsec('today', body=para() + neutral)
        self.ok()

    def test_extensionless_file_line_is_a_citation(self):
        self.p.frags['background'] = subsec('today', body=para() + disclosure(more_en='<code>Dockerfile:3</code>', more_de='<code>Dockerfile:3</code>'))
        self.ok()

    def test_host_and_port_is_no_citation(self):
        for text in ['<code>redis:6379</code>', 'localhost:8080', '<code>api.example.com:443</code>']:
            with self.subTest(text=text):
                self.p.frags['background'] = subsec('today', body=para() + disclosure(more_en='Connects to %s.' % text,
                                                                                         more_de='Verbindet mit %s.' % text))
                self.fails('#today cites no source in the en view')

    def test_repository_paths_are_citations(self):
        for ref in ['docker/server.Dockerfile:4', '.gitlab-ci.yml:2', 'ci/jenkins/src/debounce.groovy:5',
                    'shared/client/generate.mts:3', 'Dockerfile:3', 'SKILL.md:12']:
            with self.subTest(ref=ref):
                self.assertTrue(assemble.FILE_LINE.search('see %s.' % ref))
        for ref in ['redis:6379', 'api.example.com:443', 'https://example.com/a.ts:1']:
            with self.subTest(ref=ref):
                self.assertFalse(assemble.FILE_LINE.search('see %s.' % ref))

    def test_mr_url_only_for_an_mr(self):
        for st in ['branch', 'pr']:
            with self.subTest(st=st):
                self.p.spec['meta']['subjectType'] = st
                self.p.spec['mrUrl'] = 'https://gitlab.example/g/p/-/merge_requests/1'
                self.fails('mrUrl belongs to a GitLab MR')

    def test_checks_follow_severity_and_depth(self):
        # (depth, sev, category, weakest allowed check)
        cases = [('low', 'blocker', 'functionality', 'investigator'), ('low', 'optional', 'functionality', 'batch'),
                 ('low', 'fyi', 'functionality', 'batch'), ('low', 'nit', 'functionality', 'batch'),
                 ('low', 'nit', 'style', 'inline'), ('medium', 'blocker', 'functionality', 'investigator'),
                 ('medium', 'optional', 'functionality', 'investigator'), ('medium', 'fyi', 'functionality', 'investigator'),
                 ('medium', 'nit', 'functionality', 'batch'), ('medium', 'nit', 'documentation', 'inline'),
                 ('high', 'nit', 'style', 'investigator'), ('high', 'optional', 'functionality', 'investigator')]
        strengths = ['inline', 'batch', 'investigator', 'investigator2']
        for depth, sev, cat, need in cases:
            for check in strengths + ['unchecked']:
                with self.subTest(depth=depth, sev=sev, cat=cat, check=check):
                    self.tearDown()
                    self.setUp()
                    self.p.spec['meta']['depth'] = depth
                    self.p.findings = [finding(sev=sev, category=cat, check=check)]
                    if sev != 'blocker':
                        self.p.spec['verdict'] = {'word': 'mergeable', 'openBlockers': []}
                        self.p.frags['verdict'] = verdict('mergeable', 'mergebar', ids=())
                    if check == 'unchecked' or strengths.index(check) >= strengths.index(need):
                        self.ok()
                    else:
                        what = 'nit in %s' % cat if sev == 'nit' else sev
                        self.fails("F1: a %s at %s needs check %s or stronger, or unchecked, not '%s'" % (what, depth, need, check))

    def test_finding_without_check_key_fails_without_traceback(self):
        self.p.findings = [finding()]
        del self.p.findings[0]['check']
        self.fails("F1: check is None in findings.json")
        self.assertNotIn('Traceback', self.p.out)

    def test_unchecked_is_a_final_check_value(self):
        self.p.findings = [finding(check='unchecked')]
        self.ok()
        self.p.findings = [finding(check='failed')]
        self.fails("check is 'failed' in findings.json (must be inline, batch, investigator, investigator2, unchecked)")

    def test_void_element_twins_need_no_text(self):
        self.p.frags['good'] = twin('<p>Good.</p>', '<p>Gut.</p>') + '<img data-lang="en" alt="" src="#a"><img data-lang="de" alt="" src="#b">'
        self.ok()

    def test_data_payload_has_one_finding_per_line(self):
        self.p.findings = [finding('F1'), finding('F2')]
        self.p.spec['verdict'] = {'word': 'not mergeable', 'openBlockers': ['F1', 'F2']}
        self.ok()
        payload = self.p.page.split('var findings = ', 1)[1].split(';\n', 1)[0]
        self.assertEqual(payload.count('\n'), 3)
        self.assertEqual([f['id'] for f in json.loads(payload)], ['F1', 'F2'])

    def test_single_quoted_duplicate_id_fails(self):
        self.p.frags['good'] = twin("<p id='goal'>x</p>", '<p>x</p>')
        self.fails('id "goal" occurs more than once')

    def test_detail_with_cite_passes(self):
        self.p.frags['background'] = subsec('today', body=para() + disclosure(more_en='See <cite>RFC 3339</cite>.', more_de='Siehe <cite>RFC 3339</cite>.'))
        self.ok()

    def test_fragment_quoting_a_slot_marker_survives(self):
        self.p.frags['good'] = twin('<p>The marker <code>/* slot:data */</code> and <code>&lt;!-- slot:good --&gt;</code>.</p>',
                                    '<p>Der Marker <code>/* slot:data */</code> und <code>&lt;!-- slot:good --&gt;</code>.</p>')
        self.ok()
        self.assertIn('<code>/* slot:data */</code>', self.p.page)

    def test_quoted_markup_is_no_language_block_or_id(self):
        # quoted in a code sample or an attribute value, markup is text: it counts as no block and no id
        self.p.frags['good'] = twin('<p>Each block is <code>&lt;div data-lang="en" id="goal"&gt;</code>.</p>',
                                    '<p>Jeder Block ist <code>&lt;div data-lang="en" id="goal"&gt;</code>.</p>')
        self.p.frags['glossary'] = twin('<dl><dt title=\'data-lang="en" id="today"\'>A</dt><dd>B</dd></dl>', '<dl><dt>A</dt><dd>B</dd></dl>')
        self.ok()

    def test_untranslated_twin_fails(self):
        self.p.frags['questions'] = twin('<p>No open questions remain.</p>', '<p>No open questions remain.</p>')
        self.fails('questions.html: the German twin of an English <div> is the English text')

    def test_identical_twin_of_code_and_names_passes(self):
        for en in ['GitLab CI <code>npm run test --watch</code> src/a.ts:12', 'Keycloak Token Exchange', 'Docker Compose Nginx Redis']:
            with self.subTest(en=en):
                self.p.frags['questions'] = twin('<p>%s</p>' % en, '<p>%s</p>' % en)
                self.ok()

    def test_untranslated_card_field_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.p.cards[0]['fields']['why']['text'] = ['The loop never ends.', 'The loop never ends.']
        self.fails('F1: the German fields.why.text is the English text')
        self.p.cards[0]['fields']['why']['text'] = ['Card why.', 'Karte why.']
        self.p.cards[0]['fields']['fix']['more'] = ['Increment the counter once.', 'Increment the counter once.']
        self.fails('F1: the German fields.fix.more is the English text')
        self.p.cards[0]['fields']['fix']['more'] = None
        self.p.cards[0]['gitlab'] = [comment(de=comment()['text'][0])]
        self.fails('F1: the German GitLab text at src/a.ts:11 is the English text')

    def test_inline_scripts_must_parse(self):
        bad = Path(self.p.sp, 'template.html')
        bad.write_text(assemble.TEMPLATE.read_text().replace('var state = {', 'var state = {{', 1))
        self.p.run()  # writes the report directory
        out = subprocess.run([sys.executable, '-c', 'import sys, assemble; from pathlib import Path; '
                              'assemble.TEMPLATE = Path(sys.argv[1]); sys.argv = ["assemble.py", sys.argv[2]]; sys.exit(assemble.main())',
                              str(bad), str(self.p.dir)], capture_output=True, text=True, cwd=str(HERE))
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn('inline scripts do not parse', out.stdout)

    def test_data_json_not_an_array_fails(self):
        self.p.data = '{"id": "F1"}'
        self.fails('data.json must be an array')

    def test_missing_data_json_fails(self):
        self.p.run()
        (self.p.dir / 'data.json').unlink()
        out = subprocess.run([sys.executable, str(HERE / 'assemble.py'), str(self.p.dir)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn('missing data.json', out.stdout)

    def test_missing_fragment_fails(self):
        self.p.run()
        (self.p.dir / 'good.html').unlink()
        out = subprocess.run([sys.executable, str(HERE / 'assemble.py'), str(self.p.dir)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn('missing fragment good.html', out.stdout)

    def test_ids_must_increase_after_publish(self):
        self.p.findings = [finding('F2'), finding('F1')]
        self.p.spec['verdict']['openBlockers'] = ['F2', 'F1']
        self.p.spec['meta']['published'] = True
        self.fails('increasing in list order')

    def with_template(self, change):
        bad = Path(self.p.sp, 'template.html')
        bad.write_text(change(assemble.TEMPLATE.read_text()))
        self.p.run()
        out = subprocess.run([sys.executable, '-c', 'import sys, assemble; from pathlib import Path; '
                              'assemble.TEMPLATE = Path(sys.argv[1]); sys.argv = ["assemble.py", sys.argv[2]]; sys.exit(assemble.main())',
                              str(bad), str(self.p.dir)], capture_output=True, text=True, cwd=str(HERE))
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        return out.stdout

    def test_unfilled_placeholder_fails(self):
        self.assertIn('placeholder left unfilled: {{nobody}}', self.with_template(lambda t: t.replace('</footer>', '{{nobody}}</footer>', 1)))

    def test_slot_twice_in_template_fails(self):
        self.assertIn('slot good found 2 times', self.with_template(
            lambda t: t.replace('</footer>', '<!-- slot:good --><!-- /slot:good --></footer>', 1)))

    def test_unknown_modes_print_usage(self):
        # --scan and --mask are gone with the masking: secrets live in the secret files, which never reach a review;
        # --check-page moved to qubit-explanation-page/page_check.py
        for mode in ['--scan', '--mask', '--check-page', '--unknown']:
            out = subprocess.run([sys.executable, str(HERE / 'assemble.py'), mode], capture_output=True, text=True)
            self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
            self.assertIn('Usage', out.stdout)

    # active content: what the browser runs, not what a lenient parse sees
    def test_duplicate_attribute_fails(self):
        for frag in ['<a href="javascript:alert(1)" href="#goal">x</a>', '<p class="a" class="b">x</p>']:
            with self.subTest(frag=frag):
                self.p.frags['good'] = twin(frag, '<p>x</p>')
                self.fails('duplicate attribute')

    def test_svg_animation_fails(self):
        for tag in ['set', 'animate', 'animateMotion', 'animateTransform']:
            with self.subTest(tag=tag):
                self.p.frags['good'] = twin('<svg><%s attributeName="href" to="javascript:alert(1)"/></svg><p>x</p>' % tag, '<p>x</p>')
                self.fails('active content')

    def test_external_resource_fails(self):
        for frag in ['<svg><image href="https://e.example/x.png"/></svg>', '<svg><use xlink:href="https://e.example/s.svg#a"/></svg>',
                     '<svg><use href="//e.example/s.svg#a"/></svg>', '<video poster="https://e.example/p.png"></video>',
                     '<table><tr><td background="https://e.example/b.png">x</td></tr></table>',
                     '<img srcset="a.png 1x, https://e.example/b.png 2x">', '<div data="https://e.example/x">x</div>']:
            with self.subTest(frag=frag):
                self.p.frags['good'] = twin(frag + '<p>x</p>', '<p>x</p>')
                self.fails('active content')

    def test_link_to_an_outside_page_passes(self):
        self.p.frags['good'] = twin('<p><a href="https://example.org/doc">doc</a></p>', '<p><a href="https://example.org/doc">Doku</a></p>')
        self.ok()

    def test_attribute_without_value_does_not_crash(self):
        self.p.frags['good'] = twin('<p class>x</p>', '<p class>x</p>')
        self.ok()
        assemble.check_structure('background', assemble.parse_html('<div id="today" class><p>x</p></div>'))

    # the TOC lists exactly the subsections the CSS counter numbers
    def test_subsec_without_id_fails(self):
        self.p.frags['background'] = subsec('today') + '<div class="subsec">\n<h3>%s</h3>\n%s</div>\n' % (twin('Y', 'Y', 'span'), text_body())
        self.fails('a .subsec without an id')

    def test_subsec_not_led_by_h3_fails(self):
        self.p.frags['background'] = subsec('today') + '<div id="basics-y" class="subsec">%s<h3>%s</h3>\n%s</div>\n' % (
            twin('<p>Intro.</p>', '<p>Einleitung.</p>'), twin('Y', 'Y', 'span'), text_body())
        self.fails('#basics-y does not start with its <h3>')

    def test_toc_lists_h3_with_attributes_after_a_comment(self):
        self.p.frags['background'] = subsec('today') + '<div id="basics-y" class="subsec">\n<!-- note -->\n<h3 id="h-y">%s</h3>\n%s</div>\n' % (
            twin('Y', 'Y', 'span'), text_body())
        self.ok()
        self.assertIn('href="#basics-y"', self.p.page)

    def test_file_anchor_outside_the_diff_fails(self):
        self.p.cards = [card(self.p.findings[0], [comment(path='src/other.ts', startLine=None, anchor='file')])]
        self.fails('file anchor src/other.ts is not in the diff')

    def test_file_anchor_on_a_file_without_hunks_passes(self):
        rename = 'diff --git a/old.ts b/new.ts\nsimilarity index 100%\nrename from old.ts\nrename to new.ts\n'
        binary = 'diff --git a/img.png b/img.png\nindex 1..2 100644\nBinary files a/img.png and b/img.png differ\n'
        mode = 'diff --git a/run.sh b/run.sh\nold mode 100644\nnew mode 100755\n'
        quoted = 'diff --git "a/\\303\\244 b.png" "b/\\303\\244 b.png"\nBinary files differ\n'
        copy = 'diff --git a/src.ts b/dst.ts\nsimilarity index 100%\ncopy from src.ts\ncopy to dst.ts\n'
        spaced = ('diff --git a/x b/y.bin b/x b/y.bin\nBinary files a/x b/y.bin and b/x b/y.bin differ\n'
                  'diff --git a/m b/n.sh b/m b/n.sh\nold mode 100644\nnew mode 100755\n')
        for diff, at in [(rename, 'new.ts'), (copy, 'dst.ts'), (binary, 'img.png'), (mode, 'run.sh'),
                         (DIFF + binary + mode, 'run.sh'), (DIFF + quoted, 'ä b.png'), (spaced, 'x b/y.bin'), (spaced, 'm b/n.sh')]:
            with self.subTest(diff=diff[:40], at=at):
                (self.p.sp / 'inputs' / 'change.diff').write_text(diff)
                self.p.cards = [card(self.p.findings[0], [comment(path=at, startLine=None, anchor='file')])]
                self.ok()
        # the old side of a rename and a copy source are no changed files of the subject
        for diff, at in [(rename + binary + mode, 'other.ts'), (DIFF + binary, 'other.ts'), (rename, 'old.ts'), (copy, 'src.ts'),
                         (spaced, 'x'), (spaced, 'm')]:
            with self.subTest(diff=diff[:40], at=at):
                (self.p.sp / 'inputs' / 'change.diff').write_text(diff)
                self.p.cards = [card(self.p.findings[0], [comment(path=at, startLine=None, anchor='file')])]
                self.fails('file anchor %s is not in the diff' % at)
        (self.p.sp / 'inputs' / 'change.diff').write_text(DIFF + binary)
        self.p.cards = [card(self.p.findings[0], [comment(path='img.png', startLine=3)])]
        self.fails('outside the diff hunks')

    def test_missing_node_is_one_failure_line(self):
        self.ok()
        with tempfile.TemporaryDirectory() as empty:
            out = subprocess.run([sys.executable, str(HERE / 'assemble.py'), str(self.p.dir)], capture_output=True, text=True,
                                 env={'PATH': empty})
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn('- node not found: inline scripts not checked', out.stdout)
        self.assertNotIn('Traceback', out.stdout + out.stderr)

    def test_toc_lists_every_subsection_once(self):
        self.p.frags['background'] = (subsec('today') + "<div id='basics.y' class='subsec'>\n<h3>%s</h3>\n%s</div>\n" % (twin('Y', 'Y', 'span'), text_body())
                                      + '<div class = "subsec" id = "basics-w">\n<h3>%s</h3>\n%s</div>\n' % (twin('W', 'W', 'span'), text_body()))
        self.ok()
        toc = self.p.page[self.p.page.index('<nav class="toc"'):self.p.page.index('</nav>')]
        self.assertEqual(re.findall(r'href="#([^"]+)"', toc),
                         ['overview', 'background', 'today', 'basics.y', 'basics-w', 'subject', 'goal', 'approach', 'flow', 'assessment', 'manual', 'findings',
                          'questions', 'good', 'gitlab', 'evidence', 'checks', 'method', 'glossary'])
        self.assertIn('<a href="#basics.y"><span data-lang="en">Y</span>', toc)

    def test_more_forbidden_words_fail(self):
        for en in ['Your change resets `x`. It loops.\n\nSuggestion: fix `x`.', 'Our check misses `x`. It loops.\n\nSuggestion: fix `x`.',
                   'This breaks `x` for us. It loops.\n\nSuggestion: fix `x`.', "Let's bound `x`. It loops.\n\nSuggestion: fix `x`.",
                   'The fix is yours. It loops.\n\nSuggestion: fix `x`.']:
            with self.subTest(en=en):
                self.p.cards = [card(self.p.findings[0], [comment(en=en)])]
                self.fails('addresses a person')
        for de in ['Der Wert in Ihrem Formular fehlt.', 'Das zeigt Ihnen den Fehler.', 'Ihnen fehlt der Wert.',
                   'Das ändert Ihre Daten.', 'Deine Prüfung fehlt.', 'Das betrifft unsere Daten.',
                   'Dein Code setzt `x` zurück.', 'Das betrifft dich.', 'Das gilt für euch.', 'Eure Prüfung fehlt.',
                   'Unser Test fehlt.', 'Das hilft uns nicht.', 'Das zeigt dir den Fehler.']:
            with self.subTest(de=de):
                self.p.cards = [card(self.p.findings[0], [comment(de=de)])]
                self.fails('addresses a person')

    def test_ordinary_words_near_forbidden_ones_pass(self):
        cases = [('The US region times out. The user waits.\n\nSuggestion: retry `x`.', 'Die Funktion `f` liefert ihr Ergebnis zu spät.'),
                 ('The status stays open. It loops.\n\nSuggestion: close it.', 'Der Euro-Betrag wird gerundet. Die Summe stimmt nicht.'),
                 ('`f` throws. It returns null.\n\nSuggestion: catch it.', 'Sie gibt `null` zurück. Die Liste bleibt leer.'),
                 ('Requests to the us-east-1 region time out. They fail.\n\nSuggestion: retry `x`.', 'Die Deinstallation entfernt den Dienst nicht.'),
                 ('The us2 shard stays stale. It drifts.\n\nSuggestion: resync `x`.', 'Der Dienst wird deinitialisiert. Er bleibt stehen.'),
                 ('`f` throws. It returns null.\n\nSuggestion: catch it.', 'Das Objekt ist unserialisierbar.'),
                 ('`f` throws. It returns null.\n\nSuggestion: catch it.', 'Die Funktion endet. Ihr Rückgabewert fehlt.'),
                 ('`f` throws. It returns null.\n\nSuggestion: catch it.', 'Ihre Länge wird nicht geprüft.')]
        for en, de in cases:
            with self.subTest(en=en):
                self.p.cards = [card(self.p.findings[0], [comment(en=en, de=de)])]
                self.ok()

    def test_reserved_ids_fail(self):
        base = dict(self.p.frags)
        for name, frag in [('background', subsec('today') + subsec('F1')), ('good', twin('<p id="glc-F1">x</p>', '<p>x</p>'))]:
            with self.subTest(frag=frag[:40]):
                self.p.frags = dict(base, **{name: frag})
                self.fails('reserved for the cards and the GitLab list')

    def test_template_and_skeleton_declare_utf8_first(self):
        for path in [assemble.TEMPLATE, HERE.parent / 'qubit-explanation-page' / 'page-skeleton.html']:
            with self.subTest(path=path.name):
                self.assertTrue(path.read_text().startswith('<meta charset="utf-8">\n<title>'))

    def test_missing_findings_json_fails_without_traceback(self):
        self.p.run()
        (self.p.dir / 'findings.json').unlink()
        out = subprocess.run([sys.executable, str(HERE / 'assemble.py'), str(self.p.dir)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn('missing findings.json', out.stdout)
        self.assertNotIn('Traceback', out.stdout + out.stderr)

    def test_malformed_findings_json_fails_without_echo(self):
        self.p.run()
        (self.p.dir / 'findings.json').write_text('{"meta": {"pw": "Xk9fakevalue123" oops}')
        out = subprocess.run([sys.executable, str(HERE / 'assemble.py'), str(self.p.dir)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn('findings.json is not valid JSON at line 1', out.stdout)
        self.assertNotIn('Traceback', out.stdout + out.stderr)
        self.assertNotIn('Xk9fakevalue123', out.stdout + out.stderr)

    def test_finding_without_id_sev_category_or_package_fails_without_traceback(self):
        for k in ['id', 'sev', 'category', 'package']:
            with self.subTest(k=k):
                self.p.findings = [finding()]
                self.p.cards = [card(self.p.findings[0], [comment()])]
                del self.p.findings[0][k]
                self.fails('finding 1 in findings.json lacks %s' % k)
                self.assertNotIn('Traceback', self.p.out)

    def test_mr_url_must_be_https(self):
        self.p.spec['meta']['subjectType'] = 'mr'
        for url in ['javascript:alert(1)', 'http://gitlab.example/g/p/-/merge_requests/1', 'gitlab.example/mr/1']:
            with self.subTest(url=url):
                self.p.spec['mrUrl'] = url
                self.fails('mrUrl must start with https://')
        self.p.spec['mrUrl'] = 'https://gitlab.example/g/p/-/merge_requests/1'
        self.ok()

    # the MR's head at publish time
    def test_moved_head_shows_both_shas_in_the_state_row(self):
        self.p.spec['meta'].update(state='abc1234def', headAtPublish='0f9e8d7c6b')
        self.ok()
        m = re.search(r'<dd>abc1234def(.*?)</dd>', self.p.page, re.S)
        self.assertIsNotNone(m, 'state row missing')
        self.assertIn('class="moved"', m.group(1))
        self.assertIn('0f9e8d7c6b', m.group(1))
        self.assertIn('data-lang="de"', m.group(1))

    def test_unmoved_or_unknown_head_shows_no_note(self):
        for head in ['abc1234def0123', 'abc1234', None]:
            with self.subTest(head=head):
                self.p.spec['meta']['state'] = 'abc1234def'
                self.p.spec['meta'].pop('headAtPublish', None)
                if head:
                    self.p.spec['meta']['headAtPublish'] = head
                self.ok()
                self.assertNotIn('class="moved"', self.p.page)

    def test_head_at_publish_needs_shas_on_both_sides(self):
        for state, head, text in [('abc1234def', 'main', 'meta.headAtPublish must be a commit sha'),
                                  ('local files', 'abc1234def', 'meta.headAtPublish needs the reviewed sha in meta.state')]:
            with self.subTest(head=head):
                self.p.spec['meta'].update(state=state, headAtPublish=head)
                self.fails(text)

    # the effort line above the sources table in 4.2
    EFFORT = {'review': {'started': '2026-10-21T17:22:11Z', 'ended': '2026-10-21T17:51:46Z',
                         'runs': {'reviewers': {'Claude': 7, 'Codex': 2, 'Gemini': 2}, 'investigators': {'Claude': 15}}},
              'report': {'started': '2026-10-21T17:51:50Z', 'ended': '2026-10-21T19:09:28Z', 'runs': {'writers': {'Claude': 3}}}}

    def effort_text(self):
        m = re.search(r'<p class="effort">(.*?)</p>', self.p.page, re.S)
        self.assertIsNotNone(m, 'effort line missing')
        return m.group(1)

    def test_effort_line_shows_both_phases_in_both_languages(self):
        self.p.spec['meta']['effort'] = json.loads(json.dumps(self.EFFORT))
        self.ok()
        line = self.effort_text()
        self.assertIn('<span data-lang="en">Review, 30 min: 11 reviewers (7 Claude, 2 Codex, 2 Gemini) and 15 investigators '
                      '(Claude).<br>Report, 1 h 18 min: 3 writers (Claude).</span>', line)
        self.assertIn('<span data-lang="de">Review, 30 Min.: 11 Reviewer (7 Claude, 2 Codex, 2 Gemini) und 15 Prüfer '
                      '(Claude).<br>Bericht, 1 Std. 18 Min.: 3 Schreiber (Claude).</span>', line)

    def test_effort_roles_follow_the_fixed_order(self):
        effort = json.loads(json.dumps(self.EFFORT))
        effort['review']['runs'] = {'investigators': {'Claude': 9}, 'raters': {'Codex': 1}, 'reviewers': {'Claude': 8}}
        self.p.spec['meta']['effort'] = effort
        self.ok()
        self.assertIn('Review, 30 min: 8 reviewers (Claude), 1 severity rater (Codex) and 9 investigators (Claude).',
                      self.effort_text())

    def test_run_without_effort_has_no_line_and_a_note(self):
        self.ok()
        self.assertNotIn('class="effort"', self.p.page)
        self.assertNotIn('{{effortLine}}', self.p.page)
        self.assertIn('meta.effort missing', self.p.out)

    def test_method_names_codex_and_gemini_never_foreign(self):
        for en, de in [('Two foreign runs.', 'Zwei Läufe.'), ('Two runs.', 'Zwei Fremdläufe.')]:
            with self.subTest(en=en):
                self.p.frags['method'] = twin('<p>%s</p>' % en, '<p>%s</p>' % de)
                self.fails('method.html says "foreign"')
        self.p.frags['method'] = twin('<p>Extra runs by Codex and Gemini.</p>', '<p>Zusatzläufe von Codex und Gemini.</p>')
        self.ok()

    def test_broken_effort_fails(self):
        cases = [(lambda e: e.pop('report'), 'meta.effort.report missing'),
                 (lambda e: e['review'].update(started='2026-10-21T17:22:11'), 'ISO 8601 times with a time zone'),
                 (lambda e: e['review'].update(ended='2026-10-21T17:00:00Z'), 'meta.effort.review ends before it starts'),
                 (lambda e: e['report'].update(runs={}), 'meta.effort.report.runs must map'),
                 (lambda e: e['report'].update(runs={'writers': {'Claude': True}}), 'meta.effort.report.runs must map'),
                 (lambda e: e['report'].update(runs={'Claude': 3}), 'meta.effort.report.runs must map'),
                 (lambda e: e['report'].update(runs={'writers': {}}), 'meta.effort.report.runs must map')]
        for change, text in cases:
            with self.subTest(text=text):
                effort = json.loads(json.dumps(self.EFFORT))
                change(effort)
                self.p.spec['meta']['effort'] = effort
                self.fails(text)

    def test_findings_json_without_findings_array_fails(self):
        self.p.run()
        (self.p.dir / 'findings.json').write_text('{"meta": {}}')
        out = subprocess.run([sys.executable, str(HERE / 'assemble.py'), str(self.p.dir)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn('findings.json must be an object with a findings array', out.stdout)

    # subject type: fixed template wording follows it
    def test_default_subject_type_is_branch(self):
        self.ok()
        self.assertIn('A change in this branch', self.p.page)
        self.assertIn('holds the merge', self.p.page)

    def test_document_subject_wording_and_no_gitlab_line(self):
        self.p.findings = [finding(sev='nit')]
        self.p.spec['meta']['subjectType'] = 'document'
        self.p.spec['gitlab'] = False
        self.p.spec['verdict'] = {'word': 'accepted', 'openBlockers': []}
        self.p.frags['verdict'] = verdict('accepted', 'angenommen', ids=())
        self.ok()
        self.assertIn('A change in this document', self.p.page)
        self.assertNotIn('A change in this MR', self.p.page)
        self.assertNotIn('holds the merge', self.p.page)
        self.assertIn('No GitLab comments for this subject type.', self.p.page)
        self.assertIn('Keine GitLab-Kommentare für diese Art von Gegenstand.', self.p.page)
        self.assertNotIn('No comment matches this selection.', self.p.page)

    def test_pr_subject_type(self):
        self.p.spec['meta']['subjectType'] = 'pr'
        self.ok()
        self.assertIn('A change in this PR', self.p.page)
        self.assertIn('Eine Änderung in diesem PR', self.p.page)
        self.assertIn('holds the merge', self.p.page)

    def test_unknown_subject_type_fails(self):
        self.p.spec['meta']['subjectType'] = 'pull request'
        self.fails("meta.subjectType 'pull request' is not one of")

    def test_verdict_word_must_fit_the_subject_type(self):
        self.p.spec['meta']['subjectType'] = 'patch'
        self.fails("verdict 'not mergeable' does not fit subjectType 'patch'")

    # untested paths
    def test_unknown_or_missing_verdict_word_fails(self):
        self.p.spec['verdict']['word'] = 'maybe'
        self.fails("verdict word 'maybe' is not one of")
        del self.p.spec['verdict']['word']
        self.fails("verdict word '' is not one of")

    def test_card_fields_must_be_pairs(self):
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.p.cards[0]['t'] = ['Only English.']
        self.fails('F1: t is not a complete [en, de] pair')
        for k in CARD_FIELDS:
            with self.subTest(k=k):
                self.p.cards = [card(self.p.findings[0], [comment()])]
                self.p.cards[0]['fields'][k]['text'] = ['Only English.']
                self.fails('F1: fields.%s.text is not a complete [en, de] pair' % k)

    def test_data_slot_twice_in_template_fails(self):
        self.assertIn('data slot found 2 times', self.with_template(lambda t: t.replace('/* /slot:data */', '/* /slot:data */\n/* slot:data */ /* /slot:data */', 1)))

    def test_pending_check_fails(self):
        self.p.findings = [finding(check='pending')]
        self.fails("check is 'pending'")


def triggers(n):
    return [{'trigger': 'Case %d.' % i, 'wrong': 'Wrong result %d.' % i} for i in range(1, n + 1)]


def trigger_what(n, lead='The counter is a difference of events.', item='Case %d goes wrong.'):
    return lead + '\n\n' + '\n'.join('- ' + item % i for i in range(1, n + 1))


def trigger_comment(n_en, n_de=None, item_en='The server is down and the loop never ends.'):
    n_de = n_en if n_de is None else n_de
    en = '`x` resets the counter in several cases:\n\n' + '\n'.join('- ' + item_en for _ in range(n_en)) + '\n\nSuggestion: increment `x`.'
    de = ('`x` setzt den Zähler in mehreren Fällen zurück:\n\n' + '\n'.join('- Der Server ist weg und die Schleife endet nie.' for _ in range(n_de))
          + '\n\nVorschlag: `x` erhöhen.')
    return comment(en=en, de=de)


class TriggersTest(unittest.TestCase):
    """A finding merged from several triggers lists them in the card and in its GitLab comment."""

    def setUp(self):
        self.p = Report()

    def tearDown(self):
        self.p.tmp.cleanup()

    def build(self, n=2, lists=None, gitlab=None, f=None):
        f = f or finding(triggers=triggers(n))
        c = card(f, gitlab or [trigger_comment(min(n, 3))])
        en_n, de_n = lists if lists is not None else (n, n)
        c['fields']['what']['text'] = [trigger_what(en_n), trigger_what(de_n, 'Der Zähler ist eine Differenz von Ereignissen.', 'Fall %d geht schief.')]
        self.p.findings, self.p.cards = [f], [c]

    def run_ok(self):
        rc = self.p.run()
        self.assertEqual(rc, 0, self.p.out)

    def run_fails(self, text):
        rc = self.p.run()
        self.assertEqual(rc, 1, self.p.out)
        self.assertIn(text, self.p.out)

    def test_listed_triggers_pass(self):
        self.build()
        self.run_ok()

    def test_comment_lists_at_most_three(self):
        self.build(n=4)
        self.run_ok()

    def test_one_trigger_fails(self):
        self.build(f=finding(triggers=triggers(1)))
        self.run_fails('must list at least two {"trigger", "wrong"} objects')

    def test_empty_wrong_fails(self):
        t = triggers(2)
        t[1]['wrong'] = ' '
        self.build(f=finding(triggers=t))
        self.run_fails('must list at least two {"trigger", "wrong"} objects')

    def test_what_without_list_fails(self):
        self.build(lists=(0, 2))
        self.run_fails('fields.what.text (English) lists 0 of 2 triggers')

    def test_german_short_list_fails(self):
        self.build(lists=(2, 1))
        self.run_fails('fields.what.text (German) lists 1 of 2 triggers')

    def test_list_inside_a_paragraph_is_no_list(self):
        # the renderer makes a list only of a paragraph whose every line starts with "- "
        self.build()
        self.p.cards[0]['fields']['what']['text'][0] = 'The counter is a difference of events:\n- Case 1 goes wrong.\n- Case 2 goes wrong.'
        self.run_fails('fields.what.text (English) lists 0 of 2 triggers')

    def test_comment_with_too_few_lines_fails(self):
        self.build(gitlab=[trigger_comment(1)])
        self.run_fails('English GitLab text at src/a.ts:11 has 1 "- " lines; a finding with 2 triggers lists 2')

    def test_german_comment_with_too_many_lines_fails(self):
        self.build(n=3, gitlab=[trigger_comment(3, 4)])
        self.run_fails('German GitLab text at src/a.ts:11 has 4 "- " lines; a finding with 3 triggers lists 3')

    def test_trigger_lines_count_towards_the_word_limit(self):
        self.build(n=3, gitlab=[trigger_comment(3, item_en=' '.join(['word'] * 31) + '.')])
        self.run_fails('English GitLab text at src/a.ts:11 is over the word limit (100 words, the trigger lines included)')

    def test_place_list_lines_stay_outside_the_limit(self):
        # without triggers, a list of places keeps its rule: each line up to 20 words, outside the total
        item = ' '.join(['word'] * 19) + '.'
        en = '`x` is stale in four places:\n\n' + '\n'.join('- `a%d`: %s' % (i, item) for i in range(4)) + '\n\nSuggestion: update them.'
        de = '`x` ist an vier Stellen veraltet:\n\n' + '\n'.join('- `a%d`: %s' % (i, item) for i in range(4)) + '\n\nVorschlag: aktualisieren.'
        f = finding()
        self.p.findings, self.p.cards = [f], [card(f, [comment(en=en, de=de)])]
        self.run_ok()


def options_comment(en_q='Question: should `x` get a new name, which fixes both cases, or is the effect accepted?',
                    de_q='Frage: Soll `x` einen neuen Namen bekommen, was beide Fälle behebt, oder gilt der Effekt als akzeptiert?'):
    en = '`x` reads every stored value as a pick. A session that spans the deploy shows the old value.\n\n' + en_q
    de = '`x` liest jeden gespeicherten Wert als Auswahl. Eine Sitzung über das Deployment zeigt den alten Wert.\n\n' + de_q
    return comment(en=en, de=de)


class OptionsTest(unittest.TestCase):
    """A finding whose checks answered OPTIONS or OPEN asks instead of suggesting; before names the cases the target
    already had (gitlab-comments.md, What it says)."""

    def setUp(self):
        self.p = Report()

    def tearDown(self):
        self.p.tmp.cleanup()

    def build(self, f=None, gitlab=None):
        f = f or finding(options=['A new cookie name: fixes both cases.', 'State it in the description: fixes none.'])
        self.p.findings, self.p.cards = [f], [card(f, gitlab or [options_comment()])]

    def run_ok(self):
        rc = self.p.run()
        self.assertEqual(rc, 0, self.p.out)

    def run_fails(self, text):
        rc = self.p.run()
        self.assertEqual(rc, 1, self.p.out)
        self.assertIn(text, self.p.out)

    def test_options_ask(self):
        self.build()
        self.run_ok()

    def test_one_option_fails(self):
        self.build(f=finding(options=['Only one.']))
        self.run_fails('options in findings.json must list at least two options')

    def test_options_with_suggestion_fail(self):
        self.build(gitlab=[options_comment(de_q='Vorschlag: `x` umbenennen.')])
        self.run_fails('German GitLab text at src/a.ts:11 needs "Frage:" and no "Vorschlag:"')

    def test_triggers_and_options(self):
        f = finding(triggers=triggers(2), options=['A: fixes both.', 'B: fixes none.'])
        en = '`x` resets the counter:\n\n- Case one goes wrong.\n- Case two goes wrong.\n\nQuestion: A, which fixes both, or B?'
        de = '`x` setzt den Zähler zurück:\n\n- Fall eins geht schief.\n- Fall zwei geht schief.\n\nFrage: A, was beide behebt, oder B?'
        c = card(f, [comment(en=en, de=de)])
        c['fields']['what']['text'] = [trigger_what(2), trigger_what(2, 'Der Zähler ist eine Differenz von Ereignissen.', 'Fall %d geht schief.')]
        self.p.findings, self.p.cards = [f], [c]
        self.run_ok()

    def test_open_fix_asks(self):
        f = finding(fixOpen='Where the language is applied again is open.')
        en = '`x` keeps the old language on the page.\n\nQuestion: where should `x` apply the language again?'
        de = '`x` behält die alte Sprache auf der Seite.\n\nFrage: Wo soll `x` die Sprache erneut anwenden?'
        self.p.findings, self.p.cards = [f], [card(f, [comment(en=en, de=de)])]
        self.run_ok()

    def test_open_fix_with_suggestion_fails(self):
        f = finding(fixOpen='Where the language is applied again is open.')
        self.p.findings, self.p.cards = [f], [card(f, [comment()])]
        self.run_fails('needs "Question:" and no "Suggestion:"')

    def test_open_fix_with_options_fails(self):
        f = finding(fixOpen='Open.', options=['A: a.', 'B: b.'])
        self.p.findings, self.p.cards = [f], [card(f, [options_comment()])]
        self.run_fails('fixOpen excludes options and fixLeaves')

    def test_partial_fix_passes(self):
        f = finding(fixLeaves='The login page keeps the browser language.')
        self.p.findings, self.p.cards = [f], [card(f, [comment()])]
        self.run_ok()

    def test_before_passes(self):
        self.build(f=finding(before='With `LANG=en` on a German-default practice.'))
        self.p.cards = [card(self.p.findings[0], [comment()])]
        self.run_ok()

    def test_open_fix_asks(self):
        f = finding(fixOpen='Where the language is applied again is open.')
        en = '`x` keeps the old language on the page.\n\nQuestion: where should `x` apply the language again?'
        de = '`x` behält die alte Sprache auf der Seite.\n\nFrage: Wo soll `x` die Sprache erneut anwenden?'
        self.p.findings, self.p.cards = [f], [card(f, [comment(en=en, de=de)])]
        self.run_ok()

    def test_open_fix_with_suggestion_fails(self):
        f = finding(fixOpen='Where the language is applied again is open.')
        self.p.findings, self.p.cards = [f], [card(f, [comment()])]
        self.run_fails('needs "Question:" and no "Suggestion:"')

    def test_open_fix_with_options_fails(self):
        f = finding(fixOpen='Open.', options=['A: a.', 'B: b.'])
        self.p.findings, self.p.cards = [f], [card(f, [options_comment()])]
        self.run_fails('fixOpen excludes options and fixLeaves')

    def test_partial_fix_passes(self):
        f = finding(fixLeaves='The login page keeps the browser language.')
        self.p.findings, self.p.cards = [f], [card(f, [comment()])]
        self.run_ok()

    def test_empty_before_fails(self):
        f = finding(before=' ')
        self.p.findings, self.p.cards = [f], [card(f, [comment()])]
        self.run_fails('before in findings.json must name the cases on the target')


class SkeletonSyncTest(unittest.TestCase):
    """The review template carries a copy of the skeleton's shared parts: the top bar with the expand-all button and the
    language switch, the language visibility, the paragraph disclosures, the expand-all and switch scripts, the table of
    contents with its scroll spy, and the print rules; the copies stay the same."""

    @staticmethod
    def blocks(text):
        scripts = re.findall(r'<script>(.*?)</script>', text, re.S)
        pats = {
            'language visibility rules': r':root\[data-lang="de"\] \[data-lang\].*?\{ display: none; \}',
            'topbar buttons': r'<div class="switches">\s*<button type="button" class="btn" id="toggle-all".*?</button>\s*'
                              r'<div class="seg" role="group" aria-label="Language / Sprache" id="lang-group">.*?</div>\s*</div>',
            'disclosure css': r'details\.pt \{ margin.*?\.steps li > details\.pt, \.steps li > p \{[^}]*\}',
            'button css': r'\.btn \{[^}]*\}\s*\.btn:focus-visible \{[^}]*\}',
            'reduced motion': r'@media \(prefers-reduced-motion: reduce\) \{.*?\} \}',
            'table of contents label': r'<nav class="toc" aria-label="Contents / Inhalt">',
            'toc css': r'\.toc \{ position: sticky;.*?\.toc a\.active \{[^}]*\}',
            'overflow-anchor': r'html, body \{ overflow-anchor: none; \}',
            'topbar width': r'\.topbar-inner \{[^}]*\}',
            'layout width': r'\.wrap \{[^}]*\}',
            'print css': r'@media print \{(?:[^{}]*\{[^}]*\})*\s*\}',
            'language switch': r'<div class="seg" role="group" aria-label="Language / Sprache" id="lang-group">.*?</div>',
            'padForBar': r'function padForBar\(\).*?\n',
            'expand-all script': r"var toggleAll = document\.getElementById\('toggle-all'\);.*?\n  syncToggle\(\);",
            'scroll spy and expand-all': r"if \(toggleAll\) \{ toggleAll\.addEventListener\('click', function \(\) \{ pinned = null; spy\(\); \}\); \}",
            'setLang': r'function setLang\(lang\) \{.*?\n  \}',
            'visibleAll': r'function visibleAll\(sel\) \{.*?\n  \}',
            'heads and blocks': r"var HEADS = .*?\n  var BLOCKS = .*?\n",
            'readingLine': r'function readingLine\(\).*?\n',
            'keepingPlace and the switch handlers': r"function keepingPlace\(fn\).*?setLang\(root\.dataset\.lang \|\| 'en'\);",
            'scroll spy': r"var links = .*?\n  spy\(\);",
        }
        out = {'restore script': scripts[0]}
        style = re.search(r'<style>(.*?)</style>', text, re.S).group(1)
        # the section and subsection numbering, rule by rule; the order of the rules does not matter
        out['counter rules'] = '\n'.join(sorted(r.strip() for r in re.findall(r'[^{}]*\{[^{}]*counter[^{}]*\}', re.sub(r'/\*.*?\*/', '', style, flags=re.S))))
        for name, pat in pats.items():
            m = re.search(pat, text, re.S)
            out[name] = m.group(0) if m else None
        for k, v in out.items():
            if v is not None:
                v = re.sub(r"var KEY = '[^']*';", "var KEY = '';", re.sub(r'/\*.*?\*/', '', v, flags=re.S))
                out[k] = ' '.join(v.split())
        return out

    @staticmethod
    def tokens(text):
        """The custom properties of each theme block: light, dark by preference, dark by choice."""
        blocks = [re.search(p, text, re.S).group(1) for p in (r'\n:root \{(.*?)\}', r':root:not\(\[data-theme="light"\]\) \{(.*?)\}',
                                                             r'\n:root\[data-theme="dark"\] \{(.*?)\}')]
        return [dict(re.findall(r'(--[\w-]+):\s*([^;]+);', b)) for b in blocks]

    def test_template_tokens_hold_the_skeletons(self):
        skel = self.tokens((HERE.parent / 'qubit-explanation-page' / 'page-skeleton.html').read_text())
        tmpl = self.tokens(assemble.TEMPLATE.read_text())
        for theme, s, t in zip(['light', 'dark by preference', 'dark by choice'], skel, tmpl):
            with self.subTest(theme=theme):
                self.assertTrue(s)
                self.assertEqual({k: t.get(k) for k in s}, s)

    def test_shared_blocks_match(self):
        skel = self.blocks((HERE.parent / 'qubit-explanation-page' / 'page-skeleton.html').read_text())
        tmpl = self.blocks(assemble.TEMPLATE.read_text())
        for name in skel:
            with self.subTest(block=name):
                self.assertIsNotNone(skel[name], 'not found in the skeleton')
                self.assertEqual(tmpl[name], skel[name])


@unittest.skipUnless(shutil.which('node'), 'node not installed')
class CommentPlaceTest(unittest.TestCase):
    """The report's JS names a comment's place and link key like assemble.comment_place and assemble.link_key."""

    def test_js_matches_python(self):
        tmpl = assemble.TEMPLATE.read_text()
        js = ''.join(re.search(r'  function %s\(c\).*?\n' % name, tmpl).group(0) for name in ('place', 'linkKey'))
        cases = [{'path': 'src/a.ts', 'startLine': 12}, {'path': 'src/a.ts', 'startLine': 12, 'endLine': 14},
                 {'path': 'src/a.ts', 'startLine': 12, 'side': 'old'}, {'path': 'img.png'}, {}]
        js += 'console.log(JSON.stringify(%s.map(function (c) { return [place(c), linkKey(c)]; })));' % json.dumps(cases)
        out = subprocess.run(['node', '-e', js], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout), [[assemble.comment_place(c), assemble.link_key(c)] for c in cases])


class GitlabLinksTest(unittest.TestCase):
    def test_line_codes_and_mr_link(self):
        diff = assemble.parse_diff('diff --git a/src/a.ts b/src/a.ts\n--- a/src/a.ts\n+++ b/src/a.ts\n@@ -10,3 +10,3 @@\n a\n-b\n+B\n c\n')
        spec = {'mrUrl': 'https://git.example/g/p/-/merge_requests/7/'}
        data = [{'gitlab': [{'path': 'src/a.ts', 'startLine': 11, 'anchor': 'line'},
                            {'path': 'src/a.ts', 'startLine': 11, 'anchor': 'line', 'side': 'old'},
                            {'path': 'src/a.ts', 'startLine': 10, 'endLine': 12, 'anchor': 'line'},
                            {'path': 'src/a.ts', 'startLine': 99, 'anchor': 'file'}, {'anchor': 'mr'},
                            {'path': 'server/guard.ts', 'startLine': 42, 'anchor': 'mr'}]}]
        links = assemble.gitlab_links(spec, data, diff)
        sha = __import__('hashlib').sha1(b'src/a.ts').hexdigest()
        base = 'https://git.example/g/p/-/merge_requests/7'
        self.assertEqual(links['src/a.ts:11'], '%s/diffs#%s_12_11' % (base, sha))   # added line: next old number
        self.assertEqual(links['src/a.ts:11|old'], '%s/diffs#%s_11_11' % (base, sha))  # removed line: next new number
        self.assertEqual(links['src/a.ts:10'], '%s/diffs#%s_10_10' % (base, sha))   # a range opens its first line
        self.assertEqual(links['src/a.ts:99'], '%s/diffs#%s' % (base, sha))
        self.assertEqual(links[':'], base)
        self.assertEqual(links['server/guard.ts:42'], base)   # a file outside the diff: the MR

    def test_no_mr_no_links(self):
        self.assertEqual(assemble.gitlab_links({}, [{'gitlab': [{'path': 'a', 'startLine': 1, 'anchor': 'line'}]}], {}), {})

    def test_header_links_the_mr(self):
        p = Report()
        p.spec['meta']['subjectType'] = 'mr'
        p.spec['mrUrl'] = 'https://git.example/g/p/-/merge_requests/1'
        self.assertEqual(p.run(), 0, p.out)
        self.assertIn('<a href="https://git.example/g/p/-/merge_requests/1" target="_blank" rel="noopener noreferrer">MR !1</a>', p.page)
        p.tmp.cleanup()

    def test_header_links_the_ticket(self):
        p = Report()
        p.spec['meta'].update(name='Login rework', ticket='PROJ-1', subjectLine='ab/PROJ-1-login → master',
                              reference='PROJ-22, docs/PROJ-3.md, UTF-8')
        p.spec['meta']['lines'] = 0
        self.assertEqual(p.run(), 0, p.out)
        link = '<a href="https://example.atlassian.net/browse/%s" target="_blank" rel="noopener noreferrer">%s</a>'
        self.assertIn('<dd>ab/PROJ-1-login → master</dd>', p.page)
        self.assertIn('<div><dt>Ticket</dt><dd>%s</dd></div>' % (link % ('PROJ-1', 'PROJ-1')), p.page)
        self.assertIn('<span data-lang="de">Weitere Quellen</span>: %s, docs/PROJ-3.md, UTF-8</p>' % (link % ('PROJ-22', 'PROJ-22')), p.page)
        self.assertIn('<title>Login rework · MR !1 · PROJ-1</title>', p.page)
        p.tmp.cleanup()

    def test_without_a_ticket_url_ticket_keys_stay_plain(self):
        # an old run or a repository without a profile has no ticketBrowseUrl: no link, no failure
        p = Report()
        del p.spec['meta']['ticketBrowseUrl']
        p.spec['meta'].update(ticket='PROJ-1', reference='PROJ-22')
        p.spec['meta']['lines'] = 0
        p.frags['verdict'] = para('Waits for PROJ-736 (F1).', 'Wartet auf PROJ-736 (F1).')
        self.assertEqual(p.run(), 0, p.out)
        self.assertIn('<div><dt>Ticket</dt><dd>PROJ-1</dd></div>', p.page)
        self.assertNotIn('atlassian.net', p.page)
        self.assertIn('var JIRA = null;', p.page)
        p.tmp.cleanup()

    def test_only_the_own_mr_is_linked(self):
        p = Report()
        p.spec['meta'].update(subjectType='mr', subjectLine='!12 · b → master, MR !1')
        p.spec['meta']['lines'] = 0
        p.spec['mrUrl'] = 'https://git.example/g/p/-/merge_requests/1'
        self.assertEqual(p.run(), 0, p.out)
        self.assertIn('<dd>!12 · b → master, <a href="https://git.example/g/p/-/merge_requests/1" target="_blank" '
                      'rel="noopener noreferrer">MR !1</a></dd>', p.page)
        p.tmp.cleanup()

    def test_no_ticket_no_ticket_links(self):
        p = Report()
        p.spec['meta']['reference'] = 'PROJ-1'
        self.assertEqual(p.run(), 0, p.out)
        self.assertNotIn('atlassian.net', p.page)
        p.tmp.cleanup()


class TextOrderTest(unittest.TestCase):
    def test_mixed_content_reads_in_document_order(self):
        root = assemble.parse_html('<p>A<span>B</span>C</p>')
        self.assertEqual(assemble.text_of(root), 'ABC')


class RenderReportTest(unittest.TestCase):
    """render_check.py (in qubit-explanation-page) on an assembled review report."""

    @unittest.skipUnless(render_check.chrome(), 'Chrome not installed')
    def test_card_that_overflows_only_on_a_phone_is_flagged(self):
        p = Report()
        self.assertEqual(p.run(), 0, p.out)
        # an open card body wider than a phone and narrower than a desktop; a folded card hides it
        page = p.dir / 'review.html'
        page.write_text(page.read_text().replace('</style>', '.card dd{min-width:600px}</style>', 1))
        out = subprocess.run([sys.executable, str(EXPLAIN / 'render_check.py'), str(p.dir / 'review.html')],
                             capture_output=True, text=True, timeout=300)
        p.tmp.cleanup()
        lines = dict(l.split(': ', 1) for l in out.stdout.splitlines() if ': ' in l)
        self.assertNotIn('OVERFLOW', lines.get('1280 px', ''), out.stdout)
        self.assertIn('OVERFLOW', lines.get('390 px', ''), out.stdout)
        self.assertEqual(out.returncode, 1, out.stdout)

@unittest.skipUnless(render_check.chrome(), 'Chrome not installed')
class ManualTestsTest(unittest.TestCase):
    """The manual test cards in headless Chrome: two exclusive result boxes, a note on a failure, the copy line,
    ticks kept per browser, and a page that works without storage."""

    HELP = ("var r={},q=function(s){return document.querySelector(s)};"
            "var box=function(id,s){return q('#mt-'+id+' input[data-mt-state=\"'+s+'\"]')};"
            "var fail=function(id){return q('#mt-'+id+' .mt-fail')};"
            "var cnt=function(){var c=q('.mt-count');return c?[c.dataset.pass,c.dataset.fail,c.dataset.total]:null};")
    PROBE = ("<script>(function(){" + HELP +
             "r.start=[box('M1','pass').checked,box('M1','fail').checked,fail('M1').hidden,cnt()];"
             "box('M1','fail').click();r.failed=[box('M1','pass').checked,box('M1','fail').checked,fail('M1').hidden,cnt()];"
             "var ta=q('#mt-M1 textarea');ta.value='stays on the error page';ta.dispatchEvent(new Event('input',{bubbles:true}));"
             "r.line=q('#mt-M1 .glc-copy').dataset.copy;"
             "box('M1','pass').click();r.passed=[box('M1','pass').checked,box('M1','fail').checked,fail('M1').hidden,cnt()];"
             "r.stored=localStorage.getItem('review-mr-1-manual');"
             "box('M1','pass').click();r.none=[box('M1','pass').checked,box('M1','fail').checked,cnt()];"
             "r.setup=q('#manual .mt-setup').textContent;r.code=!!q('#mt-M1 code');"
             "document.documentElement.setAttribute('data-probe',JSON.stringify(r))})()</script>")
    READ = ("<script>(function(){" + HELP +
            "document.documentElement.setAttribute('data-probe',JSON.stringify([box('M1','fail').checked,"
            "fail('M1').hidden,q('#mt-M1 textarea').value,cnt()]))})()</script>")
    NO_STORAGE_CLICK = ("<script>(function(){" + HELP +
                        "box('M1','fail').click();"
                        "document.documentElement.setAttribute('data-probe',JSON.stringify([document.querySelectorAll('#manual .mt').length,"
                        "box('M1','fail').checked,fail('M1').hidden]))})()</script>")
    EMPTY = ("<script>(function(){" + HELP +
             "document.documentElement.setAttribute('data-probe',JSON.stringify([!q('#manual-empty').hidden,"
             "document.querySelectorAll('#manual .mt').length,q('#manual > .note').hidden]))})()</script>")
    SEED = "<script>try{localStorage.setItem('review-mr-1-manual','{\"M1\":{\"state\":\"fail\",\"note\":\"x\"}}')}catch(e){}</script>"

    def build(self, document=False):
        p = Report()
        p.spec['manual']['steps'] = [manual_step('M1', do='Open `/admin/auth/login` and sign in.')]
        if document:
            del p.spec['manual']
            p.spec['meta']['subjectType'] = 'document'
            p.spec['gitlab'] = False
            p.findings = [finding(sev='nit')]
            p.spec['verdict'] = {'word': 'accepted', 'openBlockers': []}
            p.frags['verdict'] = verdict('accepted', 'angenommen', ids=())
        self.assertEqual(p.run(), 0, p.out)
        p.tmp.cleanup()
        return p.page

    def run_page(self, html, height=900):
        return DoneMarkTest.run_page(self, html, height)

    def probe(self, page, after, before=''):
        return DoneMarkTest.probe(self, page, after, before)

    def test_result_boxes_note_and_copy_line(self):
        r = self.probe(self.build(), self.PROBE)
        self.assertEqual(r['start'], [False, False, True, ['0', '0', '1']])
        self.assertEqual(r['failed'], [False, True, False, ['0', '1', '1']])
        self.assertEqual(r['line'], 'MR !1 · M1 ✗ · Expected: The dashboard opens. · Observed: stays on the error page')
        self.assertEqual(r['passed'], [True, False, True, ['1', '0', '1']])
        self.assertEqual(json.loads(r['stored']), {'M1': {'state': 'pass', 'note': 'stays on the error page'}})
        self.assertEqual(r['none'], [False, False, ['0', '0', '1']])
        self.assertIn('Start the stack.', r['setup'])
        self.assertTrue(r['code'])

    def test_stored_result_survives_reload(self):
        self.assertEqual(self.probe(self.build(), self.READ, self.SEED), [True, False, 'x', ['0', '1', '1']])

    def test_no_storage_still_works(self):
        self.assertEqual(self.probe(self.build(), self.NO_STORAGE_CLICK, DoneMarkTest.NO_STORAGE), [1, True, False])

    COLOURS = ("<script>(function(){" + HELP +
               "var c=function(s){return getComputedStyle(box('M1',s)).accentColor};"
               "document.documentElement.setAttribute('data-probe',JSON.stringify([c('pass'),c('fail')]))})()</script>")

    def test_fail_box_coloured_unlike_pass_box(self):
        passed, failed = self.probe(self.build(), self.COLOURS)
        self.assertNotEqual(passed, failed)

    def test_document_shows_empty_line(self):
        self.assertEqual(self.probe(self.build(document=True), self.EMPTY), [True, 0, True])


@unittest.skipUnless(render_check.chrome(), 'Chrome not installed')
class SplitPublishRenderTest(unittest.TestCase):
    """The publish folder's page, opened from disk with its files, renders what review.html renders."""

    PROBE = ("<script>(function(){var a=function(s){return document.querySelectorAll(s).length};"
             "document.documentElement.setAttribute('data-probe',JSON.stringify([a('#cards .card'),a('#manual .mt'),"
             "a('nav.toc a'),a('#today'),a('#gitlab-list .glc-item'),document.querySelector('.verdict, #verdict, main').textContent.length>0]))})()</script>")

    def probe_file(self, page_path):
        text = page_path.read_text()
        page_path.write_text(text[:at_end(text)] + self.PROBE + text[at_end(text):])
        res = render_check.probe(render_check.chrome(), page_path.as_uri(), 1280, str(page_path.parent / 'profile'), 900)
        self.assertIsNotNone(res, 'probe did not run')
        return json.loads(res.replace('&quot;', '"'))

    def test_split_page_renders_like_the_single_file(self):
        p = Report()
        p.findings = [finding('F1'), finding('F2', 'optional')]
        self.assertEqual(p.run(), 0, p.out)
        with tempfile.TemporaryDirectory() as tmp:
            single = Path(tmp, 'single.html')
            single.write_text(p.page)
            split = Path(tmp, 'split')
            shutil.copytree(p.dir / 'publish', split)
            want, got = self.probe_file(single), self.probe_file(split / 'index.html')
        p.tmp.cleanup()
        self.assertEqual(want[:2], [2, 1])
        self.assertEqual(got, want)


@unittest.skipUnless(render_check.chrome(), 'Chrome not installed')
class DoneMarkTest(unittest.TestCase):
    """Behaviour of the per-browser "done" mark, the status row and the chip counts, run in headless Chrome."""

    HELP = ("var r={},q=function(s){return document.querySelector(s)};"
            "var chip=function(f,v){return q('.chip[data-filter=\"'+f+'\"][data-value=\"'+v+'\"]')};"
            "var n=function(f,v){var c=chip(f,v);return c&&c.querySelector('.n')?c.querySelector('.n').textContent:null};"
            "var box=function(id){return q('#'+id+' input[data-done]')};"
            "var pressed=function(f){var c=q('.chip[data-filter=\"'+f+'\"][aria-pressed=\"true\"]');return c?c.dataset.value:null};"
            "var listed=function(id){return !!q('#gitlab-list a[href=\"#'+id+'\"]')};")
    PROBE = ("<script>(function(){" + HELP +
             "r.start=[q('#F1').open,q('#F2').open,box('F1').checked,n('status','all'),n('status','open'),n('status','done')];"
             "q('#F1').open=true;box('F1').click();r.ticked=[q('#F1').open,q('#F2').open,box('F1').checked,n('status','all'),n('status','open'),n('status','done')];"
             "q('#F1 summary').click();r.reopened=[q('#F1').open,box('F1').checked];"
             "q('#F1 summary').click();r.reclosed=[q('#F1').open];"
             "r.stored=localStorage.getItem('review-mr-1-done');"
             "chip('status','open').click();r.hidden=[!!q('#F1'),!!q('#F2'),listed('F1'),listed('F2')];"
             "r.storedStatus=localStorage.getItem('review-mr-1-status');"
             "chip('status','all').click();r.shown=[!!q('#F1')];"
             "box('F1').click();r.unticked=[q('#F1').open,box('F1').checked,n('status','done')];"
             "q('#F2 .done-box').click();r.label=[q('#F2').open,box('F2').checked,n('status','done')];"
             "document.documentElement.setAttribute('data-probe',JSON.stringify(r))})()</script>")
    FACETS = ("<script>(function(){" + HELP +
              "chip('category','tests').click();"
              "r.sev={all:n('sev','all'),blocker:n('sev','blocker'),optional:n('sev','optional')};"
              "r.blockerZero=chip('sev','blocker').classList.contains('zero');"
              "chip('category','all').click();chip('sev','blocker').click();"
              "r.category={all:n('category','all'),functionality:n('category','functionality'),tests:n('category','tests')};"
              "document.documentElement.setAttribute('data-probe',JSON.stringify(r))})()</script>")
    EMPTY = ("<script>(function(){" + HELP +
             "chip('status','done').click();"
             "var res=[!q('#cards-empty').hidden,document.querySelectorAll('.chip[data-filter=\"status\"]').length,"
             "chip('status','done').classList.contains('zero')];"
             "chip('status','all').click();res.push(document.querySelectorAll('#cards .card').length);"
             "document.documentElement.setAttribute('data-probe',JSON.stringify(res))})()</script>")
    SEED = "<script>try{localStorage.setItem('review-mr-1-done','[\"F2\"]')}catch(e){}</script>"
    SEED_HIDE = ("<script>try{localStorage.removeItem('review-mr-1-status');"
                 "localStorage.setItem('review-mr-1-hide-done','1')}catch(e){}</script>")
    NO_STORAGE = ("<script>Storage.prototype.getItem=function(){throw new Error('blocked')};"
                  "Storage.prototype.setItem=function(){throw new Error('blocked')};</script>")
    READ = ("<script>(function(){" + HELP +
            "document.documentElement.setAttribute('data-probe',JSON.stringify([q('#F2').open,"
            "box('F2').checked,n('status','done')]))})()</script>")
    READ_STATUS = ("<script>(function(){" + HELP +
                   "document.documentElement.setAttribute('data-probe',JSON.stringify([pressed('status'),n('status','all')]))})()</script>")

    def run_page(self, html, height=900):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp, 'page.html')
            page.write_text(html)
            res = render_check.probe(render_check.chrome(), page.as_uri(), 1280, str(Path(tmp, 'profile')), height)
        self.assertIsNotNone(res, 'probe did not run')
        return json.loads(res.replace('&quot;', '"'))

    def build(self, f2_category='functionality'):
        p = Report()
        p.findings = [finding('F1'), finding('F2', 'optional', category=f2_category)]
        p.spec['verdict']['openBlockers'] = ['F1']
        self.assertEqual(p.run(), 0, p.out)
        p.tmp.cleanup()
        return p.page

    def probe(self, page, after, before=''):
        i, j = page.find('<script>'), at_end(page)
        return self.run_page(page[:i] + before + page[i:j] + after + page[j:])

    def test_cards_start_folded_tick_marks_and_status_filters(self):
        r = self.probe(self.build(), self.PROBE)
        self.assertEqual(r['start'], [False, False, False, '2', '2', '0'])   # every card starts folded
        self.assertEqual(r['ticked'], [False, False, True, '2', '1', '1'])   # a tick on an open card marks and folds it
        self.assertEqual(r['reopened'], [True, True])
        self.assertEqual(r['reclosed'], [False])
        self.assertEqual(json.loads(r['stored']), ['F1'])
        self.assertEqual(r['hidden'], [False, True, False, True])
        self.assertEqual(r['storedStatus'], 'open')
        self.assertEqual(r['shown'], [True])
        self.assertEqual(r['unticked'], [False, False, '0'])
        self.assertEqual(r['label'], [False, True, '1'])

    def test_counts_follow_the_other_rows(self):
        r = self.probe(self.build('tests'), self.FACETS)
        self.assertEqual(r['sev'], {'all': '1', 'blocker': '0', 'optional': '1'})
        self.assertTrue(r['blockerZero'])
        self.assertEqual(r['category'], {'all': '1', 'functionality': '1', 'tests': '0'})

    def test_empty_selection_keeps_chips(self):
        self.assertEqual(self.probe(self.build(), self.EMPTY), [True, 3, True, 2])

    def test_old_hide_done_maps_to_open(self):
        self.assertEqual(self.probe(self.build(), self.READ_STATUS, self.SEED_HIDE), ['open', '2'])

    def test_no_storage_renders_all(self):
        self.assertEqual(self.probe(self.build(), self.READ_STATUS, self.NO_STORAGE), ['all', '2'])

    def test_chip_labels_sentence_case(self):
        page = self.build()
        for label in ['>All<', '>Alle<', '>Open<', '>Offen<', '>Done<', '>Erledigt<']:
            self.assertIn(label, page)
        for label in ['>all<', '>alle<', 'id="hide-done"', 'id="done-count"']:
            self.assertNotIn(label, page)

    def test_filter_handler_only_binds_data_filter_chips(self):
        tmpl = assemble.TEMPLATE.read_text()
        self.assertNotIn("querySelectorAll('.chip'))", tmpl)
        self.assertIn("querySelectorAll('.chip[data-filter]'))", tmpl)

    def test_stored_mark_survives_reload(self):
        self.assertEqual(self.probe(self.build(), self.READ, self.SEED), [False, True, '1'])


SENTENCE = 'The `db-sync` job copies one field after another to the replica.'


def long_text(repeat):
    """A long field text of short paragraphs, within the paragraph limits of text and more."""
    return '\n\n'.join([SENTENCE] * repeat)


@unittest.skipUnless(render_check.chrome(), 'Chrome not installed')
class CardRenderTest(unittest.TestCase):
    """A card shows its location line, the four fields, each a paragraph disclosure where it has details, the follow-up and
    the GitLab comments, all visible without a switch; "Expand all details" opens the card disclosures too."""

    PROBE = ("<script>(function(){var q=function(s){return document.querySelector(s)},r={};"
             "var vis=function(e){return !!(e&&e.getClientRects().length)};"
             "Array.prototype.forEach.call(document.querySelectorAll('#cards details.card'),function(c){c.open=true});"
             "var dds=function(id){return Array.prototype.slice.call(document.querySelectorAll('#'+id+' > dl:not(.glc) > dd'))};"
             "var d=dds('F1');r.n=d.length;"
             "r.disclosure=d.map(function(x){return !!x.querySelector(':scope > details.pt')});"
             "r.whatSummary=d[0].querySelector('summary').innerText;r.whatMore=d[0].querySelector('details.pt').open;"
             "r.chev=!!d[0].querySelector('.ptxt[data-lang=\"en\"] p:last-child .chev');"
             "r.why=d[1].innerText;"
             "r.fixList=d[2].querySelectorAll(':scope > [data-lang=\"en\"] ol li').length;r.fixLead=(d[2].querySelector('p strong')||{}).textContent||'';"
             "r.file=vis(q('#F1 > p.file'))?q('#F1 > p.file').innerText:'';"
             "r.category=(q('#F1 .head .category')||{}).textContent||'';"
             "r.followUp=dds('F2').map(function(x){return x.innerText}).join('|');"
             "var g=q('#F1 .glc');r.glc=vis(g);"
             "q('#toggle-all').click();"
             "r.allOpen=Array.prototype.every.call(document.querySelectorAll('#cards details.pt'),function(x){return x.open});"
             "r.whatMoreOpen=d[0].querySelector('.more-body').checkVisibility();r.pressed=q('#toggle-all').getAttribute('aria-pressed');"
             "q('.chip[data-filter=\"sev\"][data-value=\"blocker\"]').click();"
             "r.afterFilter=[q('#F1 details.pt').open,q('#toggle-all').getAttribute('aria-pressed')];"
             "q('#F1 details.pt').open=false;"
             "setTimeout(function(){r.byHand=[q('#toggle-all').getAttribute('aria-pressed'),q('#toggle-all').innerText];"
             "document.documentElement.setAttribute('data-probe',JSON.stringify(r))},50)})()</script>")

    def test_card_fields_details_and_expand_all(self):
        p = Report()
        p.findings = [finding('F1'), finding('F2', 'optional')]
        p.cards = [card(f, [comment()]) for f in p.findings]
        p.cards[0]['fields']['fix']['text'] = ['**Two steps.** In this order:\n\n1. Stop the job.\n2. Start it again.',
                                               '**Zwei Schritte.** In dieser Reihenfolge:\n\n1. Job anhalten.\n2. Neu starten.']
        self.assertEqual(p.run(), 0, p.out)
        p.tmp.cleanup()
        i = at_end(p.page)
        r = DoneMarkTest.run_page(self, p.page[:i] + self.PROBE + p.page[i:])
        self.assertEqual(r['n'], 4)
        self.assertEqual(r['disclosure'], [True, False, False, True])
        self.assertIn('Card what.', r['whatSummary'])
        self.assertFalse(r['whatMore'], 'the details are open before a click')
        self.assertTrue(r['chev'], 'the arrow does not end the last paragraph of the summary')
        self.assertIn('Card why.', r['why'])
        self.assertEqual(r['fixList'], 2)
        self.assertEqual(r['fixLead'], 'Two steps.')
        self.assertIn('server', r['file'])
        self.assertIn('src/a.ts:11', r['file'])
        self.assertIn('Functionality', r['category'])
        self.assertIn('Follow-up title', r['followUp'])
        self.assertTrue(r['glc'], 'the GitLab comment is not visible inside the card')
        self.assertTrue(r['allOpen'])
        self.assertTrue(r['whatMoreOpen'])
        self.assertEqual(r['pressed'], 'true')
        self.assertEqual(r['afterFilter'], [True, 'true'], 'a filter closed the disclosures "Expand all details" opened')
        self.assertEqual(r['byHand'][0], 'false')
        self.assertIn('Expand all details', r['byHand'][1])


@unittest.skipUnless(render_check.chrome(), 'Chrome not installed')
class SwitchKeepsPlaceTest(unittest.TestCase):
    """The language switch and "Expand all details" keep the element under the reading line where it was."""

    HELPERS = ("Array.prototype.forEach.call(document.querySelectorAll('#cards details.card'),function(c){c.open=true});"
               "var line=function(){return document.querySelector('.topbar').getBoundingClientRect().bottom};"
               "var vis=function(s){return Array.prototype.filter.call(document.querySelectorAll(s),function(e){return e.getClientRects().length})[0]};"
               "var fails=[];var click=function(s){var e=document.querySelector(s),was=e.getAttribute('aria-pressed');e.click();"
               "if(e.id==='toggle-all'?e.getAttribute('aria-pressed')===was:(e.getAttribute('aria-pressed')!=='true'"
               "||(e.dataset.setLang&&document.documentElement.dataset.lang!==e.dataset.setLang))){fails.push(s)}};")

    def probe(self, html, body, height=900):
        i = at_end(html)
        # browser scroll anchoring off, as in Safari: the page itself must keep the place
        html = html[:i] + '<style>*{overflow-anchor:none}</style><div style="height:3000px"></div><script>(function(){' + self.HELPERS + body + \
            "r.switchFailed=fails;document.documentElement.setAttribute('data-probe',JSON.stringify(r))})()</script>" + html[i:]
        r = DoneMarkTest.run_page(self, html, height)
        self.assertEqual(r.pop('switchFailed'), [], 'the language switch or the expand-all button did not take effect')
        return r

    def review_report(self, repeat=40):
        p = Report()
        p.findings = [finding('F%d' % n) for n in range(1, 13)]
        p.spec['verdict']['openBlockers'] = [f['id'] for f in p.findings]
        p.cards = []
        for f in p.findings:
            c = card(f, [comment()])
            c['fields']['why'] = {'text': [long_text(repeat), 'DE ' + long_text(repeat)],
                                  'more': [long_text(repeat), 'DE ' + long_text(repeat)]}
            p.cards.append(c)
        self.assertEqual(p.run(), 0, p.out)
        p.tmp.cleanup()
        return p.page

    def test_card_title_stays_at_its_distance(self):
        r = self.probe(self.review_report(),
            "var el=function(){return vis('#F6 > summary')},r={};"
            "scrollTo(0,scrollY+el().getBoundingClientRect().top-line()-40);scrollTo(0,scrollY+el().getBoundingClientRect().top-line()-40);"
            "r.before=Math.round(el().getBoundingClientRect().top-line());"
            "click('#toggle-all');r.expand=Math.round(el().getBoundingClientRect().top-line());"
            "click('[data-set-lang=\"de\"]');r.lang=Math.round(el().getBoundingClientRect().top-line());")
        self.assertEqual(r['before'], 40)
        self.assertLessEqual(abs(r['expand'] - 40), 2, r)
        self.assertLessEqual(abs(r['lang'] - 40), 2, r)

    def test_without_a_title_on_screen_the_card_keeps_the_ratio(self):
        r = self.probe(self.review_report(80),
            "var el=function(){return vis('#F6')},r={};"
            "var ratio=function(){var b=el().getBoundingClientRect();return Math.round(100*(line()-b.top)/b.height)};"
            "var b=el().getBoundingClientRect();scrollTo(0,scrollY+b.top-line()+0.3*b.height);b=el().getBoundingClientRect();scrollTo(0,scrollY+b.top-line()+0.3*b.height);"
            "r.before=ratio();click('#toggle-all');r.after=ratio();")
        self.assertEqual(r['before'], 30)
        self.assertLessEqual(abs(r['after'] - 30), 2, r)

    def test_next_card_stays_when_the_line_is_in_the_tail_of_the_previous(self):
        r = self.probe(self.review_report(),
            "var el=function(){return vis('#F7')},r={};"
            "click('#toggle-all');"
            "scrollTo(0,scrollY+el().getBoundingClientRect().top-line()-140);scrollTo(0,scrollY+el().getBoundingClientRect().top-line()-140);"
            "var leaf=Array.prototype.some.call(document.querySelectorAll('#F6 dt[data-field]'),function(e){var b=e.getBoundingClientRect();return b.height&&b.top<=line()&&b.bottom>line()});"
            "var f6=vis('#F6').getBoundingClientRect();r.inTail=!leaf&&f6.top<=line()&&f6.bottom>line();"
            "r.before=Math.round(el().getBoundingClientRect().top-line());"
            "click('#toggle-all');r.after=Math.round(el().getBoundingClientRect().top-line());", height=400)
        self.assertTrue(r['inTail'], r)
        self.assertEqual(r['before'], 140)
        self.assertLessEqual(abs(r['after'] - 140), 2, r)

    def tall_neighbours(self):
        """Eight Blockers; F2's Checked and F3's Impact long, each with long details."""
        p = Report()
        p.findings = [finding('F%d' % n) for n in range(1, 9)]
        p.spec['verdict']['openBlockers'] = [f['id'] for f in p.findings]
        p.cards = [card(f, [comment()]) for f in p.findings]
        p.cards[1]['fields']['verify'] = {'text': [long_text(20), 'DE ' + long_text(20)], 'more': [long_text(20), 'DE ' + long_text(20)]}
        p.cards[2]['fields']['why'] = {'text': [long_text(20), 'DE ' + long_text(20)], 'more': [long_text(20), 'DE ' + long_text(20)]}
        self.assertEqual(p.run(), 0, p.out)
        p.tmp.cleanup()
        return p.page

    def test_visible_card_title_stays_when_the_line_is_in_the_previous_field(self):
        r = self.probe(self.tall_neighbours(),
            "var el=function(){return vis('#F3 > summary')},f=function(){return vis('#F2 > dl > dd:nth-of-type(4)')},r={};"
            "var b=f().getBoundingClientRect();scrollTo(0,scrollY+b.top-line()+0.3*b.height);b=f().getBoundingClientRect();scrollTo(0,scrollY+b.top-line()+0.3*b.height);"
            "var c=el().getBoundingClientRect();r.fully=vis('#F3').getBoundingClientRect().bottom<=innerHeight;"
            "r.before=Math.round(c.top-line());"
            "click('#toggle-all');r.after=Math.round(el().getBoundingClientRect().top-line());")
        self.assertFalse(r['fully'], r)
        self.assertGreater(r['before'], 225)
        self.assertLessEqual(abs(r['after'] - r['before']), 2, r)

    def test_title_stays_with_the_browsers_own_anchoring_on(self):
        """Chrome and Firefox correct the scroll in the next frame, after the page's own correction."""
        html = self.tall_neighbours()
        i = at_end(html)
        html = html[:i] + '<div style="height:3000px"></div><script>(function(){' + self.HELPERS + \
            "var el=function(){return vis('#F3 > summary')},f=function(){return vis('#F2 > dl > dd:nth-of-type(4)')},r={};" \
            "var b=f().getBoundingClientRect();scrollTo(0,scrollY+b.top-line()+0.3*b.height);b=f().getBoundingClientRect();scrollTo(0,scrollY+b.top-line()+0.3*b.height);" \
            "setTimeout(function(){r.before=Math.round(el().getBoundingClientRect().top-line());click('#toggle-all');r.now=Math.round(el().getBoundingClientRect().top-line());" \
            "setTimeout(function(){r.later=Math.round(el().getBoundingClientRect().top-line());" \
            "r.switchFailed=fails;document.documentElement.setAttribute('data-probe',JSON.stringify(r))},300)},100)})()</script>" + html[i:]
        r = DoneMarkTest.run_page(self, html)
        self.assertEqual(r.pop('switchFailed'), [], 'the expand-all button did not take effect')
        self.assertLessEqual(abs(r['now'] - r['before']), 2, r)
        self.assertLessEqual(abs(r['later'] - r['before']), 2, r)

    def test_title_half_under_the_bar_stays(self):
        p = Report()
        p.findings = [finding('F%d' % n) for n in range(1, 9)]
        p.spec['verdict']['openBlockers'] = [f['id'] for f in p.findings]
        p.cards = [card(f, [comment()]) for f in p.findings]
        p.cards[5]['fields']['why']['more'] = [long_text(6), 'DE ' + long_text(6)]
        self.assertEqual(p.run(), 0, p.out)
        p.tmp.cleanup()
        r = self.probe(p.page,
            "var el=function(){return vis('#F6 > summary')},r={};"
            "scrollTo(0,scrollY+el().getBoundingClientRect().top-line()+8);scrollTo(0,scrollY+el().getBoundingClientRect().top-line()+8);"
            "var n=vis('#F7 > summary').getBoundingClientRect();r.nextOnScreen=n.top<innerHeight;"
            "r.before=Math.round(el().getBoundingClientRect().top-line());"
            "click('#toggle-all');r.expand=Math.round(el().getBoundingClientRect().top-line());")
        self.assertTrue(r['nextOnScreen'], r)
        self.assertEqual(r['before'], -8)
        self.assertLessEqual(abs(r['expand'] + 8), 2, r)

    def test_without_a_title_on_screen_the_first_field_label_stays(self):
        p = Report()
        p.findings = [finding('F%d' % n) for n in range(1, 9)]
        p.spec['verdict']['openBlockers'] = [f['id'] for f in p.findings]
        p.cards = [card(f, [comment()]) for f in p.findings]
        for c in p.cards:
            for k in ['why', 'verify']:
                c['fields'][k] = {'text': [long_text(40), 'DE ' + long_text(40)], 'more': [long_text(40), 'DE ' + long_text(40)]}
        self.assertEqual(p.run(), 0, p.out)
        p.tmp.cleanup()
        r = self.probe(p.page,
            "var el=function(){return vis('#F6 dt[data-field=\"fix\"]')},r={};"
            "scrollTo(0,scrollY+el().getBoundingClientRect().top-line()-40);scrollTo(0,scrollY+el().getBoundingClientRect().top-line()-40);"
            "r.titles=Array.prototype.filter.call(document.querySelectorAll('.card > summary'),function(s){var b=s.getBoundingClientRect();return b.bottom>line()&&b.top<innerHeight}).length;"
            "r.before=Math.round(el().getBoundingClientRect().top-line());"
            "click('#toggle-all');r.expand=Math.round(el().getBoundingClientRect().top-line());"
            "click('[data-set-lang=\"de\"]');r.lang=Math.round(el().getBoundingClientRect().top-line());")
        self.assertEqual(r['titles'], 0, r)
        self.assertEqual(r['before'], 40)
        self.assertLessEqual(abs(r['expand'] - 40), 2, r)
        self.assertLessEqual(abs(r['lang'] - 40), 2, r)

    def test_skeleton_subsection_stays(self):
        html = (HERE.parent / 'qubit-explanation-page' / 'page-skeleton.html').read_text()
        r = self.probe(html,
            "var el=function(){return vis('#concept-x')},r={};"
            "scrollTo(0,scrollY+el().getBoundingClientRect().top-line()-30);scrollTo(0,scrollY+el().getBoundingClientRect().top-line()-30);"
            "r.before=Math.round(el().getBoundingClientRect().top-line());"
            "click('#toggle-all');r.expand=Math.round(el().getBoundingClientRect().top-line());"
            "click('[data-set-lang=\"de\"]');r.lang=Math.round(el().getBoundingClientRect().top-line());")
        self.assertEqual(r['before'], 30)
        self.assertLessEqual(abs(r['expand'] - 30), 2, r)
        self.assertLessEqual(abs(r['lang'] - 30), 2, r)


class SaveOutputTest(unittest.TestCase):
    def transcript(self, entries):
        f = tempfile.NamedTemporaryFile('w', suffix='.output', delete=False)
        for e in entries:
            f.write(json.dumps(e) + '\n')
        f.close()
        return f.name

    def say(self, text):
        return {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': text}]}}

    def handback(self, text):
        return {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'SubagentHandback', 'input': {'message': text}}]}}

    def test_short_final_text_is_saved(self):
        path = self.transcript([self.say('Plan: ' + 'x' * 900), self.say('# Summary\nClean.')])
        self.assertEqual(save_output.final_output(path), '# Summary\nClean.')

    def test_text_blocks_of_the_last_message_are_joined(self):
        part = lambda text: {'type': 'assistant', 'message': {'id': 'm2', 'content': [{'type': 'text', 'text': text}]}}
        path = self.transcript([self.say('earlier'), part('# Summary\nA.'), part('# Findings\nB.')])
        self.assertEqual(save_output.final_output(path), '# Summary\nA.\n\n# Findings\nB.')

    def test_missing_transcript_is_no_output(self):
        out = subprocess.run([sys.executable, str(HERE / 'save_output.py'), '/nonexistent/x.output', '/tmp/never-written.md'],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn('no output found', out.stdout)
        self.assertNotIn('Traceback', out.stderr)

    def test_handback_wins_over_later_text(self):
        path = self.transcript([self.handback('# Summary\nHanded back.'), self.say('y' * 900)])
        self.assertEqual(save_output.final_output(path), '# Summary\nHanded back.')

    def test_no_output_exits_1_and_writes_nothing(self):
        path = self.transcript([{'type': 'user', 'message': {'content': 'go'}}])
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, 'core.md')
            out = subprocess.run([sys.executable, str(HERE / 'save_output.py'), path, str(target)], capture_output=True, text=True)
            self.assertEqual(out.returncode, 1, out.stdout)
            self.assertIn('no output found', out.stdout)
            self.assertFalse(target.exists())

    def api_error(self, text='API Error: Request rejected (429)'):
        return {'type': 'assistant', 'isApiErrorMessage': True, 'message': {'content': [{'type': 'text', 'text': text}]}}

    def test_run_that_ended_on_an_api_error_exits_3(self):
        path = self.transcript([self.say('# Summary\nHalf done.'), self.api_error()])
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, 'core.md')
            out = subprocess.run([sys.executable, str(HERE / 'save_output.py'), path, str(target)], capture_output=True, text=True)
            self.assertEqual(out.returncode, 3, out.stdout)
            self.assertIn('ended on an API error', out.stdout)
            self.assertEqual(target.read_text(), '# Summary\nHalf done.')
            self.assertNotIn('Half done', out.stdout)

    def test_api_error_alone_is_no_output(self):
        path = self.transcript([self.api_error()])
        self.assertIsNone(save_output.final_output(path))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, 'core.md')
            out = subprocess.run([sys.executable, str(HERE / 'save_output.py'), path, str(target)], capture_output=True, text=True)
            self.assertEqual(out.returncode, 3, out.stdout)
            self.assertIn('ended on an API error', out.stdout)
            self.assertFalse(target.exists())

    def test_api_error_before_a_later_output_is_no_failure(self):
        path = self.transcript([self.api_error(), self.say('# Summary\nDone.')])
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, 'core.md')
            out = subprocess.run([sys.executable, str(HERE / 'save_output.py'), path, str(target)], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stdout)
            self.assertEqual(target.read_text(), '# Summary\nDone.')

    def test_output_is_written_and_only_its_size_printed(self):
        output = '# Summary\nClean.\n\n# Findings\nNone.'
        path = self.transcript([self.say(output)])
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, 'core.md')
            out = subprocess.run([sys.executable, str(HERE / 'save_output.py'), path, str(target)], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stdout)
            self.assertEqual(target.read_text(), output)
            self.assertNotIn('Clean.', out.stdout)
            self.assertIn('saved %d characters' % len(output), out.stdout)


class DocsMatchCodeTest(unittest.TestCase):
    """The word lists the docs give the writers and the translator are the ones assemble.py checks."""

    def test_verdict_words(self):
        table = (HERE / 'SKILL.md').read_text()
        rows = [r.split('|')[4].strip() for r in table.splitlines()
                if r.startswith('| ') and r.count('|') == 6 and ' / ' in r.split('|')[4]]
        self.assertEqual([tuple(r.split(' / ')) for r in rows], list(assemble.VERDICTS.items()))
        tooling = ' '.join((HERE / 'tooling.md').read_text().split())
        m = re.search(r'German verdict words `assemble\.py` checks: (.*?)\. ', tooling)
        self.assertIsNotNone(m, 'tooling.md lists no German verdict words')
        de = [tuple(p.split(' / ')) for p in m.group(1).split(', ')]
        self.assertEqual(de, [(assemble.VERDICTS_DE[w], assemble.VERDICTS_DE[n]) for w, n in assemble.VERDICTS.items()])

    def forbidden(self, lang):
        doc = ' '.join((HERE / 'gitlab-comments.md').read_text().split())
        m = re.search(r'- %s: (.*?)(?= - [A-Z][a-z]+:|\. The writer| The writer)' % lang, doc)
        self.assertIsNotNone(m, 'gitlab-comments.md has no %s list' % lang)
        words = set(re.findall(r'`([^`]+)`', m.group(1))) - {'us-east-1', 'ihr'}  # the two the list names as passing
        if 'Ihr…' in words:
            words = words - {'Ihr…'} | {'Ihr' + e for e in ['', 'e', 'em', 'en', 'er', 'es']}
        if 'unser' in words and 'same endings' in m.group(1):
            words |= {'unser' + e for e in ['e', 'em', 'en', 'er', 'es']}
        return words

    VOCAB = {'English': 'you your yours I we our ours us let\'s please me my mine they them their he she it one',
             'German': 'du dich dir ich wir uns euch euer bitte dein deine deinem deinen deiner deines unser unsere unserem '
                       'unseren unserer unseres eure eurem euren eurer eures Sie Ihr Ihre Ihrem Ihren Ihrer Ihres Ihnen ihr '
                       'ihre mich mir mein meine sein seine man es'}

    def flagged(self, lang, word):
        en, de = ('The check fails for %s now.' % word, 'Der Test.') if lang == 'English' else ('The test.', 'Das betrifft %s heute.' % word)
        return assemble.addresses_person(en, de)

    def test_forbidden_words(self):
        for lang in ['English', 'German']:
            with self.subTest(lang=lang):
                doc = self.forbidden(lang)
                self.assertGreater(len(doc), 8)
                self.assertEqual(sorted(w for w in doc if not self.flagged(lang, w)), [], 'listed, but assemble.py lets them pass')
                code = {w for w in self.VOCAB[lang].split() if self.flagged(lang, w)}
                self.assertEqual(sorted(code - doc), [], 'assemble.py fails them, but the list does not name them')


class PromptSyncTest(unittest.TestCase):
    """SECRET_FILES, the INFL excludes, the patch gate and the reviewer prompt name the same secret files."""

    SECRETS = ['.production.env', '.staging.env', '.envrc']
    PROFILE_PY = HERE.parent / '_profiles' / 'profile.py'

    def setUp(self):
        # a profile folder and a repository of the tests' own, so the user's local profiles never decide the result
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        profiles = Path(self.tmp.name, 'profiles')
        (profiles / 'test').mkdir(parents=True)
        (profiles / 'test' / 'config.json').write_text(json.dumps(
            {'remotes': ['git.example.com/g/r'], 'secretFiles': self.SECRETS}))
        (profiles / 'none').mkdir()
        self.repo = Path(self.tmp.name, 'repo')
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'remote', 'add', 'origin', 'https://git.example.com/g/r.git'], check=True)
        self.env = dict(os.environ, QUBIT_PROFILES_DIR=str(profiles))
        self.no_profile_env = dict(os.environ, QUBIT_PROFILES_DIR=str(profiles / 'none'))

    def tooling(self):
        return (HERE / 'tooling.md').read_text()

    def sourced(self, name, env=None):
        """The elements of an array that scripts/secrets.sh defines, as bash expands it, with WT at the test repo."""
        run = subprocess.run(['bash', '-c', 'WT="$2"; . "$1"; printf "%%s\\n" "${%s[@]}"' % name, 'bash',
                              str(HERE / 'scripts' / 'secrets.sh'), str(self.repo)],
                             capture_output=True, text=True, check=True, env=env or self.env)
        return run.stdout.splitlines()

    def profile(self, *args, env=None):
        return subprocess.run([sys.executable, str(self.PROFILE_PY), *args], cwd=self.repo, capture_output=True,
                              text=True, check=True, env=env or self.env).stdout.strip()

    def test_without_a_matching_profile_the_secret_files_are_the_broad_fallback(self):
        names = self.sourced('SECRET_FILES', env=self.no_profile_env)
        self.assertEqual(names, self.profile('secret-files', env=self.no_profile_env).splitlines())
        for pattern in ['.env', '*.env', '.envrc', '*.pem']:
            self.assertIn(pattern, names)
        # secrets.sh repeats profile.py's fallback for the case that profile.py itself fails
        sh = (HERE / 'scripts' / 'secrets.sh').read_text()
        fallback = re.search(r"if \[ \$\{#SECRET_FILES\[@\]\} -eq 0 \]; then\n  SECRET_FILES=\((.*?)\)\n", sh, re.S).group(1)
        self.assertEqual(shlex.split(fallback), names)

    def test_infl_prompt_and_gate_name_the_secret_files(self):
        names = self.sourced('SECRET_FILES')
        self.assertEqual(names, self.SECRETS)
        infl = [e for e in self.sourced('INFL') if 'glob' in e]
        self.assertEqual(infl, [':(exclude,glob)**/' + n for n in names])
        # the orchestrator fills the prompt's placeholder from profile.py; it names the same excludes as INFL
        excludes = self.profile('secret-excludes')
        self.assertEqual(shlex.split(excludes), ['--'] + infl)
        prompt = (HERE / 'reviewer-prompt.md').read_text()
        self.assertIn('`<SECRET_EXCLUDES>`', prompt)
        self.assertIn('<SECRET_FILES>', prompt)
        self.assertEqual(re.findall(r"'(:\(exclude,glob\)[^']+)'", prompt), [])
        self.assertNotIn("':(exclude)<pattern", prompt)
        for script in sorted((HERE / 'scripts').glob('*.sh')):
            text = script.read_text()
            if script.name == 'secrets.sh' or not re.search(r'\$\{(SECRET_FILES|INFL)\[@\]\}', text):
                continue
            with self.subTest(script=script.name):
                self.assertIn('. "$(dirname "$0")/secrets.sh"', text)
                self.assertNotRegex(text, r'(?m)^\s*(SECRET_FILES|INFL)=\(')  # one source: secrets.sh
        self.assertIn('"${SECRET_FILES[@]}"', (HERE / 'scripts' / 'patch-inputs.sh').read_text())

    def test_patch_gate_stops_on_secret_files_and_unreadable_patches(self):
        gate = HERE / 'scripts' / 'patch-inputs.sh'
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp, 'r')
            git = lambda *a: subprocess.run(['git', '-C', str(repo)] + list(a), capture_output=True, text=True, check=True).stdout
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            git('remote', 'add', 'origin', 'https://git.example.com/g/r.git')
            (repo / 'x.ts').write_text('a\n')
            (repo / 'ops').mkdir()
            (repo / 'ops' / '.production.env').write_text('K=1\nL=2\nM=3\n')
            (repo / 'dir \u00e4').mkdir()
            (repo / 'dir \u00e4' / '.staging.env').write_text('D=1\n')
            (repo / '.empty.env').write_text('E=1\n')
            git('add', '-A')
            git('-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'init')
            patches = {}
            def cached(*flags):
                git('add', '-A'); out = git('diff', '--cached', *flags); git('reset', '-q', '--hard'); git('clean', '-qfd'); return out
            (repo / 'x.ts').write_text('b\n'); patches['ok'] = cached()
            (repo / '.empty.env').write_text('E=2\n'); patches['dummy env'] = cached()
            (repo / 'note .staging.env').write_text('n\n'); patches['lookalike'] = cached()
            (repo / 'ops' / '.production.env').write_text('K=2\nL=2\nM=3\n'); patches['secret'] = cached()
            (repo / 'ops' / '.production.env').unlink(); patches['delete'] = cached()
            (repo / 'dir \u00e4' / '.staging.env').write_text('D=2\n'); patches['quoted path'] = cached()
            git('mv', 'x.ts', '.envrc'); patches['rename to'] = cached('-M')
            git('mv', 'ops/.production.env', 'y.ts'); (repo / 'y.ts').write_text('K=2\nL=2\nM=3\n'); patches['rename from'] = cached('-M')
            (repo / 'z.ts').write_text('K=1\nL=2\nM=3\nN=4\n'); patches['copy from'] = cached('-C', '-C')
            patches['bad'] = 'garbage\n'
            self.assertIn('rename from ops/.production.env', patches['rename from'])
            self.assertIn('copy from ops/.production.env', patches['copy from'])
            # the last two run without a matching profile: the broad fallback stops a dummy env file too
            cases = [('ok', 0, self.env), ('dummy env', 0, self.env), ('lookalike', 0, self.env), ('secret', 1, self.env),
                     ('delete', 1, self.env), ('quoted path', 1, self.env), ('rename to', 1, self.env),
                     ('rename from', 1, self.env), ('copy from', 1, self.env), ('bad', 1, self.env),
                     ('ok', 0, self.no_profile_env), ('dummy env', 1, self.no_profile_env)]
            for i, (name, want, env) in enumerate(cases):
                with self.subTest(patch=name, profile=env is self.env):
                    pf = Path(tmp, name.replace(' ', '-') + '.patch'); pf.write_text(patches[name])
                    sp = Path(tmp, 'sp-%d-%s' % (i, name.replace(' ', '-')))
                    for d in ['inputs', 'checks']:
                        (sp / d).mkdir(parents=True)
                    run = subprocess.run(['bash', str(gate), str(sp), str(repo), str(pf), 'p'], capture_output=True, text=True,
                                         env=env)
                    self.assertEqual(run.returncode, want, (run.stdout, run.stderr))
                    self.assertEqual((sp / 'inputs' / 'change.diff').exists(), want == 0)

    def test_repo_rules_collects_the_instruction_files_above_every_changed_path(self):
        block = re.search(r'^### Repo rules.*?```bash\n(.*?)```', self.tooling(), re.S | re.M)
        self.assertIsNotNone(block, 'tooling.md has no Repo rules block')
        shells = [sh for sh in ['bash', 'zsh'] if shutil.which(sh)]
        self.assertTrue(shells)
        for sh in shells:
            with self.subTest(shell=sh), tempfile.TemporaryDirectory() as tmp:
                repo, sp = Path(tmp, 'r'), Path(tmp, 'sp')
                for p in ['CLAUDE.md', 'server/CLAUDE.md', 'server/AGENTS.md', 'server/src/x/a.ts',
                          'other/CLAUDE.md', 'dir ä/CLAUDE.md', 'dir ä/b.ts', 'gone/CLAUDE.md']:
                    (repo / p).parent.mkdir(parents=True, exist_ok=True)
                    (repo / p).write_text(p + '\n')
                (sp / 'inputs').mkdir(parents=True)
                (sp / 'inputs' / 'change.files.txt').write_text(
                    'M\tserver/src/x/a.ts\nR100\told/b.ts\tdir ä/b.ts\nD\tgone/c.ts\n')
                script = block.group(1).replace('SP=<absolute scratchpad path>', 'SP=' + shlex.quote(str(sp)))
                run = subprocess.run([sh, '-c', script], cwd=repo, capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                got = sorted(p.name for p in (sp / 'inputs' / 'sources' / 'rules').iterdir())
                self.assertEqual(got, sorted(['CLAUDE.md', 'server__CLAUDE.md', 'server__AGENTS.md',
                                              'dir ä__CLAUDE.md', 'gone__CLAUDE.md']))
                self.assertEqual((sp / 'inputs' / 'sources' / 'rules' / 'server__CLAUDE.md').read_text(), 'server/CLAUDE.md\n')

    def test_state_files_stay_outside_inputs(self):
        for doc in ['SKILL.md', 'tooling.md', 'report-sections.md', 'reviewer-prompt.md']:
            text = (HERE / doc).read_text()
            for f in ['dispatch.txt', 'trace.md', 'ranking.txt']:
                with self.subTest(doc=doc, f=f):
                    self.assertNotIn('inputs/' + f, text)
        prompt = ' '.join((HERE / 'reviewer-prompt.md').read_text().split())
        self.assertIn('read only <scratchpad path>/inputs/', prompt)
        self.assertNotIn('A pre-computed copy is in <scratchpad path>.', prompt)


class SaveRunScriptTest(unittest.TestCase):
    """scripts/save-run.sh: an update of an earlier report keeps the earlier raw outputs and puts the new ones in a
    subfolder of their own."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.wt, self.sp = t / 'wt', t / 'sp'
        subprocess.run(['git', 'init', '-q', str(self.wt)], check=True)
        for sub in ['reviews', 'report', 'state']:
            (self.sp / sub).mkdir(parents=True)
        (self.sp / 'report' / 'findings.json').write_text('{}')

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, *args):
        return subprocess.run(['bash', str(HERE / 'scripts' / 'save-run.sh'), str(self.sp), str(self.wt), 'review-runs', 'n'] + list(args),
                              capture_output=True, text=True)

    def test_update_puts_new_raw_outputs_in_a_subfolder(self):
        (self.sp / 'reviews' / 'core.md').write_text('first run')
        self.assertEqual(self.save('no').returncode, 0)
        (self.sp / 'reviews' / 'core.md').write_text('second run')
        out = self.save('yes', 'rerun-abcd1234')
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        run = self.wt / 'review-runs' / 'n'
        self.assertEqual((run / 'core.md').read_text(), 'first run')
        self.assertEqual((run / 'rerun-abcd1234' / 'core.md').read_text(), 'second run')

    def test_update_keeps_the_earlier_state_and_inputs(self):
        (self.sp / 'reviews' / 'core.md').write_text('first run')
        (self.sp / 'state' / 'trace.md').write_text('first trace')
        self.assertEqual(self.save('no').returncode, 0)
        (self.sp / 'state' / 'trace.md').write_text('second trace')
        self.assertEqual(self.save('yes', 'rerun-abcd1234').returncode, 0)
        run = self.wt / 'review-runs' / 'n'
        self.assertEqual((run / 'state' / 'trace.md').read_text(), 'first trace')
        self.assertEqual((run / 'rerun-abcd1234' / 'state' / 'trace.md').read_text(), 'second trace')

    def test_without_subfolder_raw_outputs_go_to_the_run_folder(self):
        (self.sp / 'reviews' / 'core.md').write_text('first run')
        self.assertEqual(self.save('no').returncode, 0)
        self.assertEqual((self.wt / 'review-runs' / 'n' / 'core.md').read_text(), 'first run')


class SourcesScriptTest(unittest.TestCase):
    """scripts/sources.sh writes the commit messages and the MR description; a failed glab stops the review."""

    def run_script(self, glab_exit):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo, sp, bin_ = Path(tmp.name, 'r'), Path(tmp.name, 'sp'), Path(tmp.name, 'bin')
        git = lambda *a: subprocess.run(['git', '-C', str(repo), '-c', 'user.email=t@t', '-c', 'user.name=t'] + list(a),
                                        capture_output=True, text=True, check=True)
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
        (repo / 'a.ts').write_text('a\n'); git('add', '-A'); git('commit', '-qm', 'base')
        git('checkout', '-qb', 'feature')
        for i, msg in enumerate(['dev: first\n\nWhy it changes.', 'dev: second']):
            (repo / ('b%d.ts' % i)).write_text('b\n'); git('add', '-A'); git('commit', '-qm', msg)
        (sp / 'state').mkdir(parents=True)
        (sp / 'state' / 'target.env').write_text("REMOTE=''\nTGT=main\n")
        bin_.mkdir()
        mr = {'iid': 7, 'title': 'Add it', 'web_url': 'https://git.example/g/p/-/merge_requests/7', 'author': {'username': 'dev'},
              'source_branch': 'feature', 'target_branch': 'main', 'description': "Body with $SP and 'quotes'.", 'sha': 'abc123'}
        (bin_ / 'glab').write_text('#!/bin/sh\n%s\n' % ("cat <<'J'\n%s\nJ" % json.dumps(mr) if glab_exit == 0 else 'exit 1'))
        (bin_ / 'glab').chmod(0o755)
        env = dict(os.environ, PATH=str(bin_) + os.pathsep + os.environ['PATH'])
        run = subprocess.run(['bash', str(HERE / 'scripts' / 'sources.sh'), str(sp), str(repo), '7'], capture_output=True, text=True, env=env)
        return run, sp

    def test_writes_commit_messages_and_mr_description(self):
        run, sp = self.run_script(0)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        commits = (sp / 'inputs' / 'sources' / 'commit-messages.txt').read_text()
        self.assertIn('Why it changes.', commits)
        self.assertIn('dev: second', commits)
        self.assertNotIn('base', commits)
        desc = (sp / 'inputs' / 'sources' / 'mr-description.md').read_text()
        self.assertTrue(desc.startswith('# MR !7: Add it'))
        self.assertIn("Body with $SP and 'quotes'.", desc)
        self.assertIn('mrUrl https://git.example/g/p/-/merge_requests/7', run.stdout)
        self.assertIn('sha abc123', run.stdout)

    def test_failed_glab_stops(self):
        run, sp = self.run_script(1)
        self.assertEqual(run.returncode, 1)
        self.assertIn('stop and ask the user', run.stdout)
        self.assertFalse((sp / 'inputs' / 'sources' / 'mr-description.md').exists())


class ReadPartsTest(unittest.TestCase):
    def test_parts_cover_every_line_within_the_limit(self):
        text = '\n'.join(['x' * 30] * 50 + ['y' * 500] + ['z' * 10] * 20)
        parts = assemble.read_parts(text, limit=400)
        self.assertEqual(parts[0][0], 1)
        self.assertEqual(parts[-1][1], 71)
        self.assertEqual([b[0] for b in parts[1:]], [a[1] + 1 for a in parts[:-1]])
        lines = text.split('\n')
        for a, b in parts:
            size = sum(len(l) + 1 for l in lines[a - 1:b])
            self.assertTrue(size <= 400 or a == b, (a, b, size))

    def test_node_error_gives_location_and_message(self):
        err = '/x/inline.js:57\n  foo(\n     ^\n\nSyntaxError: missing ) after argument list\n    at ...\n'
        self.assertEqual(assemble.node_error(err), '/x/inline.js:57 SyntaxError: missing ) after argument list')
        self.assertIn('without a message', assemble.node_error(''))


class ParseDiffTest(unittest.TestCase):
    # quoted non-ASCII paths
    def test_quoted_path(self):
        diff = ('diff --git a/first.ts b/first.ts\n--- a/first.ts\n+++ b/first.ts\n@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n'
                'diff --git "a/\\303\\244.ts" "b/\\303\\244.ts"\n--- "a/\\303\\244.ts"\n+++ "b/\\303\\244.ts"\n@@ -1,2 +1,3 @@\n x\n+y\n z\n')
        files = assemble.parse_diff(diff)
        self.assertEqual(files['first.ts']['new'][2], (3, 2))
        self.assertEqual(files['first.ts']['new'][3], (3, 3))
        self.assertNotIn(4, files['first.ts']['new'])
        self.assertEqual(files['ä.ts']['new'][2], (2, 2))

    def test_path_with_spaces_from_real_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = lambda *a: subprocess.run(['git', '-C', tmp] + list(a), capture_output=True, text=True, check=True).stdout
            run('init', '-q')
            run('config', 'user.email', 't@t'); run('config', 'user.name', 't')
            Path(tmp, 'x y.md').write_text('a\n')
            Path(tmp, 'ä.md').write_text('a\n')
            run('add', '.'); run('commit', '-qm', 'a')
            Path(tmp, 'x y.md').write_text('a\nb\n')
            Path(tmp, 'ä.md').write_text('a\nb\n')
            files = assemble.parse_diff(run('diff', 'HEAD'))
        self.assertEqual(files['x y.md']['new'][2], (2, 2))
        self.assertEqual(files['ä.md']['new'][2], (2, 2))



class PublishBatchTest(unittest.TestCase):
    FILES = {'index.html': 'i' * 10, 'report.css': 'c' * 20, 'report.js': 'j' * 20, 'manual.js': 'm' * 5,
             'findings-1.js': 'f' * 40, 'findings-2.js': 'f' * 40, 'slots/good.js': 'g' * 30}

    def test_every_batch_sends_the_page_and_holds_the_limit(self):
        batches = assemble.publish_batches(self.FILES, sorted(self.FILES), limit=70)
        self.assertEqual(sorted(n for b in batches for n in b[1:]), sorted(n for n in self.FILES if n != 'index.html'))
        for b in batches:
            self.assertEqual(b[0], 'index.html')
            self.assertLessEqual(sum(len(self.FILES[n]) for n in b), 70, b)

    def test_only_changed_files_are_batched(self):
        self.assertEqual(assemble.publish_batches(self.FILES, ['index.html', 'slots/good.js']), [['index.html', 'slots/good.js']])

    def test_page_alone_is_one_batch(self):
        self.assertEqual(assemble.publish_batches(self.FILES, ['index.html']), [['index.html']])

    def test_file_over_the_limit_gets_a_batch_of_its_own(self):
        batches = assemble.publish_batches(self.FILES, ['index.html', 'report.css', 'findings-1.js'], limit=35)
        self.assertEqual(batches, [['index.html', 'report.css'], ['index.html', 'findings-1.js']])

    def test_pushed_files_cut_at_the_limit(self):
        items = [json.dumps('x' * 10)] * 10
        files = assemble.pushed_files('findings', items, 'V', limit=50)
        self.assertGreater(len(files), 1)
        self.assertEqual(list(files)[0], 'findings-1.js')
        self.assertEqual(sum(f.count('"xxxxxxxxxx"') for f in files.values()), 10)

    def test_pushed_files_one_file_keeps_the_plain_name(self):
        self.assertEqual(list(assemble.pushed_files('findings', ['1', '2'], 'V')), ['findings.js'])


class ColdReadTest(unittest.TestCase):
    """notes.coldRead records the cold read of the GitLab comments (gitlab-comments.md, Cold read)."""

    def setUp(self):
        self.p = Report()

    def tearDown(self):
        self.p.tmp.cleanup()

    def run_ok(self):
        rc = self.p.run()
        self.assertEqual(rc, 0, self.p.out)
        return self.p.out

    def run_fails(self, text):
        rc = self.p.run()
        self.assertEqual(rc, 1, self.p.out)
        self.assertIn(text, self.p.out)

    def test_items_fixed_and_left_pass(self):
        self.p.spec['notes']['coldRead'] = cold_read(1, rounds=2, ref=2, calque=1, left=['F1 calque: the German term is the glossary word'])
        self.run_ok()

    def test_missing_fails_before_publish(self):
        self.p.cold_read = False
        self.run_fails('notes.coldRead missing')

    def test_missing_passes_with_note_after_publish(self):
        self.p.cold_read = False
        self.p.spec['meta']['published'] = True
        self.assertIn('cold read missing: published before the cold read existed', self.run_ok())

    def test_not_needed_without_comments(self):
        self.p.cold_read = False
        self.p.spec['meta']['subjectType'] = 'document'
        self.p.spec['gitlab'] = False
        self.p.spec['verdict']['word'] = 'not accepted'
        self.p.spec.pop('manual')
        self.p.manual = False
        rc = self.p.run()
        self.assertNotIn('coldRead', self.p.out)
        self.assertNotIn('cold read', self.p.out, rc)

    def test_wrong_shape_fails(self):
        self.p.spec['notes']['coldRead'] = dict(cold_read(1), items={'ref': 0, 'calque': 0})
        self.run_fails('notes.coldRead must be')

    def test_third_round_fails(self):
        self.p.spec['notes']['coldRead'] = cold_read(1, rounds=3)
        self.run_fails('notes.coldRead must be')

    def test_comment_count_differs_fails(self):
        self.p.spec['notes']['coldRead'] = cold_read(2)
        self.run_fails('notes.coldRead.comments is 2, but data.json holds 1 GitLab comments')

    def test_unaccounted_item_fails(self):
        self.p.spec['notes']['coldRead'] = cold_read(1, ref=2, fixed=1)
        self.run_fails('fixed (1) plus left (0) is not the 2 items')

    def test_left_needs_finding_type_and_reason(self):
        self.p.spec['notes']['coldRead'] = cold_read(1, ref=1, fixed=0, left=['F9 ref: no such finding'])
        self.run_fails("notes.coldRead.left 'F9 ref: no such finding' is not")
        self.p.spec['notes']['coldRead'] = cold_read(1, ref=1, fixed=0, left=['F1 tone: other type'])
        self.run_fails("notes.coldRead.left 'F1 tone: other type' is not")


class MethodColdReadTest(unittest.TestCase):
    """The method section names the cold read in each language (report-sections.md, 4.2)."""

    def setUp(self):
        self.p = Report()
        self.cr = cold_read(1, ref=2, calque=1, fixed=2, left=['F1 ref: an identifier the rule allows'])
        self.p.spec['notes']['coldRead'] = self.cr
        self.p.method_cold_read = False

    def tearDown(self):
        self.p.tmp.cleanup()

    def method(self, en, de):
        self.p.frags['method'] = twin('<p>Method.</p>', '<p>Methode.</p>') + twin('<p>%s</p>' % en, '<p>%s</p>' % de)

    def run_fails(self, *texts):
        rc = self.p.run()
        self.assertEqual(rc, 1, self.p.out)
        for t in texts:
            self.assertIn(t, self.p.out)

    def test_named_in_both_languages_passes(self):
        self.method('Cold read: 1 comment read, 2 fixed, F1 left.', 'Kalt-Lesen: 1 Kommentar gelesen, 2 behoben, F1 offen.')
        self.assertEqual(self.p.run(), 0, self.p.out)

    def test_missing_counts_fail_in_english(self):
        self.method('Cold read done, F1 left.', 'Kalt-Lesen: 1 Kommentar gelesen, 2 behoben, F1 offen.')
        self.run_fails('method.html: the en text does not name the cold read (notes.coldRead): the 1 comments read; '
                       'the 2 items fixed')

    def test_missing_counts_fail_in_german(self):
        self.method('Cold read: 1 comment read, 2 fixed, F1 left.', 'Kalt-Lesen erledigt, F1 offen.')
        self.run_fails('the de text does not name the cold read', 'the 1 comments read; the 2 items fixed')

    def test_missing_left_id_fails_in_english(self):
        self.method('Cold read: 1 comment read, 2 fixed, one left.', 'Kalt-Lesen: 1 Kommentar gelesen, 2 behoben, F1 offen.')
        self.run_fails('the en text does not name the cold read (notes.coldRead): F1, which has an item left')

    def test_missing_left_id_fails_in_german(self):
        self.method('Cold read: 1 comment read, 2 fixed, F1 left.', 'Kalt-Lesen: 1 Kommentar gelesen, 2 behoben, eins offen.')
        self.run_fails('the de text does not name the cold read (notes.coldRead): F1, which has an item left')

    def test_count_inside_another_number_does_not_count(self):
        self.method('Cold read of 12 comments, 22 fixed, F1 left.', 'Kalt-Lesen: 1 Kommentar gelesen, 2 behoben, F1 offen.')
        self.run_fails('the en text does not name the cold read (notes.coldRead): the 1 comments read; the 2 items fixed')

    def test_no_check_without_a_cold_read(self):
        self.p.spec['notes'].pop('coldRead')
        self.p.cold_read = False
        self.p.spec['meta']['published'] = True
        self.assertEqual(self.p.run(), 0, self.p.out)


class MethodWithdrawnTest(unittest.TestCase):
    """The method section names every id withdrawn after publish in each language (report-sections.md, 4.2)."""

    def setUp(self):
        self.p = Report()
        self.p.findings = [finding('F1'), finding('F3', sev='nit')]
        self.p.spec['meta']['published'] = True
        self.p.spec['notes']['withdrawn'] = ['F2: merged into F1 after the first publish']
        self.p.method_withdrawn = False

    def tearDown(self):
        self.p.tmp.cleanup()

    def method(self, en, de):
        self.p.frags['method'] = twin('<p>Method.</p>', '<p>Methode.</p>') + twin('<p>%s</p>' % en, '<p>%s</p>' % de)

    def test_named_in_both_languages_passes(self):
        self.method('F2 was merged into F1.', 'F2 ging in F1 auf.')
        self.assertEqual(self.p.run(), 0, self.p.out)

    def test_missing_in_english_fails(self):
        self.method('One finding was merged into F1.', 'F2 ging in F1 auf.')
        self.assertEqual(self.p.run(), 1, self.p.out)
        self.assertIn('method.html: the en text does not name F2, withdrawn after publish (notes.withdrawn; '
                      'report-sections.md, 4.2)', self.p.out)
        self.assertNotIn('the de text does not name F2', self.p.out)

    def test_missing_in_german_fails(self):
        self.method('F2 was merged into F1.', 'Ein Finding ging in F1 auf.')
        self.assertEqual(self.p.run(), 1, self.p.out)
        self.assertIn('method.html: the de text does not name F2, withdrawn after publish', self.p.out)

    def test_no_check_without_withdrawn(self):
        self.p.findings = [finding('F1'), finding('F2', sev='nit')]
        self.p.spec['notes']['withdrawn'] = []
        self.assertEqual(self.p.run(), 0, self.p.out)


class PlaceholderTest(unittest.TestCase):
    """No TODO-DE is left in data.json, a fragment or manual.json (tooling.md, Translator)."""

    def setUp(self):
        self.p = Report()
        self.c = card(self.p.findings[0], [comment()])
        self.p.cards = [self.c]

    def tearDown(self):
        self.p.tmp.cleanup()

    def run_fails(self, text):
        rc = self.p.run()
        self.assertEqual(rc, 1, self.p.out)
        self.assertIn(text, self.p.out)

    def test_filled_report_passes(self):
        self.assertEqual(self.p.run(), 0, self.p.out)

    def test_data_field_fails(self):
        self.c['t'][1] = 'TODO-DE'
        self.run_fails('F1: t[1] in data.json holds the placeholder TODO-DE: the translator fills it')

    def test_field_text_fails(self):
        self.c['fields']['what']['text'][1] = 'TODO-DE'
        self.run_fails('F1: fields.what.text[1] in data.json holds the placeholder TODO-DE')

    def test_field_more_fails(self):
        self.c['fields']['verify']['more'][1] = '`src/a.ts:11` gelesen. TODO-DE'
        self.run_fails('F1: fields.verify.more[1] in data.json holds the placeholder TODO-DE')

    def test_gitlab_text_fails(self):
        self.c['gitlab'][0]['text'][1] = 'TODO-DE'
        self.run_fails('F1: gitlab[0].text[1] in data.json holds the placeholder TODO-DE')

    def test_fragment_fails(self):
        self.p.frags['questions'] = twin('<p>No open questions.</p>', '<p>TODO-DE</p>')
        self.run_fails('questions.html line 1 holds the placeholder TODO-DE: the translator fills it')

    def test_manual_json_fails(self):
        self.p.manual = manual_json(self.p.spec['manual'])
        self.p.manual['steps'][0]['expect'][1] = 'TODO-DE'
        self.run_fails('manual.json M1.expect[1] holds the placeholder TODO-DE')


COLD_DIFF ="""diff --git a/src/a.ts b/src/a.ts
index 1..2 100644
--- a/src/a.ts
+++ b/src/a.ts
@@ -10,4 +10,4 @@
 keep 10
-gone 11
+new 11
 keep 12
 keep 13
"""


class ColdReadInputTest(unittest.TestCase):
    """cold_read_input.py: the comments beside their code, labelled without ids, one language per packet."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sp = Path(self.tmp.name)
        self.wt = self.sp / 'wt'
        (self.wt / 'src').mkdir(parents=True)
        (self.wt / 'src' / 'a.ts').write_text(''.join('line %d\n' % n for n in range(1, 41)))
        (self.sp / 'report').mkdir()
        (self.sp / 'inputs' / 'sources').mkdir(parents=True)
        (self.sp / 'inputs' / 'change.diff').write_text(COLD_DIFF)
        self.cards = [
            card(finding('F1'), [comment(startLine=11, endLine=12, en='EN one `x`.', de='DE eins `x`.')]),
            card(finding('F2', sev='optional'), [comment(startLine=11, side='old', en='EN old.', de='DE alt.'),
                                                 comment(anchor='file', startLine=30, en='EN file.', de='DE Datei.')]),
            card(finding('F3', sev='nit'), [comment(path=None, startLine=None, anchor='mr', en='EN mr.', de='DE MR.')]),
        ]
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self):
        (self.sp / 'report' / 'data.json').write_text(json.dumps(self.cards, ensure_ascii=False))

    def call(self, *args):
        out = subprocess.run([sys.executable, '-I', str(HERE / 'cold_read_input.py'), *args], capture_output=True, text=True)
        return out.returncode, out.stdout + out.stderr

    def build(self, *extra):
        rc, out = self.call(str(self.sp / 'report'), str(self.wt), *extra)
        self.assertEqual(rc, 0, out)
        return out

    def state(self, name):
        return (self.sp / 'state' / name).read_text()

    def test_labels_carry_no_id_or_severity(self):
        self.build()
        en = self.state('cold-read-input-en.md')
        self.assertEqual(re.findall(r'^## (C\d+)', en, flags=re.M), ['C1', 'C2', 'C3', 'C4'])
        for word in ('F1', 'F2', 'F3', 'blocker', 'optional', 'nit', 'Blocker', 'Optional', 'Nit'):
            self.assertNotIn(word, en)
        labels = json.loads(self.state('cold-read-labels.json'))
        self.assertEqual([labels[k]['finding'] for k in ('C1', 'C2', 'C3', 'C4')], ['F1', 'F2', 'F2', 'F3'])

    def test_sections_split_by_language(self):
        self.build()
        en = self.state('cold-read-input-en.md')
        self.assertIn('EN one', en)
        self.assertNotIn('DE eins', en)
        self.assertFalse((self.sp / 'state' / 'cold-read-input-de.md').exists())

    def test_german_only_after_english_notes(self):
        self.build()
        rc, out = self.call('--de', str(self.sp / 'report'), str(self.wt))
        self.assertEqual(rc, 1, out)
        self.assertIn('write the English notes to', out)
        (self.sp / 'state' / 'cold-read-en.md').write_text('## C1\nclaim: …\nok\n')
        rc, out = self.call('--de', str(self.sp / 'report'), str(self.wt))
        self.assertEqual(rc, 0, out)
        de = self.state('cold-read-input-de.md')
        self.assertIn('DE eins', de)
        self.assertNotIn('EN one', de)

    def test_line_range_marked_from_worktree(self):
        self.build()
        c1 = self.state('cold-read-input-en.md').split('## C2')[0]
        self.assertIn('src/a.ts:11–12', c1)
        self.assertIn('>11 | line 11', c1)
        self.assertIn('>12 | line 12', c1)
        self.assertIn(' 13 | line 13', c1)
        self.assertIn('  1 | line 1\n', c1)
        self.assertIn(' 24 | line 24', c1)
        self.assertNotIn('line 25', c1)

    def test_old_side_from_diff(self):
        self.build()
        c2 = self.state('cold-read-input-en.md').split('## C2')[1].split('## C3')[0]
        self.assertIn('old side', c2)
        self.assertIn('>11 | gone 11', c2)
        self.assertIn(' 10 | keep 10', c2)
        self.assertNotIn('line 11', c2)

    def test_file_anchor_shows_its_line(self):
        self.build()
        c3 = self.state('cold-read-input-en.md').split('## C3')[1].split('## C4')[0]
        self.assertIn('src/a.ts:30', c3)
        self.assertIn('>30 | line 30', c3)

    def test_mr_anchor_gets_description_or_says_none(self):
        self.build()
        c4 = self.state('cold-read-input-en.md').split('## C4')[1]
        self.assertIn('no merge request description', c4)
        self.assertNotIn(' | ', c4)
        (self.sp / 'inputs' / 'sources' / 'mr-description.md').write_text('# MR !1: Add counts\n\nCounts things.\n')
        self.build()
        c4 = self.state('cold-read-input-en.md').split('## C4')[1]
        self.assertIn('Counts things.', c4)

    def test_fence_holds_a_suggestion_block(self):
        self.cards[0]['gitlab'][0]['text'][0] = 'Reword.\n\n```suggestion:-0+0\nnew\n```'
        self.write()
        self.build()
        c1 = self.state('cold-read-input-en.md').split('## C2')[0]
        self.assertIn('````text\nReword.', c1)

    def test_second_round_takes_changed_comments_only(self):
        self.build()
        self.cards[1]['gitlab'][1]['text'][0] = 'EN file, reworded.'
        self.write()
        out = self.build('--name', 'cold-read-2', '--since', 'cold-read')
        self.assertIn('1 comments', out)
        en2 = self.state('cold-read-2-input-en.md')
        self.assertEqual(re.findall(r'^## (C\d+)', en2, flags=re.M), ['C3'])


if __name__ == '__main__':
    unittest.main(verbosity=1)
