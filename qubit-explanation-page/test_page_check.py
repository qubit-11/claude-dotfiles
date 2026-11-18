#!/usr/bin/env python3
"""Tests for page_check.py and render_check.py. Run: python3 test_page_check.py"""
import contextlib
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import render_check  # noqa: E402

def twin(en, de, tag='div'):
    return '<%s data-lang="en">%s</%s><%s data-lang="de">%s</%s>' % (tag, en, tag, tag, de, tag)


def disclosure(en='Visible.', de='Sichtbar.', body_en='Why <code>src/a.ts:11</code>.', body_de='Warum <code>src/a.ts:11</code>.'):
    """A paragraph with details: the paragraph is the summary, the details its .more-body."""
    return ('<details class="pt"><summary><span data-lang="en" class="ptxt">%s</span><span data-lang="de" class="ptxt">%s</span>'
            '<span class="chev" aria-hidden="true"></span></summary><div class="more-body">%s</div></details>\n'
            % (en, de, twin('<p>%s</p>' % body_en, '<p>%s</p>' % body_de, 'div')))


def paras():
    """A plain paragraph, then one with details that cites a source."""
    return twin('Plain paragraph.', 'Einfacher Absatz.', 'p') + '\n' + disclosure()


def subsec(sid, en='Title', de='Titel', body=None):
    return '<div id="%s" class="subsec">\n<h3>%s</h3>\n%s</div>\n' % (sid, twin(en, de, 'span'), body or paras())


class UsageTest(unittest.TestCase):
    def test_wrong_call_prints_usage(self):
        for args in [[], ['--check-page'], ['a.html', 'b.html']]:
            out = subprocess.run([sys.executable, str(HERE / 'page_check.py')] + args, capture_output=True, text=True)
            self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
            self.assertIn('Usage', out.stdout)


