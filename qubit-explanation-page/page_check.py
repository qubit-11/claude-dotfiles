#!/usr/bin/env python3
"""Check a qubit-explanation-page page, and the page checks a calling skill reuses for its own fragments.

Usage: python3 page_check.py <page.html>
Checks a whole standalone explanation page: exactly one <main> with exactly the sections background, subject and
glossary in this order; the fixed subsections #today, #goal, #approach and #flow present and first in their
sections; every .subsec with an id and an <h3> first; the paragraph disclosures (details.pt: one level, never nested,
a summary with the paragraph in both languages, one .more-body, no figure or table in either); no file:line and no paragraph over VISIBLE_PARAGRAPH_MAX words in the visible
text; in the details at most DETAIL_REFS_MAX references per disclosure and DETAIL_PARAGRAPH_MAX words per paragraph; a
citation in every subsection; language twins and untranslated German twins; text outside a language block; the
hand-written table of contents against the sections and subsections of <main>; duplicate ids; duplicate attributes
and active content in <main>. Prints only its check result; exit code 1 on a problem, 2 on a wrong call.

A calling skill imports the checks (parse_html, check_twins, check_paragraphs, check_citations, active_content, ...) and
shares `errors`: `fail` collects into it, `result` prints and returns the exit code.
"""
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

REQUIRED_IDS = {'background': ['today'], 'subject': ['goal', 'approach', 'flow']}
# the details of a paragraph name the central places only; more references make them a file index, not an explanation
DETAIL_REFS_MAX = 3
# a paragraph in the details explains one point; longer ones read as a wall of text
DETAIL_PARAGRAPH_MAX = 100
# a visible paragraph makes one point in two to four sentences; longer ones are a wall of text
VISIBLE_PARAGRAPH_MAX = 80
# a bare line reference after a file:line in the same block (":85", ":96-101") counts as one more reference
BARE_LINE = re.compile(r'(?<![\w.:/-]):\d+(?:-\d+)?\b')
# the top-level sections of every qubit-explanation-page page, in order
FIXED_SECTIONS = ['background', 'subject', 'glossary']
# a source reference: a path with a / whose last part has an extension (docker/api.Dockerfile:3, a/.gitlab-ci.yml:2),
# a bare file name with a known source extension (SKILL.md:12) or a dotfile (.gitignore:2), or a known extensionless file
# (Dockerfile:3); a host:port (redis:6379, api.example.com:443) and a URL are none
FILE_EXTS = ('ts', 'tsx', 'mts', 'cts', 'js', 'jsx', 'mjs', 'cjs', 'py', 'md', 'html', 'htm', 'css', 'scss', 'json',
             'yaml', 'yml', 'toml', 'ini', 'cfg', 'conf', 'sh', 'zsh', 'bash', 'sql', 'txt', 'xml', 'svg', 'java', 'kt',
             'groovy', 'go', 'rs', 'rb', 'php', 'c', 'h', 'cpp', 'hpp', 'cs', 'swift', 'vue', 'svelte', 'j2', 'njk',
             'mjml', 'hbs', 'env', 'properties', 'gradle', 'lock', 'bru', 'c4', 'likec4', 'diff', 'patch', 'csv')
FILE_LINE = re.compile(r'(?<![\w./:-])(?:(?:[\w.-]+/)+[\w.-]*\.[A-Za-z][\w-]*'
                       r'|[\w.-]*\.(?:%s)|\.[\w.-]+'
                       r'|(?:[\w.-]+\.)?(?:Dockerfile|Makefile|Jenkinsfile|Procfile|Gemfile|Containerfile))'
                       r':\d+' % '|'.join(FILE_EXTS))
NEUTRAL_TAGS = {'svg', 'code', 'pre', 'kbd', 'samp'}
LETTER = re.compile(r'[A-Za-zÄÖÜäöüß]')
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr',
        'path', 'line', 'rect', 'circle', 'ellipse', 'polyline', 'polygon', 'use', 'stop'}
# the HTML parser lowercases tag names, so SVG's animateMotion arrives as animatemotion
ACTIVE_TAGS = {'script', 'iframe', 'frame', 'object', 'embed', 'link', 'meta', 'base', 'form', 'applet',
               'animate', 'set', 'animatemotion', 'animatetransform'}