class CheckPageTest(unittest.TestCase):
    """page_check.py runs the page checks on a whole explanation page."""
    SKELETON = HERE / 'page-skeleton.html'

    TOC = ('<nav class="toc" aria-label="Contents / Inhalt">\n  <ol>\n'
           '    <li><a href="#background">%s</a><ol class="toc-sub"><li><a href="#today">%s</a></li></ol></li>\n'
           '    <li><a href="#subject">%s</a><ol class="toc-sub"><li><a href="#goal">%s</a></li><li><a href="#approach">%s</a></li><li><a href="#flow">%s</a></li></ol></li>\n'
           '    <li><a href="#glossary">%s</a></li>\n  </ol>\n</nav>') % (
        twin('Background', 'Hintergrund', 'span'), twin('Title', 'Titel', 'span'), twin('The topic', 'Das Thema', 'span'),
        twin('Title', 'Titel', 'span'), twin('Title', 'Titel', 'span'), twin('Title', 'Titel', 'span'),
        twin('Glossary', 'Glossar', 'span'))

    def page(self, extra='', toc=None):
        main = ('<main>\n<h1>%s</h1>\n<section id="background"><h2>%s</h2>\n%s</section>\n'
                '<section id="subject"><h2>%s</h2>\n%s%s%s</section>\n<section id="glossary"><h2>%s</h2>\n%s</section>\n%s</main>') % (
            twin('Title', 'Titel', 'span'), twin('Background', 'Hintergrund', 'span'), subsec('today'),
            twin('The topic', 'Das Thema', 'span'), subsec('goal'), subsec('approach'), subsec('flow'),
            twin('Glossary', 'Glossar', 'span'),
            twin('<dl class="gl"><dt>A</dt><dd>B</dd></dl>', '<dl class="gl"><dt>A</dt><dd>B</dd></dl>'), extra)
        text = self.SKELETON.read_text()
        text = re.sub(r'<nav class="toc".*?</nav>', lambda m: toc or self.TOC, text, count=1, flags=re.S)
        return text[:text.index('<main>')] + main + text[text.index('</main>') + len('</main>'):]

    def test_page_structure_fails(self):
        good = self.page()
        drop_glossary = re.sub(r'<section id="glossary">.*?</section>', '', good, count=1, flags=re.S)
        for html, msg in [(drop_glossary, 'it needs exactly background, subject, glossary in this order')]:
            with self.subTest(msg=msg):
                rc, out = self.run_check(html)
                self.assertEqual(rc, 1, out)
                self.assertIn(msg, out)

    def test_fixed_subsections_and_exact_sections(self):
        good = self.page()
        no_today = good.replace(subsec('today'), subsec('basics-x'), 1).replace('href="#today"', 'href="#basics-x"', 1)
        extra = good.replace('<section id="glossary">', '<section id="extra"><h2>%s</h2>\n%s</section>\n<section id="glossary">' % (
            twin('Extra', 'Extra', 'span'), twin('<p>An added section.</p>', '<p>Ein hinzugefügter Abschnitt.</p>')), 1)
        for html, msg in [(no_today, '#background: subsection #today missing'),
                          (extra, 'it needs exactly background, subject, glossary')]:
            with self.subTest(msg=msg):
                rc, out = self.run_check(html)
                self.assertEqual(rc, 1, out)
                self.assertIn(msg, out)

    def run_check(self, html):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp, 'page.html')
            f.write_text(html)
            out = subprocess.run([sys.executable, str(HERE / 'page_check.py'), str(f)], capture_output=True, text=True)
        return out.returncode, out.stdout + out.stderr

    def test_filled_skeleton_passes(self):
        rc, out = self.run_check(self.page())
        self.assertEqual(rc, 0, out)
        self.assertIn('OK', out)

    def test_broken_pages_fail(self):
        no_cite = subsec('basics-z', body=disclosure(body_de='Siehe den Code.'))
        for extra, msg in [('<div data-lang="en"><p>Only English.</p></div>', 'twin'),
                           ('<p>Untagged.</p>', 'text outside a language block'),
                           (no_cite, '#basics-z cites no source in the de view'),
                           (twin('<p id="goal">x</p>', '<p>x</p>'), 'id "goal" occurs more than once'),
                           (twin('<img src="https://e.example/x.png">', '<p>x</p>'), 'active content')]:
            with self.subTest(msg=msg):
                rc, out = self.run_check(self.page(extra))
                self.assertEqual(rc, 1, out)
                self.assertIn(msg, out)

    def test_paragraph_rules(self):
        """One level of details, never nested; figures and file:line where they belong; short details."""
        fig = '<figure><svg viewBox="0 0 10 10"><rect x="0" y="0" width="5" height="5"/></svg>%s</figure>' % (
            twin('Figure.', 'Abbildung.', 'span'))
        nested = disclosure().replace('<div class="more-body">', '<div class="more-body">' + disclosure(), 1)
        fig_inside = disclosure().replace('<div class="more-body">', '<div class="more-body">' + fig, 1)
        visible_ref = twin('See <code>src/b.ts:4</code>.', 'Siehe <code>src/b.ts:4</code>.', 'p') + disclosure()
        one_lang = disclosure().replace('<span data-lang="de" class="ptxt">Sichtbar.</span>', '', 1)
        refs = ' '.join('<code>src/f%d.ts:1</code>' % i for i in range(4))
        many = disclosure(body_en=refs, body_de=refs)
        bare = disclosure(body_en='<code>src/a.ts:11</code>, :12, :20-24, :30', body_de='<code>src/a.ts:11</code>, :12, :20-24, :30')
        wall = disclosure(body_en='<code>src/a.ts:11</code> ' + ' '.join(['word'] * 101), body_de='<code>src/a.ts:11</code> Kurz.')
        stray = twin('<div class="more-body"><p>Loose.</p></div>', '<div class="more-body"><p>Lose.</p></div>') + disclosure()
        for body, msg in [(nested, 'a details.pt in #concept-x holds another one'),
                          (fig_inside, 'a figure or table inside a details.pt in #concept-x'),
                          (disclosure().replace('<div class="more-body">', '<div class="more-body"><div class="tbl"><table><tr><td>'
                                                '<span data-lang="en">x</span><span data-lang="de">x</span></td></tr></table></div>', 1),
                           'a figure or table inside a details.pt in #concept-x'),
                          (visible_ref, 'the en visible text of #concept-x names src/b.ts:4'),
                          (one_lang, 'needs the paragraph as one EN and one DE .ptxt, has en'),
                          (many, 'the en details of a paragraph in #concept-x name 4 source references, at most 3'),
                          (bare, 'the en details of a paragraph in #concept-x name 4 source references, at most 3'),
                          (wall, 'a en paragraph in the details of #concept-x has 101 words, at most 100'),
                          (stray, 'a .more-body in #concept-x stands outside a details.pt'),
                          (twin(' '.join(['word'] * 81), ' '.join(['Wort'] * 20), 'p') + disclosure(),
                           'a en visible paragraph of #concept-x has 81 words, at most 80'),
                          (disclosure(en=' '.join(['word'] * 81)), 'a en visible paragraph of #concept-x has 81 words, at most 80'),
                          (('<div class="callout">%s</div>' % twin('Key.', 'Kern.', 'p')) * 2 + paras(), '#concept-x has 2 callouts, at most 1'),
                          (disclosure().replace('<div class="more-body">', '<div class="more-body"><div class="callout">%s</div>'
                                                % twin('Key.', 'Kern.', 'p'), 1), 'a callout inside the details of #concept-x')]:
            with self.subTest(msg=msg):
                rc, out = self.run_check(self.page(subsec('concept-x', body=body)))
                self.assertEqual(rc, 1, out)
                self.assertIn(msg, out)
        rc, out = self.run_check(self.page(subsec('concept-x', body=fig + paras())))
        self.assertEqual(rc, 0, out)

    def test_skeleton_as_shipped_passes(self):
        rc, out = self.run_check(self.SKELETON.read_text())
        self.assertEqual(rc, 0, out)

    def test_table_of_contents_must_match_the_sections(self):
        flow = '<li><a href="#flow">%s</a></li>' % twin('Title', 'Titel', 'span')
        goal = '<li><a href="#goal">%s</a></li>' % twin('Title', 'Titel', 'span')
        arch = '<li><a href="#approach">%s</a></li>' % twin('Title', 'Titel', 'span')
        have = 'the page has goal, approach, flow'
        for toc, msg in [(self.TOC.replace(flow, ''), 'under #subject lists goal, approach, ' + have),
                         (self.TOC.replace(goal + arch, arch + goal), 'under #subject lists approach, goal, flow, ' + have),
                         (self.TOC.replace('<li><a href="#glossary">', '<li><a href="#extra">x</a></li><li><a href="#glossary">'),
                          'lists the sections background, subject, extra, glossary, the page has background, subject, glossary'),
                         (self.TOC.replace('class="toc"', 'class="contents"'), '0 nav.toc elements, needs 1')]:
            with self.subTest(msg=msg):
                rc, out = self.run_check(self.page(toc=toc))
                self.assertEqual(rc, 1, out)
                self.assertIn(msg, out)

    def test_untagged_brand_fails(self):
        html = self.page().replace('<div class="brand"><span data-lang="en">Topic Name</span><span data-lang="de">Thema</span></div>',
                                   '<div class="brand">Topic Name</div>')
        self.assertIn('<div class="brand">Topic Name</div>', html)
        rc, out = self.run_check(html)
        self.assertEqual(rc, 1, out)
        self.assertIn('text outside a language block', out)
        rc, out = self.run_check(self.page().replace('</main>', '</main>\n<footer>Untagged footer.</footer>'))
        self.assertEqual(rc, 1, out)
        self.assertIn('text outside a language block', out)

    def test_missing_file_fails(self):
        rc, out = self.run_check('')
        self.assertEqual(rc, 1, out)