BAD_URL = re.compile(r'(?i)^(?:javascript:|vbscript:|data:text/html)')
URL_ATTRS = {'href', 'xlink:href', 'src', 'srcset', 'action', 'formaction', 'poster', 'background', 'data'}
# attributes that load a resource; href loads one on every tag but <a>, which only links to a page
LOAD_ATTRS = {'src', 'srcset', 'poster', 'background', 'data'}
EXTERNAL = re.compile(r'(?i)^\s*(?:https?:|//)')
# every CSS function that loads a resource, unless it points into the page (#id); the CSS is decoded first
BAD_CSS = re.compile(r'(?i)@import|expression\(|(?<![\w-])(?:url|src|image|image-set|-webkit-image-set|cross-fade)\((?!\s*["\']?\s*#)')
CSS_ESCAPE = re.compile(r'\\(?:([0-9a-fA-F]{1,6})[ \t\r\n\f]?|(\r\n|[\n\r\f])|(.))', re.S)
# the attributes a browser reads as CSS: style, and the SVG presentation attributes that take a url()
CSS_ATTRS = {'style', 'fill', 'stroke', 'filter', 'mask', 'clip-path', 'marker-start', 'marker-mid', 'marker-end', 'cursor'}
errors = []


def fail(msg):
    errors.append(msg)


def result(head):
    print(head)
    if errors:
        print('FAILED, %d problem(s):' % len(errors))
        for e in errors:
            print('- ' + e)
        return 1
    return 0


class Tree(HTMLParser):
    """A minimal element tree: tag, attributes, children, text, and `seq`, text and children in document order."""

    def __init__(self, text=''):
        super().__init__(convert_charrefs=True)
        self.root = {'tag': '', 'attrs': {}, 'children': [], 'text': [], 'seq': []}
        self.stack = [self.root]
        # offset of each line, so a node can record where its inner markup lies in the source (`inner`)
        self.lines = [0] + [m.end() for m in re.finditer('\n', text)]

    def source_pos(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def add(self, node):
        self.stack[-1]['children'].append(node)
        self.stack[-1]['seq'].append(node)

    @staticmethod
    def node(tag, attrs):
        # a browser keeps the first of two equal attributes; a value-less attribute (<div class>) counts as ''
        kept = {}
        for k, v in attrs:
            kept.setdefault(k, v or '')
        return {'tag': tag, 'attrs': kept, 'dup': len(kept) < len(attrs), 'children': [], 'text': [], 'seq': []}

    def handle_starttag(self, tag, attrs):
        node = self.node(tag, attrs)
        node['start'] = self.source_pos() + len(self.get_starttag_text() or '')
        self.add(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.add(self.node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i]['tag'] == tag:
                self.stack[i]['inner'] = (self.stack[i]['start'], self.source_pos())
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1]['text'].append(data)
        self.stack[-1]['seq'].append(data)


def parse_html(text):
    t = Tree(text)
    t.feed(text)
    t.close()
    return t.root


def walk(node):
    yield node
    for c in node['children']:
        yield from walk(c)


def text_of(node):
    return ''.join(x if isinstance(x, str) else text_of(x) for x in node.get('seq', []))


def strip_code(text):
    return re.sub(r'`[^`]*`', ' ', re.sub(r'```.*?```', ' ', text, flags=re.S))


def prose_words(text):
    """The words of a text that a translation changes: code, file:line references and links left out."""
    text = re.sub(r'(?i)\b[a-z][a-z0-9+.-]*://\S+', ' ', FILE_LINE.sub(' ', strip_code(text)))
    # a word is letters only: names like DB_PASSWORD, a.b or camelCase stay the same in both languages
    words = (t.strip('.,;:!?()[]{}"\'«»„“”–—…') for t in text.split())
    return [w for w in words if re.fullmatch(r"[A-ZÄÖÜa-zäöüß][a-zäöüß'-]+", w)]


def untranslated(en, de):
    """True when the German text is the English one and holds prose (three words or more, one of them in lower
    case); names and code stay the same in both languages."""
    words = prose_words(en)
    return ' '.join(en.split()) == ' '.join(de.split()) and len(words) >= 3 and any(w[0].islower() for w in words)


def prose_of(node):
    """The text of a node without its language-neutral parts (diagrams, code)."""
    return ''.join(x if isinstance(x, str) else '' if x['tag'] in NEUTRAL_TAGS else prose_of(x) for x in node.get('seq', []))


def check_twins(name, root):
    """Every data-lang="en" element is directly followed by its data-lang="de" twin, same tag, and vice versa;
    neither twin may be empty, and the German one is no copy of the English text."""
    for node in walk(root):
        kids = node['children']
        for i, k in enumerate(kids):
            lang = k['attrs'].get('data-lang')
            if lang == 'en':
                nxt = kids[i + 1] if i + 1 < len(kids) else None
                if not nxt or nxt['attrs'].get('data-lang') != 'de' or nxt['tag'] != k['tag']:
                    fail('%s.html: an English <%s> has no German twin right after it' % (name, k['tag']))
                elif k['tag'] not in VOID and (not text_of(k).strip() or not text_of(nxt).strip()):
                    fail('%s.html: an English <%s> and its German twin: one or both are empty' % (name, k['tag']))
                elif untranslated(prose_of(k), prose_of(nxt)):
                    fail('%s.html: the German twin of an English <%s> is the English text' % (name, k['tag']))
            elif lang == 'de':
                prev = kids[i - 1] if i > 0 else None
                if not prev or prev['attrs'].get('data-lang') != 'en':
                    fail('%s.html: a German <%s> has no English twin right before it' % (name, k['tag']))


def check_fixed(name, scope, rids):
    """The fixed subsections (1.1; 2.1 to 2.3) exist and come first, in this order, so their numbers never shift."""
    subs = [n['attrs'].get('id') for n in walk(scope) if 'subsec' in n['attrs'].get('class', '').split()]
    for rid in rids:
        if rid not in subs:
            fail('%s: subsection #%s missing' % (name, rid))
    if all(r in subs for r in rids) and subs[:len(rids)] != rids:
        fail('%s: the subsections start %s; the fixed ones (%s) come first, in this order' % (
            name, ', '.join('#' + str(i) for i in subs[:len(rids)]), ', '.join('#' + r for r in rids)))


def has_class(node, cls):
    return cls in node['attrs'].get('class', '').split()


def is_subsec(node):
    return has_class(node, 'subsec')


def is_disclosure(node):
    """A paragraph with details: details.pt, its summary the visible paragraph, its .more-body the details."""
    return node['tag'] == 'details' and has_class(node, 'pt')


def without_details(node):
    """The node as a reader sees it with every disclosure closed: the .more-body subtrees left out."""
    keep = lambda x: isinstance(x, str) or not has_class(x, 'more-body')
    seq = [x if isinstance(x, str) else without_details(x) for x in node.get('seq', []) if keep(x)]
    return dict(node, seq=seq, children=[x for x in seq if not isinstance(x, str)])


def check_paragraphs(name, root):
    """The paragraph disclosures: one level, never nested; the summary first, holding the paragraph as an EN and a DE
    .ptxt; exactly one .more-body after it; no figure or table in the summary or the details; a .more-body only inside a
    disclosure. In every .subsec: no file:line and no paragraph over VISIBLE_PARAGRAPH_MAX words in the visible text,
    and per disclosure and language at most
    DETAIL_REFS_MAX distinct references and at most DETAIL_PARAGRAPH_MAX words per paragraph of the details."""
    for n in walk(root):
        if has_class(n, 'more-body') and not any(is_disclosure(d) and any(c is n for c in d['children']) for d in walk(root)):
            fail('%s.html: a .more-body in #%s stands outside a details.pt' % (name, subsec_of(root, n)))
        if not is_disclosure(n):
            continue
        sid = subsec_of(root, n)
        if any(is_disclosure(d) for d in walk(n) if d is not n):
            fail('%s.html: a details.pt in #%s holds another one; details open one level, never nested' % (name, sid))
        kids = n['children']
        summary = kids[0] if kids and kids[0]['tag'] == 'summary' else None
        if summary is None:
            fail('%s.html: a details.pt in #%s does not start with its summary' % (name, sid))
            continue
        langs = sorted(c['attrs'].get('data-lang', '') for c in summary['children'] if has_class(c, 'ptxt'))
        if langs != ['de', 'en']:
            fail('%s.html: a details.pt summary in #%s needs the paragraph as one EN and one DE .ptxt, has %s'
                 % (name, sid, ', '.join(langs) or 'none'))
        bodies = [c for c in kids[1:] if has_class(c, 'more-body')]
        if len(bodies) != 1 or len(kids) != 2:
            fail('%s.html: a details.pt in #%s needs its summary and exactly one .more-body, nothing else' % (name, sid))
        if any(d['tag'] in ('figure', 'svg', 'table') for part in [summary] + bodies for d in walk(part)):
            fail('%s.html: a figure or table inside a details.pt in #%s; figures and tables stand in the visible text'
                 % (name, sid))
    for n in walk(root):
        if not is_subsec(n):
            continue
        sid = n['attrs'].get('id', '?')
        visible = without_details(n)
        callouts = [d for d in walk(n) if has_class(d, 'callout')]
        if len(callouts) > 1:
            fail('%s.html: #%s has %d callouts, at most 1: a highlight works only when it is the one point'
                 % (name, sid, len(callouts)))
        if any(has_class(d, 'callout') for b in walk(n) if has_class(b, 'more-body') for d in walk(b)):
            fail('%s.html: a callout inside the details of #%s; it marks a point of the visible text' % (name, sid))
        for lang in ['en', 'de']:
            vis = view(visible, lang)
            refs = sorted(set(FILE_LINE.findall(text_of(vis))))
            if refs:
                fail('%s.html: the %s visible text of #%s names %s; file:line belongs in the details'
                     % (name, lang, sid, ', '.join(refs)))
            # a paragraph is a p, an li, or a .ptxt that holds no p or li of its own
            paras = [d for d in walk(vis) if d['tag'] in ('p', 'li') or (
                has_class(d, 'ptxt') and not any(x['tag'] in ('p', 'li') for x in walk(d) if x is not d))]
            for para in paras:
                n_words = len(prose_words(prose_of(para)))
                if n_words > VISIBLE_PARAGRAPH_MAX:
                    fail('%s.html: a %s visible paragraph of #%s has %d words, at most %d: a wall of text; split it, '
                         'or make it a list, a table or a figure' % (name, lang, sid, n_words, VISIBLE_PARAGRAPH_MAX))
            for body in (d for d in walk(n) if has_class(d, 'more-body')):
                v = view(body, lang)
                t = text_of(v)
                refs = set(FILE_LINE.findall(t)) | set(BARE_LINE.findall(t))
                if len(refs) > DETAIL_REFS_MAX:
                    fail('%s.html: the %s details of a paragraph in #%s name %d source references, at most %d: the '
                         'central places only, no file index' % (name, lang, sid, len(refs), DETAIL_REFS_MAX))
                for para in (d for d in walk(v) if d['tag'] in ('p', 'li')):
                    n_words = len(prose_words(prose_of(para)))
                    if n_words > DETAIL_PARAGRAPH_MAX:
                        fail('%s.html: a %s paragraph in the details of #%s has %d words, at most %d: one short '
                             'paragraph per point' % (name, lang, sid, n_words, DETAIL_PARAGRAPH_MAX))


def check_subsections(name, root):
    """The CSS counter numbers every .subsec > h3, the table of contents lists each .subsec by its id: both need
    an id and an <h3> as the first element."""
    for n in walk(root):
        if 'subsec' not in n['attrs'].get('class', '').split():
            continue
        if not n['attrs'].get('id'):
            fail('%s.html: a .subsec without an id; the table of contents cannot list it' % name)
        elif not n['children'] or n['children'][0]['tag'] != 'h3':
            fail('%s.html: .subsec #%s does not start with its <h3>' % (name, n['attrs']['id']))


def check_citations(name, root):
    """Every listed .subsec cites a source in each language view: a file:line, a link or a <cite>; a file:line only in
    the details, since the visible text names none."""
    for n in walk(root):
        if not is_listed_subsec(n):
            continue
        for lang in ['en', 'de']:
            if not cites(view(n, lang)):
                fail('%s.html: #%s cites no source in the %s view (a file:line in the details, a link or a <cite>)'
                     % (name, n['attrs'].get('id', '?'), lang))


def cites(node):
    """True when a block points the reader to a source: a path:line, a link or a <cite>."""
    return bool(FILE_LINE.search(text_of(node))) or any(
        d['tag'] == 'cite' or (d['tag'] == 'a' and d['attrs'].get('href')) for d in walk(node))


def view(node, lang):
    """The node as a reader of one language sees it: subtrees of the other language left out."""
    keep = lambda x: isinstance(x, str) or x['attrs'].get('data-lang') in (None, lang)
    seq = [x if isinstance(x, str) else view(x, lang) for x in node.get('seq', []) if keep(x)]
    return dict(node, seq=seq, children=[x for x in seq if not isinstance(x, str)])


def subsec_of(root, target):
    for n in walk(root):
        if 'subsec' in n['attrs'].get('class', '').split() and any(d is target for d in walk(n)):
            return n['attrs'].get('id', '?')
    return '?'


def check_language_owner(name, root, skip=lambda node: False):
    """Every text with a letter sits inside a data-lang element; diagrams and code are language-neutral.
    `skip` names the nodes whose text is not judged."""
    def visit(node, owned):
        if skip(node):
            return
        owned = owned or 'data-lang' in node['attrs'] or node['tag'] in NEUTRAL_TAGS
        for x in node.get('seq', []):
            if isinstance(x, str):
                if not owned and LETTER.search(x):
                    fail('%s.html: text outside a language block: wrap it in data-lang="en" with its German twin' % name)
                    return False
            elif visit(x, owned) is False:
                return False
    visit(root, False)


def css_decode(css):
    """CSS as the browser reads it: comments dropped, escapes (\\75, \\000075, \\u) decoded."""
    def esc(m):
        if m.group(1):
            n = int(m.group(1), 16)
            return chr(n) if 0 < n <= 0x10FFFF and not 0xD800 <= n <= 0xDFFF else '\ufffd'
        return '' if m.group(2) else m.group(3)
    return CSS_ESCAPE.sub(esc, re.sub(r'/\*.*?\*/', '', css, flags=re.S))


def active_content(root):
    """True when a parsed fragment can run code or load from outside; text nodes are never judged."""
    for n in walk(root):
        if n['tag'] in ACTIVE_TAGS:
            return True
        # inside inline SVG a browser decodes character references in <style>; decoding every <style> is the safe side
        if n['tag'] == 'style' and BAD_CSS.search(css_decode(html.unescape(text_of(n)))):
            return True
        for k, raw in n['attrs'].items():
            v = re.sub(r'[\s\x00-\x1f]', '', raw)  # attribute values arrive decoded; drop whitespace tricks
            if k.startswith('on') or (k in URL_ATTRS and BAD_URL.match(v)):
                return True
            loads = k in LOAD_ATTRS or (k in ('href', 'xlink:href') and n['tag'] != 'a')
            urls = [c.strip() for c in raw.split(',')] if k == 'srcset' else [v]
            if loads and any(EXTERNAL.match(u) for u in urls):
                return True
            if k in CSS_ATTRS and BAD_CSS.search(css_decode(raw)):
                return True
    return False


def duplicate_ids(root):
    """Ids that occur on more than one parsed element; markup quoted as text or in a script is no element."""
    seen, dups = set(), []
    for i in (n['attrs']['id'] for n in walk(root) if 'id' in n['attrs']):
        if i in seen and i not in dups:
            dups.append(i)
        seen.add(i)
    return dups


def lang_counts(root):
    """(German, English) language blocks among the parsed elements."""
    langs = [n['attrs'].get('data-lang') for n in walk(root)]
    return langs.count('de'), langs.count('en')


def is_listed_subsec(n):
    """A .subsec the table of contents lists and the CSS counter numbers: an id and an <h3> first."""
    kids = n['children']
    return 'subsec' in n['attrs'].get('class', '').split() and bool(n['attrs'].get('id')) and bool(kids) and kids[0]['tag'] == 'h3'


def check_toc(name, root, main):
    """The hand-written table of contents of a standalone page lists every section of <main> with an id, and in each
    every listed .subsec, in page order."""
    navs = [n for n in walk(root) if n['tag'] == 'nav' and 'toc' in n['attrs'].get('class', '').split()]
    if len(navs) != 1:
        fail('%s: %d nav.toc elements, needs 1' % (name, len(navs)))
        return
    want = [(s['attrs']['id'], [(n['attrs']['id'], n['attrs'].get('data-level')) for n in walk(s) if is_listed_subsec(n)])
            for s in walk(main) if s['tag'] == 'section' and s['attrs'].get('id')]
    have = []
    for ol in (c for c in navs[0]['children'] if c['tag'] == 'ol'):
        for li in (c for c in ol['children'] if c['tag'] == 'li'):
            a = next((c for c in li['children'] if c['tag'] == 'a'), None)
            subs = [(next((x['attrs'].get('href', '') for x in sub['children'] if x['tag'] == 'a'), '').lstrip('#'),
                     sub['attrs'].get('data-level'))
                    for ol2 in li['children'] if ol2['tag'] == 'ol' for sub in ol2['children'] if sub['tag'] == 'li']
            have.append(((a['attrs'].get('href', '') if a else '').lstrip('#'), subs))
    names = lambda entries: ', '.join(i + (' (%s)' % lv if lv else '') for i, lv in entries) or 'nothing'
    if [s for s, _ in have] != [s for s, _ in want]:
        fail('%s: the table of contents lists the sections %s, the page has %s' % (
            name, ', '.join(s for s, _ in have), ', '.join(s for s, _ in want)))
        return
    for (sid, got), (_, subs) in zip(have, want):
        if got != subs:
            fail('%s: the table of contents under #%s lists %s, the page has %s' % (name, sid, names(got), names(subs)))


def check_page(path):
    """The fragment checks on a whole standalone explainer page: its <main> holds the content, the rest is the
    skeleton's chrome (switches, table of contents, scripts)."""
    p = Path(path)
    text = p.read_text(errors='replace') if p.exists() else ''
    if not text.strip():
        fail('%s is missing or empty' % path)
        return result('checked ' + path)
    root = parse_html(text)
    mains = [n for n in walk(root) if n['tag'] == 'main']
    if len(mains) != 1:
        fail('the page has %d <main> elements, needs 1' % len(mains))
        return result('checked ' + path)
    name = p.stem
    check_twins(name, root)
    # all visible text is judged; not judged: <title>, scripts, styles and the EN/DE buttons, whose labels are the
    # language names themselves
    check_language_owner(name, root, skip=lambda n: n['tag'] in ('head', 'title', 'script', 'style') or 'data-set-lang' in n['attrs'])
    sections = [s for s in walk(mains[0]) if s['tag'] == 'section']
    found = [s['attrs'].get('id') for s in sections]
    # a standalone page has no caller, so its sections are exactly the fixed three: none skipped, none added
    if found != FIXED_SECTIONS:
        fail('%s: <main> has the sections %s; it needs exactly %s in this order (a section is never skipped or added)' % (
            name, ', '.join(map(str, found)) or 'none', ', '.join(FIXED_SECTIONS)))
    for sec in sections:
        sid = sec['attrs'].get('id')
        if sid in REQUIRED_IDS:
            check_fixed('%s #%s' % (name, sid), sec, REQUIRED_IDS[sid])
    check_subsections(name, mains[0])
    check_paragraphs(name, mains[0])
    check_toc(name, root, mains[0])
    check_citations(name, mains[0])
    if active_content(mains[0]):
        fail('%s: active content in <main> (script, iframe, SVG animation, event handler, external resource, stylesheet '
             'import or a javascript: link)' % name)
    if any(n.get('dup') for n in walk(mains[0])):
        fail('%s: a tag in <main> carries the same attribute twice (duplicate attribute)' % name)
    for i in duplicate_ids(root):
        fail('id "%s" occurs more than once on the page' % i)
    de, en = lang_counts(root)
    if de != en:
        fail('data-lang blocks differ: de %d, en %d' % (de, en))
    status = result('checked %s: de/en blocks %d/%d' % (path, de, en))
    if not status:
        print('OK: the page passes the explainer checks')
    return status


def main():
    if len(sys.argv) != 2 or sys.argv[1].startswith('--'):
        print(__doc__)
        return 2
    return check_page(sys.argv[1])


if __name__ == '__main__':
    sys.exit(main())