class RenderCheckTest(unittest.TestCase):
    def test_probe_is_appended_without_body_tag(self):
        page = render_check.with_probe('<p>x</p>\n<script>var a = 1;</script>')
        self.assertTrue(page.startswith('<!doctype html>'))
        self.assertTrue(page.endswith(render_check.PROBE))
        self.assertIn('var a = 1;</script>' + render_check.PROBE, page)

    def run_main(self, chrome='/fake/chrome', probe=None):
        """render_check.main with Chrome and the probe stubbed; returns (exit code, output)."""
        saved = render_check.chrome, render_check.probe, sys.argv
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp, 'page.html')
            page.write_text('<p>x</p>')
            render_check.chrome = lambda: chrome
            render_check.probe = probe or (lambda *a, **k: None)
            sys.argv = ['render_check.py', str(page)]
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    rc = render_check.main()
            finally:
                render_check.chrome, render_check.probe, sys.argv = saved
        return rc, buf.getvalue()

    def test_missing_chrome_exits_2(self):
        rc, out = self.run_main(chrome=None)
        self.assertEqual(rc, 2, out)
        self.assertIn('no Chrome', out)

    def test_probe_without_result_exits_2(self):
        rc, out = self.run_main()
        self.assertEqual(rc, 2, out)
        self.assertIn('probe failed', out)

    def test_malformed_probe_output_exits_2(self):
        for res in ['en:abc/1280', 'en', 'en:12']:
            with self.subTest(res=res):
                rc, out = self.run_main(probe=lambda *a, **k: res)
                self.assertEqual(rc, 2, out)
                self.assertIn('probe failed', out)

    def test_overflow_at_1280_exits_1(self):
        rc, out = self.run_main(probe=lambda b, url, width, *a, **k: 'en:%d/%d' % ((1300, 1280) if width == 1280 else (390, 390)))
        self.assertEqual(rc, 1, out)
        self.assertIn('1280 px: en:1300/1280 OVERFLOW', out)
        self.assertIn('390 px: en:390/390\n', out)

    def test_chrome_timeout_is_a_failed_probe(self):
        saved = render_check.subprocess.run
        def timeout(*a, **k):
            raise subprocess.TimeoutExpired('chrome', 120)
        render_check.subprocess.run = timeout
        try:
            self.assertIsNone(render_check.probe('/fake/chrome', 'file:///x', 1280, '/tmp/p'))
        finally:
            render_check.subprocess.run = saved

class ProbeResultTest(unittest.TestCase):
    def test_incomplete_probe_is_no_pass(self):
        with self.assertRaises(ValueError):
            render_check.overflows('incomplete')


if __name__ == '__main__':
    unittest.main()
