#!/usr/bin/env python3
"""Assemble the review report from the writers' fragments and check it against findings.json.

Usage: python3 assemble.py <report dir>
       python3 assemble.py --run-name <report dir>
       python3 assemble.py --mark-published <report dir> [<file> ...]
The first form reads <report dir>/findings.json, the fragments <slot>.html and data.json, writes <report dir>/review.html
and <report dir>/inline.js (the report's scripts, for the parse check). It prints a short check result; exit code 1 when any
check fails. The orchestrator reads only the check result.
The second form prints the run-folder name of the review from findings.json (key, ticket, name, date, short sha, run).
The first form also writes <report dir>/publish/ (the page and its files), names the files that changed since the
last publish and plans their publish in batches, one publish subagent each; the third form, run after a batch's
publish with that batch's files (or with none: the whole folder), records them as published (publish/manifest.json).
The page checks (parser, language twins, paragraph disclosures, citations, table of contents, active content) come from
qubit-explanation-page/page_check.py, which also checks a standalone explanation page.
"""
import hashlib
import html
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

# the page checks belong to the explanation skill, whose page this report extends
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'qubit-explanation-page'))
from page_check import (  # noqa: E402
    REQUIRED_IDS,
    DETAIL_PARAGRAPH_MAX,
    VISIBLE_PARAGRAPH_MAX,
    FIXED_SECTIONS,
    FILE_EXTS,
    FILE_LINE,
    NEUTRAL_TAGS,
    LETTER,
    VOID,
    ACTIVE_TAGS,
    BAD_URL,
    URL_ATTRS,
    LOAD_ATTRS,
    EXTERNAL,
    BAD_CSS,
    CSS_ESCAPE,
    CSS_ATTRS,
    errors,
    fail,
    result,
    Tree,
    parse_html,
    walk,
    text_of,
    strip_code,
    prose_words,
    untranslated,
    prose_of,
    check_twins,
    check_fixed,
    check_paragraphs,
    check_subsections,
    check_citations,
    cites,
    view,
    subsec_of,
    check_language_owner,
    css_decode,
    active_content,
    duplicate_ids,
    lang_counts,
    is_listed_subsec,
    check_toc,
)

TEMPLATE = Path(__file__).with_name('review-report-template.html')
SLOTS = ['verdict', 'summary', 'background', 'subject', 'questions', 'good', 'checks', 'method', 'glossary']
# a card's fields, in render order, with the labels the renderer shows; no field text starts with its label
CARD_FIELDS = ['what', 'why', 'fix', 'verify']
FIELD_LABELS = {'what': ['What', 'Was'], 'why': ['Impact', 'Auswirkung'], 'fix': ['Fix', 'Lösung'],
                'verify': ['Checked', 'Geprüft']}
META = ['title', 'key', 'subject', 'subjectLine', 'state', 'author', 'reference', 'depth', 'date',
        'sources', 'lines', 'worktree', 'runDir', 'resume']
# the severity, the only thing the verdict depends on (SKILL.md, Severity)
SEVERITIES = ['blocking', 'non-blocking']
# what a source may propose; possibly-blocking is a proposal only, an investigator decides blocking or non-blocking
PROPOSALS = ['blocking', 'possibly-blocking', 'non-blocking']
# the kind of a finding, in report order (report-sections.md, Kinds); the GitLab prefix is the label the comment
# convention gives it (gitlab-comments.md, Labels)
KINDS = ['issue', 'question', 'chore', 'suggestion', 'nitpick', 'note']
# the kinds a blocking finding may not have
NON_BLOCKING_KINDS = ('suggestion', 'nitpick', 'note')
# a ticket a finding refers to: a Jira key
TICKET_KEY = re.compile(r'[A-Z][A-Z0-9]+-\d+')
# the category filter: key and [en, de] label, in chip order
CATEGORIES = [('functionality', ['Functionality', 'Funktion']),
              ('architecture', ['Architecture', 'Architektur']), ('design', ['Design', 'Design']),
              ('security', ['Security', 'Sicherheit']), ('operations', ['Ops', 'Betrieb']),
              ('performance', ['Performance', 'Performance']), ('usability', ['UX', 'UX']),
              ('tests', ['Tests', 'Tests']), ('documentation', ['Docs', 'Doku']),
              ('style', ['Style', 'Stil'])]
# weakest first: batch, investigator (own), investigator2 (own plus a second);
# unchecked: an investigator failed three times (tooling.md, "Failed subagents"); 4.2 names the claim
STRENGTHS = ['batch', 'investigator', 'investigator2']
CHECKS = STRENGTHS + ['unchecked']


def required_check(proposed, sev, depth):
    """The weakest check SKILL.md §4 allows for a finding: the stronger of what its strongest proposal needs and what
    its final severity needs, so a finding a batch raised to blocking still needs its own investigator. Older runs
    keep their old depth names (high = deep, medium = standard, low below both)."""
    if depth in ('deep', 'high') or sev == 'blocking' or proposed in ('blocking', 'possibly-blocking'):
        return 'investigator'
    return 'batch'


# a finding in these categories names the design principle it breaks, or null when its check named none
PRINCIPLE_CATEGORIES = ('architecture', 'design')
# runs from this date on carry the field; an older run (republish, publish-report) assembles without it
PRINCIPLE_SINCE = '2026-11-04'
# runs from this date on keep a principle on Architecture and Design findings only; older runs may have it elsewhere
PRINCIPLE_ONLY_SINCE = '2026-11-05'
# from this review date on the verdict text is a quick summary: at most VERDICT_WORDS_MAX words per language, no details
VERDICT_SHORT_SINCE = '2026-11-06'
VERDICT_WORDS_MAX = 70
# the findings summary that opens 3.2: an overview by severity, read in seconds
SUMMARY_WORDS_MAX = 120
# a severity line names a finding only when it singles one out: no id ranges, never more ids than this in one line
SUMMARY_LINE_IDS_MAX = 3


def principle_required(spec):
    """True when the run knows the principle field: dated from PRINCIPLE_SINCE on, or a finding already carries it."""
    date = str((spec.get('meta') or {}).get('date', ''))
    return date >= PRINCIPLE_SINCE or any('principle' in f for f in spec.get('findings') or [])


ANCHORS = ['line', 'file', 'mr']
# verdict word -> its negative; the negative is required exactly when a Blocker is open
VERDICTS = {'mergeable': 'not mergeable', 'applicable': 'not applicable', 'fit for use': 'not yet'}
# the German verdict words the translator uses
VERDICTS_DE = {'mergeable': 'mergebar', 'not mergeable': 'nicht mergebar', 'applicable': 'anwendbar',
               'not applicable': 'nicht anwendbar', 'fit for use': 'einsatzbereit', 'not yet': 'noch nicht'}
# the explanation fragments: every subsection cites its source (a file:line in its details, a link or a <cite>)
CITED = {'background', 'subject'}
FINDING_ID = re.compile(r'\bF(\d+)\b')
RESERVED_ID = re.compile(r'^(glc-)?F\d+$')
# per subject type: the positive verdict word, the section 2 heading, what a Blocker holds, where a change goes; [en, de]
SUBJECT_TYPES = {
    'branch': ('mergeable', ['The branch', 'Der Branch'], ['holds the merge', 'hält den Merge auf'], ['in this branch', 'in diesem Branch']),
    'mr': ('mergeable', ['The MR', 'Der MR'], ['holds the merge', 'hält den Merge auf'], ['in this MR', 'in diesem MR']),
    'pr': ('mergeable', ['The PR', 'Der PR'], ['holds the merge', 'hält den Merge auf'], ['in this PR', 'in diesem PR']),
    'patch': ('applicable', ['The patch', 'Der Patch'], ['holds applying the patch', 'hält das Anwenden des Patches auf'],
              ['in this patch', 'in diesem Patch']),
    'files': ('fit for use', ['The code', 'Der Code'], ['holds their use', 'hält den Einsatz auf'],
              ['in these files', 'in diesen Dateien']),
}
# per subject type: the label above the heading, the first header row's label, the reviewed-up-to row's label and the
# word after its sha (None: meta.state shown as it is); [en, de]
HEADER_LABELS = {
    'branch': (['Branch review', 'Branch-Review'], ['Branch', 'Branch'], ['Reviewed up to', 'Geprüft bis'],
               ['branch head', 'Branch-Head']),
    'mr': (['Merge request review', 'Merge-Request-Review'], ['Merge request', 'Merge-Request'],
           ['Reviewed up to', 'Geprüft bis'], ['branch head', 'Branch-Head']),
    'pr': (['Pull request review', 'Pull-Request-Review'], ['Pull request', 'Pull-Request'],
           ['Reviewed up to', 'Geprüft bis'], ['branch head', 'Branch-Head']),
    'patch': (['Patch review', 'Patch-Review'], ['Patch', 'Patch'], ['Applied to', 'Angewendet auf'], None),
    'files': (['Code review', 'Code-Review'], ['Files', 'Dateien'], ['Version', 'Fassung'], None),
}
GITLAB_TYPES = {'branch', 'mr', 'pr'}
MANUAL_ID = re.compile(r'^M[1-9]\d*$')
# a subject with nothing to run has no manual tests
NO_MANUAL_TYPES = {'files'}
MANUAL_TEXT = ['do', 'expect']
# what the cold reader names in a GitLab comment (gitlab-comments.md, Cold read)
COLD_READ_TYPES = ('ref', 'calque', 'mismatch')
# what a writer puts in the German side of a text it changed after the translator ran (tooling.md, Translator)
PLACEHOLDER = 'TODO-DE'
TICKET = re.compile(r'^[A-Z][A-Z0-9]*-\d+$')
# the name leads the browser tab, which cuts the end off
NAME_MAX = 40
TRANSLIT = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss', 'Ä': 'ae', 'Ö': 'oe', 'Ü': 'ue'}
TOOL_OR_ID = re.compile(r'(?i)\b(codex|gemini|claude|agy)\b|\bF\d+\b')


def is_pair(v):
    return isinstance(v, list) and len(v) == 2 and all(isinstance(x, str) and x.strip() for x in v)


def lang_pair(v):
    if isinstance(v, list):
        return '<span data-lang="en">' + html.escape(v[0]) + '</span><span data-lang="de">' + html.escape(v[1]) + '</span>'
    return html.escape(v)


EFFORT_PHASES = [('review', ['Review', 'Review']), ('report', ['Report', 'Bericht'])]
# meta.effort roles, in line order: key -> [en singular, en plural, de]; under each role a run count per model
EFFORT_ROLES = {'reviewers': ['reviewer', 'reviewers', 'Reviewer'],
                'raters': ['severity rater', 'severity raters', 'Schweregrad-Bewerter'],
                'investigators': ['investigator', 'investigators', 'Prüfer'],
                'writers': ['writer', 'writers', 'Schreiber']}


def effort_phase(phase, label, v):
    """[en, de] for one phase of meta.effort ("Review, 30 min: 11 reviewers (7 Claude, 2 Codex, 2 Gemini)"); None after a fail."""
    if not isinstance(v, dict):
        return fail('meta.effort.%s missing: it needs started, ended and runs' % phase)
    try:
        start, end = (datetime.fromisoformat(str(v.get(k, ''))) for k in ('started', 'ended'))
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError('no time zone')
        minutes = round((end - start).total_seconds() / 60)
    except ValueError:
        return fail('meta.effort.%s.started and .ended must be ISO 8601 times with a time zone' % phase)
    if minutes < 0:
        return fail('meta.effort.%s ends before it starts' % phase)
    runs = v.get('runs')
    if not isinstance(runs, dict) or not runs or any(r not in EFFORT_ROLES for r in runs) or not all(
            isinstance(m, dict) and m and all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in m.values())
            for m in runs.values()):
        return fail('meta.effort.%s.runs must map a role (%s) to a run count per model, e.g. '
                    '{"reviewers": {"Claude": 7, "Codex": 2}}' % (phase, ', '.join(EFFORT_ROLES)))
    en, de = [], []
    for role in (r for r in EFFORT_ROLES if r in runs):
        models = runs[role]
        total = sum(models.values())
        # one model: "15 investigators (Claude)"; several: "11 reviewers (7 Claude, 2 Codex, 2 Gemini)"
        which = ', '.join(models) if len(models) == 1 else ', '.join('%d %s' % (n, m) for m, n in models.items())
        words = EFFORT_ROLES[role]
        en.append('%d %s (%s)' % (total, words[0 if total == 1 else 1], which))
        de.append('%d %s (%s)' % (total, words[2], which))
    h, m = divmod(max(minutes, 1), 60)
    return ['%s, %s: %s.' % (label[0], '%d h %d min' % (h, m) if h else '%d min' % m, ', '.join(en[:-1]) + ' and ' + en[-1] if len(en) > 1 else en[0]),
            '%s, %s: %s.' % (label[1], '%d Std. %d Min.' % (h, m) if h else '%d Min.' % m, ', '.join(de[:-1]) + ' und ' + de[-1] if len(de) > 1 else de[0])]


def effort_line(meta):
    """4.2's first two lines, the runs and time of the review and of the report; '' for a run without meta.effort."""
    effort = meta.get('effort')
    if effort is None:
        return ''
    if not isinstance(effort, dict):
        fail('meta.effort must be an object with review and report')
        return ''
    parts = [effort_phase(phase, label, effort.get(phase)) for phase, label in EFFORT_PHASES]
    if any(p is None for p in parts):
        return ''
    # one line per phase, so the report never continues the review's line
    return ''.join('<span data-lang="%s">%s</span>' % (lang, '<br>'.join(html.escape(p[i]) for p in parts))
                   for i, lang in enumerate(['en', 'de']))


def moved_note(meta):
    """The state row's warning when the subject's head at publish is not the reviewed sha in meta.state; '' otherwise."""
    head = str(meta.get('headAtPublish') or '')
    if not head:
        return ''
    if not re.fullmatch(r'[0-9a-f]{7,40}', head):
        fail('meta.headAtPublish must be a commit sha (7 to 40 hex characters)')
        return ''
    m = re.search(r'\b[0-9a-f]{7,40}\b', str(meta.get('state', '')))
    if not m:
        fail('meta.headAtPublish needs the reviewed sha in meta.state')
        return ''
    sha = m.group(0)
    if sha.startswith(head) or head.startswith(sha):
        return ''
    return '<span class="moved">%s</span>' % lang_pair([
        'New commits since this review: now at %s; the findings refer to %s.' % (head, sha),
        'Neue Commits seit diesem Review: jetzt bei %s; die Findings beziehen sich auf %s.' % (head, sha)])


def script_json(v):
    """JSON for a script element: no `<`, so no string can close the script."""
    return json.dumps(v, ensure_ascii=False).replace('<', '\\u003c')


def script_json_lines(items):
    """A JSON array with one element per line, so no line of the report outgrows what one Read call returns."""
    return '[\n' + ',\n'.join(script_json(x) for x in items) + '\n]' if items else '[]'


def load_data_json(path):
    """Parse data.json, the writers' findings array; it is data, never executed."""
    try:
        data = json.loads(path.read_text())
    except ValueError as e:
        # the position only: the message of a decode error never quotes the source
        fail('data.json is not valid JSON at line %d, column %d' % (getattr(e, 'lineno', 0), getattr(e, 'colno', 0)))
        return []
    if not isinstance(data, list) or not all(isinstance(f, dict) for f in data):
        fail('data.json must be an array of finding objects')
        return []
    return data


# ---------------------------------------------------------------- fragments


def check_structure(name, root):
    if name in REQUIRED_IDS:
        check_fixed(name + '.html', root, REQUIRED_IDS[name])
    # the template owns every <section> and every <h2>, the subject's heading per subject type included, so the CSS
    # counter numbers five sections and the heading always fits meta.subjectType
    tags = [n['tag'] for n in walk(root)]
    if 'section' in tags:
        fail('%s.html: contains a <section>; the template supplies the sections' % name)
    if 'h2' in tags:
        fail('%s.html: %d <h2>, needs 0 (the template supplies every section heading)' % (name, tags.count('h2')))
    for n in walk(root):
        nid = n['attrs'].get('id', '')
        if RESERVED_ID.match(nid):
            fail('%s.html: id "%s" is reserved for the cards and the GitLab list' % (name, nid))
    if any('data-level' in n['attrs'] for n in walk(root)):
        fail('%s.html: a data-level block; the report has no reading levels: visible paragraphs, each with its '
             'details where they pay off (details.pt, qubit-explanation-page "Paragraphs and details")' % name)
    check_subsections(name, root)
    # every disclosure keeps the shape; the subsection rules (no file:line in the visible text, references and
    # paragraph lengths in the details) apply where a .subsec exists
    check_paragraphs(name, root)
    if name in CITED:
        check_citations(name, root)


def check_verdict_ids(root, blockers, known, frag='verdict.html'):
    """Each language names every open Blocker, in id order, and no id that is not a finding."""
    for lang in ['en', 'de']:
        text = ' '.join(text_of(e) for e in walk(root) if e['attrs'].get('data-lang') == lang)
        named = ['F' + m for m in FINDING_ID.findall(text)]
        for fid in sorted(set(named) - set(known)):
            fail('%s: the %s text names %s, which is no finding' % (frag, lang, fid))
        missing = [b for b in blockers if b not in named]
        if missing:
            fail('%s: the %s text does not name the open Blocker(s) %s' % (frag, lang, ', '.join(missing)))
        present = [b for b in blockers if b in named]
        if sorted(present, key=named.index) != present:
            fail('%s: the %s text names the open Blockers out of id order' % (frag, lang))


def check_verdict(root, word, blockers, known=(), ids=True):
    """The verdict word fits the open Blockers; before the abstract (ids) each language of the verdict text names
    every open Blocker, since then the findings summary does; the banner itself comes from `verdict_line`."""
    if word not in VERDICTS and word not in VERDICTS.values():
        fail('verdict word %r is not one of %s' % (word, ', '.join(list(VERDICTS) + list(VERDICTS.values()))))
        return
    positive = word in VERDICTS
    if positive == bool(blockers):
        fail('verdict %r with %d open Blocker(s)' % (word, len(blockers)))
    if ids:
        check_verdict_ids(root, blockers, known)


# verdict words whose banner text needs more than the word to stand alone; [en, de]
VERDICT_DISPLAY = {'not yet': ['Not yet fit for use', 'Noch nicht einsatzbereit']}


# 3.4 "What works well": a few points, one line each, so they also close the review comment (report-sections.md, 3.4)
GOOD_POINTS_MAX = 3
REVIEW_COMMENT_MARK = '\x00reviewComment\x00'
GOOD_POINT_WORDS_MAX = 20


def markdown_text(node):
    """A node's text as GitLab Markdown: code in backticks, the rest as plain text."""
    return ''.join(x if isinstance(x, str) else '`%s`' % text_of(x) if x['tag'] == 'code' else markdown_text(x)
                   for x in node.get('seq', []))


def good_points(root):
    """The 3.4 points per language: {'en': [text, ...], 'de': [...]}, one per list item, code in backticks."""
    out = {'en': [], 'de': []}
    for e in walk(root):
        lang = e['attrs'].get('data-lang')
        if lang in out:
            out[lang] += [' '.join(markdown_text(li).split()) for li in walk(e) if li['tag'] == 'li']
    return out


def check_good(root):
    """3.4 is a short list: one to GOOD_POINTS_MAX list items per language, each one line of at most
    GOOD_POINT_WORDS_MAX words, nothing else."""
    if any(e['tag'] in ('details', 'p', 'table', 'pre') for e in walk(root)):
        fail('good.html: "What works well" is a list only, no paragraphs or details (report-sections.md, 3.4)')
    for lang, points in good_points(root).items():
        if not 1 <= len(points) <= GOOD_POINTS_MAX:
            fail('good.html: the %s list has %d points, 1 to %d (report-sections.md, 3.4)' % (lang, len(points), GOOD_POINTS_MAX))
        for t in points:
            if len(t.split()) > GOOD_POINT_WORDS_MAX:
                fail('good.html: a %s point has %d words, at most %d: one line' % (lang, len(t.split()), GOOD_POINT_WORDS_MAX))


def review_comment(spec, points):
    """The closing review comment to copy at the end of 3.5: the verdict, the count of blocking and non-blocking
    findings and the 3.4 points, [en, de]; '' for a subject without GitLab comments."""
    if not gitlab_on(spec):
        return ''
    word = (spec.get('verdict') or {}).get('word', '')
    de_word = VERDICTS_DE.get(word, word)
    verdict = VERDICT_DISPLAY.get(word, [word[:1].upper() + word[1:], de_word[:1].upper() + de_word[1:]])
    sevs = [f.get('sev') for f in spec['findings']]
    counts = '%d blocking, %d non-blocking' % (sevs.count('blocking'), sevs.count('non-blocking'))
    heads = [('**%s.** %s findings.' % (verdict[0], counts)), ('**%s.** %s Findings.' % (verdict[1], counts))]
    labels = [('What works well:', 'Copy'), ('Was gut funktioniert:', 'Kopieren')]
    boxes = ''
    for i, lang in enumerate(['en', 'de']):
        text = heads[i]
        if points.get(lang):
            text += '\n\n' + labels[i][0] + '\n' + '\n'.join('- ' + t for t in points[lang])
        boxes += ('<div class="glc-box" data-lang="%s"><p class="glc-text">%s</p><button type="button" class="glc-copy" '
                  'data-copy="%s">%s</button></div>' % (lang, html.escape(text), html.escape(text), labels[i][1]))
    return ('<div class="glc-review"><p class="glc-file">%s</p>%s</div>' % (
        lang_pair(['Review comment, to close the review', 'Review-Kommentar zum Abschluss des Reviews']), boxes))


def check_verdict_short(root):
    """The verdict text is an abstract under the banner: no details to open, at most VERDICT_WORDS_MAX words per
    language; the findings summary (3.2) carries the findings, what the verdict covers stands in 4.2."""
    if any(e['tag'] == 'details' for e in walk(root)):
        fail('verdict.html: the verdict is an abstract without details; the findings carry them')
    for lang in ['en', 'de']:
        words = len(' '.join(text_of(e) for e in walk(root) if e['attrs'].get('data-lang') == lang).split())
        if words > VERDICT_WORDS_MAX:
            fail('verdict.html: the %s text has %d words, at most %d' % (lang, words, VERDICT_WORDS_MAX))


def check_summary(root):
    """The findings summary is an overview by severity, shorter than reading the cards: no details, at most
    SUMMARY_WORDS_MAX words per language."""
    if any(e['tag'] == 'details' for e in walk(root)):
        fail('summary.html: the findings summary has no details; the cards carry them')
    for lang in ['en', 'de']:
        text = ' '.join(text_of(e) for e in walk(root) if e['attrs'].get('data-lang') == lang)
        words = len(text.split())
        if words > SUMMARY_WORDS_MAX:
            fail('summary.html: the %s text has %d words, at most %d' % (lang, words, SUMMARY_WORDS_MAX))
        if re.search(r'\bF\d+\s*[–-]\s*F\d+\b', text):
            fail('summary.html: the %s text has an id range; name a finding only when the line singles it out' % lang)
    for e in walk(root):
        if e['tag'] == 'li':
            n = len(FINDING_ID.findall(text_of(e)))
            if n > SUMMARY_LINE_IDS_MAX:
                fail('summary.html: a severity line names %d ids, at most %d; the cards list them' % (n, SUMMARY_LINE_IDS_MAX))


def unchecked_line(findings):
    """The line under the findings summary naming the findings no investigator could check, from findings.json, so
    the reader knows where the review is unsure; '' when every finding was checked."""
    ids = [f.get('id') for f in findings if f.get('check') == 'unchecked']
    if not ids:
        return ''
    return '\n<p class="note">%s</p>' % lang_pair(['Not fully checked: ' + ', '.join(ids), 'Nicht vollständig geprüft: ' + ', '.join(ids)])


def check_verdict_abstract(root):
    """The abstract reads before the MR and the findings do: what the MR is for and the gist of the verdict, so no
    finding id and no code name."""
    if any(e['tag'] == 'code' for e in walk(root)):
        fail('verdict.html: the abstract names code; say what it means for a user or the system, in words')
    for lang in ['en', 'de']:
        text = ' '.join(text_of(e) for e in walk(root) if e['attrs'].get('data-lang') == lang)
        ids = sorted(set(FINDING_ID.findall(text)), key=int)
        if ids:
            fail('verdict.html: the %s abstract names %s; finding ids belong in the findings summary (3.2)'
                 % (lang, ', '.join('F' + n for n in ids)))


# what the banner and the stats row already say: the verdict and the Blocker count
RESTATE = {'en': re.compile(r'\b(?:no|zero|0)\s+(?:open\s+)?blockers?\b|\b(?:not\s+)?(?:mergeable|applicable)\b', re.I),
           'de': re.compile(r'\b(?:kein|keine|0)\s+(?:offenen?\s+|offener\s+)?blocker\b|\b(?:nicht\s+)?(?:mergebar|anwendbar)\b', re.I)}


def check_verdict_no_restate(root):
    """The summary says only what the banner and the stats row cannot: never the verdict word or the Blocker count."""
    for lang in ['en', 'de']:
        text = ' '.join(text_of(e) for e in walk(root) if e['attrs'].get('data-lang') == lang)
        m = RESTATE[lang].search(text)
        if m:
            fail('verdict.html: the %s text restates %r, which the banner or the stats row shows' % (lang, m.group(0)))


def ticket_base(meta):
    """The Jira browse URL of the run (meta.ticketBrowseUrl, from the profile); empty when unset."""
    return str((meta or {}).get('ticketBrowseUrl') or '').strip()


def link_text(frag, known, ticket, base=''):
    """Link the ids of known findings to their cards and the keys of the ticket's Jira project to Jira at `base`, in the
    text of a fragment only: never inside a tag, a link, code or pre. Without a base, keys stay plain."""
    key = re.compile(r'(?<![\w/.-])%s-\d+(?![\w-])' % re.escape(ticket.split('-')[0])) if ticket and base else None
    fid = re.compile(r'\bF\d+\b')
    out, skip = [], 0
    for part in re.split(r'(<[^>]*>)', frag):
        if part.startswith('<'):
            m = re.match(r'<(/?)(a|code|pre)\b', part, re.I)
            if m:
                skip += -1 if m.group(1) else 1
            out.append(part)
            continue
        if skip <= 0:
            if key:
                part = key.sub(lambda m: '<a href="%s%s" target="_blank" rel="noopener noreferrer">%s</a>' % (
                    html.escape(base, quote=True), m.group(0), m.group(0)), part)
            pieces = re.split(r'(<a [^>]*>[^<]*</a>)', part)
            part = ''.join(p if p.startswith('<a ') else fid.sub(
                lambda m: '<a href="#%s">%s</a>' % (m.group(0), m.group(0)) if m.group(0) in known else m.group(0), p)
                for p in pieces)
        out.append(part)
    return ''.join(out)


def lines_changed(n):
    """The size of the change after the subject line, e.g. ` · 1,428 lines changed`; nothing without a count."""
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        return ''
    note = ['without lockfiles and generated code', 'ohne Lockfiles und generierten Code']
    return ' · ' + ''.join('<span data-lang="%s" title="%s">%s</span>' % (lang, note[i], text) for i, (lang, text) in enumerate(
        [('en', '{:,} lines changed'.format(n)), ('de', '{:,} geänderte Zeilen'.format(n).replace(',', '.'))]))


# what each category covers, short, from the category table in report-sections.md (Findings 3.2); [en, de]
CATEGORY_TEXT = {
    'functionality': ['the change does what it intends, completely and without faults',
                      'die Änderung tut, was sie soll, vollständig und fehlerfrei'],
    'architecture': ['fit with the rest of the system: boundaries, dependency direction, ADRs, a second mechanism',
                     'Einpassung ins übrige System: Grenzen, Abhängigkeitsrichtung, ADRs, ein zweiter Mechanismus'],
    'design': ['inside the change: unneeded complexity, dead code, misleading names',
               'innerhalb der Änderung: unnötige Komplexität, toter Code, irreführende Namen'],
    'security': ['access control, sessions, secrets, personal data, input validation',
                 'Zugriffsschutz, Sessions, Secrets, personenbezogene Daten, Eingabeprüfung'],
    'operations': ['deploy, config, migrations, rollback, dependencies, logging',
                   'Deployment, Konfiguration, Migrationen, Rollback, Abhängigkeiten, Logging'],
    'performance': ['unbounded queries, missing indexes, repeated work', 'unbegrenzte Abfragen, fehlende Indizes, wiederholte Arbeit'],
    'usability': ['visible to the user and not a fault: texts, errors, accessibility',
                  'für den User sichtbar und kein Fehler: Texte, Fehlermeldungen, Barrierefreiheit'],
    'tests': ['presence, meaningfulness and robustness of tests', 'Vorhandensein, Aussagekraft und Robustheit der Tests'],
    'documentation': ['comments, JSDoc, README, ADR text', 'Kommentare, JSDoc, README, ADR-Text'],
    'style': ['the written style rules and naming by convention', 'die schriftlichen Stilregeln und Benennung nach Konvention'],
}


# what each kind means, short, from the kind table in report-sections.md (Kinds); [en, de]
KIND_TEXT = {
    'issue': ['something is wrong or missing in the subject; also a problem that existed before the change',
              'etwas ist falsch oder fehlt im Gegenstand; auch ein Problem, das schon vor der Änderung bestand'],
    'question': ['only the author can decide it; blocking when one plausible answer is a Blocker',
                 'nur der Autor kann es entscheiden; blocking, wenn eine plausible Antwort ein Blocker ist'],
    'chore': ['the code is right, but someone must act outside the repository (infrastructure, migration, release order)',
              'der Code stimmt, aber jemand muss außerhalb des Repositorys handeln (Infrastruktur, Migration, '
              'Release-Reihenfolge)'],
    'suggestion': ['it works and is complete; another way would be better. Never blocking',
                   'es funktioniert und ist vollständig; ein anderer Weg wäre besser. Nie blocking'],
    'nitpick': ['wording only: names, comments, docs. Never blocking', 'nur Wortlaut: Namen, Kommentare, Doku. Nie blocking'],
    'note': ['information only, nobody has to act. Never blocking', 'nur Information, niemand muss handeln. Nie blocking'],
}


def kind_legend():
    """The kinds part of the 3.2 reference: every kind with what it means."""
    return ''.join('<dt>%s</dt><dd>%s</dd>' % (k, lang_pair(KIND_TEXT[k])) for k in KINDS)


def category_legend():
    """The categories part of the 3.2 reference: every category with what it covers."""
    return ''.join('<dt>%s</dt><dd>%s</dd>' % (lang_pair(label), lang_pair(CATEGORY_TEXT[k])) for k, label in CATEGORIES)


def verdict_line(word):
    """The verdict banner's content from verdict.word: ✓ or ✕ (colour is never the only signal) and the word in
    sentence case, e.g. `Not mergeable` / `Nicht mergebar`; the label "Verdict" stands above it in the template."""
    de = VERDICTS_DE.get(word, word)
    text = VERDICT_DISPLAY.get(word, [word[:1].upper() + word[1:], de[:1].upper() + de[1:]])
    icon = '✓' if word in VERDICTS else '✕'
    return '<span class="verdict-icon" aria-hidden="true">%s</span><strong>%s</strong>' % (icon, lang_pair(text))


VERDICT_WORDS = set(VERDICTS) | set(VERDICTS.values()) | set(VERDICTS_DE.values())
LEAD_WORD = re.compile(r'(<p data-lang="(en|de)">)\s*<strong>\s*(?:(?:Verdict|Urteil):\s*)?([^<]*?)\.?\s*</strong>\.?\s*')


def strip_lead_word(frag, word):
    """Drop a verdict word that a writer put in a paragraph's lead <strong> (reports before the verdict line), so the
    word stands once, in the line above the text; a lead word other than verdict.word fails."""
    def drop(m):
        said = m.group(3).strip().lower()
        if said not in VERDICT_WORDS:
            return m.group(0)
        expected = word if m.group(2) == 'en' else VERDICTS_DE.get(word, word)
        if said != expected:
            fail('verdict.html: the %s lead says %r, verdict.word gives %r' % (m.group(2), said, expected))
        return m.group(1)
    return LEAD_WORD.sub(drop, frag)


# the skill's word for Codex and Gemini runs, which a reader does not know
SKILL_WORD_FOREIGN = re.compile(r'\bforeign\b|\bFremd(lauf|läufe|tool|werkzeug)', re.I)


def check_fragment(name, frag):
    if not frag.strip():
        fail('%s.html is empty' % name)
        return
    root = parse_html(frag)
    if active_content(root):
        fail('%s.html: active content (script, iframe, SVG animation, event handler, external resource, stylesheet '
             'import or a javascript: link)' % name)
    if any(n.get('dup') for n in walk(root)):
        fail('%s.html: a tag carries the same attribute twice (duplicate attribute)' % name)
    check_twins(name, root)
    check_structure(name, root)
    check_language_owner(name, root)
    if name == 'method' and SKILL_WORD_FOREIGN.search(re.sub(r'<[^>]+>', ' ', frag)):
        fail('method.html says "foreign" or "Fremd…" for Codex and Gemini: name the tools (report-sections.md, 4.2)')
    return root


# ---------------------------------------------------------------- findings and comments

def gitlab_on(spec):
    """GitLab comments exist exactly for a branch, an MR or a PR; the subject type decides."""
    return (spec.get('meta') or {}).get('subjectType', 'branch') in GITLAB_TYPES


def gitlab_mismatch(spec):
    """True when findings.json gives a gitlab value the subject type contradicts; check_spec flags it once."""
    return 'gitlab' in spec and (spec.get('meta') or {}).get('subjectType', 'branch') in SUBJECT_TYPES \
        and bool(spec['gitlab']) != gitlab_on(spec)


def complete_findings(spec):
    """Every finding has an id, a severity, a kind, a category and a package; the later checks index them."""
    ok = True
    for i, f in enumerate(spec['findings'], 1):
        for k in ['id', 'sev', 'kind', 'category']:
            if not isinstance(f.get(k), str) or not f[k]:
                fail('finding %d in findings.json lacks %s' % (i, k))
                ok = False
        if not (isinstance(f.get('package'), str) and f['package']) and not is_pair(f.get('package')):
            fail('finding %d in findings.json lacks package' % i)
            ok = False
    return ok


def check_spec(spec):
    meta = spec.get('meta', {})
    for k in META:
        if k not in meta:
            fail('findings.json meta lacks ' + k)
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', str(meta.get('key', ''))):
        fail('meta.key must be a slug (a-z, 0-9, -)')
    st = meta.get('subjectType', 'branch')
    if gitlab_mismatch(spec):
        fail('gitlab is %s, but subjectType %r %s GitLab comments (leave gitlab out: the subject type decides)' % (
            'true' if spec['gitlab'] else 'false', st, 'has' if gitlab_on(spec) else 'has no'))
    if spec.get('mrUrl') and not re.fullmatch(r'https://[^\s"\'<>]+', str(spec['mrUrl'])):
        fail('mrUrl must start with https:// and hold no space or quote')
    if spec.get('mrUrl') and st != 'mr':
        # the links are GitLab line codes; a branch has no MR page and a GitHub PR another anchor scheme
        fail('mrUrl is set, but meta.subjectType is %r: mrUrl belongs to a GitLab MR (subjectType "mr") only' % st)
    if 'subjectType' in meta:
        st, word = meta['subjectType'], (spec.get('verdict') or {}).get('word', '')
        if st not in SUBJECT_TYPES:
            fail('meta.subjectType %r is not one of %s' % (st, ', '.join(SUBJECT_TYPES)))
        elif word in VERDICTS or word in VERDICTS.values():
            positive = SUBJECT_TYPES[st][0]
            if word not in (positive, VERDICTS[positive]):
                fail('verdict %r does not fit subjectType %r (%s / %s)' % (word, st, positive, VERDICTS[positive]))
    fs = spec['findings']
    ids = [f.get('id') for f in fs]
    if not meta.get('published'):
        if ids != ['F%d' % i for i in range(1, len(fs) + 1)]:
            fail('ids must run F1..F%d in list order' % len(fs))
    else:
        # once published, a withdrawn finding leaves its id unused; every gap is named in notes.withdrawn
        nums = [int(i[1:]) if re.fullmatch(r'F\d+', str(i)) else 0 for i in ids]
        if 0 in nums or nums != sorted(set(nums)):
            fail('ids must be F<n>, increasing in list order')
        withdrawn = {m.group(0) for w in (spec.get('notes') or {}).get('withdrawn', []) for m in [FINDING_ID.match(str(w))] if m}
        for n in range(1, max(nums or [0]) + 1):
            if n not in nums and 'F%d' % n not in withdrawn:
                fail('F%d is missing; a finding withdrawn after publish is named in notes.withdrawn ("F%d: reason")' % (n, n))
        for i in ids:
            if i in withdrawn:
                fail('%s is withdrawn and cannot be reused' % i)
    ranks = [(SEVERITIES.index(f['sev']), KINDS.index(f['kind'])) for f in fs
             if f.get('sev') in SEVERITIES and f.get('kind') in KINDS]
    if ranks != sorted(ranks) and not meta.get('published'):  # once published, a re-graded finding keeps id and place
        fail('order must be blocking before non-blocking, then by kind (%s)' % ', '.join(KINDS))
    for f in fs:
        if f.get('sev') not in SEVERITIES:
            fail('%s: sev %r is not one of %s' % (f.get('id'), f.get('sev'), ', '.join(SEVERITIES)))
        if f.get('kind') not in KINDS:
            fail('%s: kind %r is not one of %s' % (f.get('id'), f.get('kind'), ', '.join(KINDS)))
        elif f.get('sev') == 'blocking' and f['kind'] in NON_BLOCKING_KINDS:
            fail('%s: a %s is never blocking; a blocking finding is an issue, a question or a chore '
                 '(report-sections.md, Kinds)' % (f.get('id'), f['kind']))
        if f.get('proposed') not in PROPOSALS:
            fail('%s: proposed %r is not one of %s: the strongest severity any source proposed' % (
                f.get('id'), f.get('proposed'), ', '.join(PROPOSALS)))
        if f.get('check') not in CHECKS:
            fail('%s: check is %r in findings.json (must be %s)' % (f.get('id'), f.get('check'), ', '.join(CHECKS)))
        sev, proposed, check, depth = f.get('sev'), f.get('proposed'), f.get('check'), meta.get('depth')
        if sev in SEVERITIES and proposed in PROPOSALS and check in STRENGTHS:
            need = required_check(proposed, sev, depth)
            if STRENGTHS.index(check) < STRENGTHS.index(need):
                fail('%s: a %s finding proposed %s at %s needs check %s or stronger, or unchecked, not %r (dispatch the '
                     'check; unchecked only after it failed for good)' % (f.get('id'), sev, proposed, depth, need, check))
        if 'followUp' in f:
            fail('%s: findings carry no followUp; a ticket that exists goes into tickets' % f.get('id'))
        if 'tickets' in f and not tickets_of(f):
            fail('%s: tickets must list Jira keys (["PROJ-123"]); a finding without a ticket has no tickets field'
                 % f.get('id'))
        if 'reason' in f:
            fail("%s: findings carry no reason; a Blocker's verify states the proof" % f.get('id'))
        p = f.get('principle')
        if 'principle' in f and p is not None and not (isinstance(p, str) and p.strip()):
            fail('%s: principle must name the principles or be null (SKILL.md §4, step 9)' % f.get('id'))
        if principle_required(spec) and f.get('category') in PRINCIPLE_CATEGORIES and 'principle' not in f:
            fail('%s: category %s needs principle, the one its check named, or null when it named none '
                 '(SKILL.md §4, step 9)' % (f.get('id'), f.get('category')))
        if (str((spec.get('meta') or {}).get('date', '')) >= PRINCIPLE_ONLY_SINCE
                and f.get('category') not in PRINCIPLE_CATEGORIES and p is not None):
            fail('%s: only Architecture and Design findings carry a principle, not category %s '
                 '(SKILL.md §4, step 9)' % (f.get('id'), f.get('category')))
        if 'triggers' in f and triggers_of(f) is None:
            fail('%s: triggers in findings.json must list at least two {"trigger", "wrong"} objects with text in both; '
                 'a finding with one trigger has no triggers field (SKILL.md §4, Merge)' % f.get('id'))
        if 'options' in f and options_of(f) is None:
            fail('%s: options in findings.json must list at least two options with text; a finding with one fix has '
                 'no options field (report-sections.md, Mapping)' % f.get('id'))
        for key in ('fixLeaves', 'fixOpen'):
            if key in f and not (isinstance(f[key], str) and f[key].strip()):
                fail('%s: %s in findings.json must say what is left or open; else the field is left out '
                     '(report-sections.md, Mapping)' % (f.get('id'), key))
        if 'fixOpen' in f and ('options' in f or 'fixLeaves' in f):
            fail('%s: fixOpen excludes options and fixLeaves: an open fix has neither (report-sections.md, Mapping)'
                 % f.get('id'))
        if 'before' in f and not (isinstance(f['before'], str) and f['before'].strip()):
            fail('%s: before in findings.json must name the cases on the target; a finding without any has no '
                 'before field (report-sections.md, Mapping)' % f.get('id'))
    blockers = [f['id'] for f in fs if f.get('sev') == 'blocking']
    if sorted((spec.get('verdict') or {}).get('openBlockers') or []) != sorted(blockers):
        fail('verdict openBlockers %s differ from the Blocker findings %s' % (
            (spec.get('verdict') or {}).get('openBlockers'), blockers))
    return blockers


OLD_CARD_KEYS = ('plain', 'tech')
# a comment text that already carries a label prefix (**Nit:**, **issue (blocking):**)
PREFIX_START = re.compile(r'\s*\*\*[^*\n]{1,40}:\*\*')


def tickets_of(f):
    """A finding's tickets, a non-empty list of distinct Jira keys; None when the field is malformed."""
    t = f.get('tickets')
    if not (isinstance(t, list) and t and all(isinstance(k, str) and TICKET_KEY.fullmatch(k) for k in t)
            and len(set(t)) == len(t)):
        return None
    return t


def check_findings(spec, data):
    want = {f['id']: f for f in spec['findings']}
    got = {f.get('id'): f for f in data}
    if list(want) != [f.get('id') for f in data]:
        fail('ids or order differ: findings.json %s, data.json %s' % (list(want), [f.get('id') for f in data]))
    cards = {}
    for fid, w in want.items():
        g = got.get(fid)
        if not g:
            continue
        if any(k in g for k in OLD_CARD_KEYS) or 'fields' not in g:
            # the card shape of an older skill version: its report is changed in its own HTML, never rebuilt here
            fail('%s: data.json has the card shape of an older skill version (%s): a card holds fields.what, .why, '
                 '.fix and .verify, each {"text", "more"}; a report published by an older version of the skill is '
                 'changed in its own HTML (report-sections.md)'
                 % (fid, ', '.join(k for k in OLD_CARD_KEYS if k in g) or 'no fields'))
            continue
        if 'sources' in g or 'check' in g:
            fail('%s: data.json carries sources or check; findings name no source' % fid)
        for k in ['sev', 'kind', 'category', 'package', 'file', 'tickets']:
            if g.get(k) != w.get(k):
                fail('%s: %s is %r, findings.json says %r' % (fid, k, g.get(k), w.get(k)))
        if not is_pair(g.get('t')):
            fail('%s: t is not a complete [en, de] pair' % fid)
        elif untranslated(*g['t']):
            fail('%s: the German t is the English text' % fid)
        for k in CARD_FIELDS:
            if k in g:
                fail('%s: data.json carries the consolidated %s; it stays in findings.json, the card shows '
                     'fields.%s' % (fid, k, k))
        if check_card_fields(w, g):
            cards[fid] = g['fields']
            check_trigger_lists(w, g)
            check_principle(w, g)
        if 'proposed' in g or 'followUp' in g:
            fail('%s: data.json carries proposed or followUp; proposed stays in findings.json, followUp is gone' % fid)
        check_comments(spec, w, g)
    check_removes(spec, cards)


def field_paragraphs(text):
    """The paragraphs of a field text as the renderer shows them: a blank line starts a paragraph, and each line of a
    "- " or "1. " list is one item of its own."""
    out = []
    for para in re.split(r'\n\s*\n', str(text)):
        lines = para.split('\n')
        if all(re.match(r'- |\d+\. ', l) for l in lines):
            out += lines
        elif para.strip():
            out.append(para)
    return out


def check_card_fields(w, g):
    """A card's fields: what, why, fix and verify, each a visible `text` and its `more` (the details) or null. Returns
    False when the shape is broken, so the later checks skip the card."""
    fid, fields = w['id'], g.get('fields')
    if not isinstance(fields, dict) or sorted(fields) != sorted(CARD_FIELDS):
        fail('%s: fields must hold exactly %s' % (fid, ', '.join(CARD_FIELDS)))
        return False
    ok = True
    for k in CARD_FIELDS:
        v = fields[k]
        if not isinstance(v, dict) or sorted(v) != ['more', 'text']:
            fail('%s: fields.%s must be {"text": [en, de], "more": [en, de] or null}' % (fid, k))
            ok = False
            continue
        text, more = v['text'], v['more']
        if not is_pair(text):
            fail('%s: fields.%s.text is not a complete [en, de] pair' % (fid, k))
            ok = False
        elif untranslated(*text):
            fail('%s: the German fields.%s.text is the English text' % (fid, k))
        if more is not None and not is_pair(more):
            fail('%s: fields.%s.more is neither a complete [en, de] pair nor null' % (fid, k))
            ok = False
        elif more is not None and untranslated(*more):
            fail('%s: the German fields.%s.more is the English text' % (fid, k))
        for i, lang in enumerate(['English', 'German']):
            if is_pair(text):
                t = text[i]
                refs = sorted(set(FILE_LINE.findall(t)))
                if refs:
                    fail('%s: the %s fields.%s.text names %s; file:line belongs in its more' % (fid, lang, k, ', '.join(refs)))
                for label in FIELD_LABELS[k]:
                    if re.match(r'\s*\**\s*%s\s*\**\s*:' % re.escape(label), t, re.I):
                        fail('%s: the %s fields.%s.text starts with its label %r; the card shows the label' % (fid, lang, k, label))
                for para in field_paragraphs(t):
                    n = len(prose_words(para))
                    if n > VISIBLE_PARAGRAPH_MAX:
                        fail('%s: a paragraph of the %s fields.%s.text has %d words, at most %d: two to four sentences; '
                             'split it, make it a list, or move the depth into more' % (fid, lang, k, n, VISIBLE_PARAGRAPH_MAX))
            if is_pair(more):
                for para in field_paragraphs(more[i]):
                    n = len(prose_words(para))
                    if n > DETAIL_PARAGRAPH_MAX:
                        fail('%s: a paragraph of the %s fields.%s.more has %d words, at most %d: one short paragraph '
                             'per point' % (fid, lang, k, n, DETAIL_PARAGRAPH_MAX))
    if ok and w.get('sev') == 'blocking':
        what_more, verify_more = fields['what']['more'], fields['verify']['more']
        for i, lang in enumerate(['English', 'German']):
            if not (is_pair(what_more) and FILE_LINE.search(what_more[i])):
                fail('%s: a Blocker needs the evidence path in fields.what.more, with at least one file:line (%s)'
                     % (fid, lang))
        if not is_pair(verify_more):
            fail('%s: a Blocker needs fields.verify.more: what was read or run, and how to check it again' % fid)
    return ok


def check_principle(w, g):
    """A finding with a principle names it in the English fields.what.text (report-sections.md, Findings 3.2)."""
    p = w.get('principle')
    if not (isinstance(p, str) and p.strip()):
        return
    text = g['fields']['what']['text'][0].lower()
    for name in (x.strip() for x in p.split(',')):
        if name and name.lower() not in text:
            fail('%s: the English fields.what.text does not name the principle %s; it joins the sentence that gives '
                 'the reason (report-sections.md, Findings 3.2)' % (w['id'], name))


def check_removes(spec, cards):
    """A finding whose fix also removes others names each by id in its fields.fix.text, and each removed finding names
    it back in its own, so a reader of either card sees the link."""
    ids = [f.get('id') for f in spec['findings']]
    for f in spec['findings']:
        if 'removes' not in f:
            continue
        r = f['removes']
        if not (isinstance(r, list) and r and all(isinstance(x, str) for x in r)):
            fail('%s: removes must list the ids of the findings its fix also removes' % f['id'])
            continue
        for rid in r:
            if rid not in ids or rid == f['id']:
                fail('%s: removes names %s, which is no other finding' % (f['id'], rid))
                continue
            for a, b, why in ((f['id'], rid, 'which its fix also removes'), (rid, f['id'], 'whose fix also removes it')):
                if a not in cards:
                    continue
                for lang, t in zip(['English', 'German'], cards[a]['fix']['text']):
                    if b not in ['F' + m for m in FINDING_ID.findall(t)]:
                        fail('%s: the %s fields.fix.text does not name %s, %s (report-sections.md, Findings 3.2)'
                             % (a, lang, b, why))


def check_manual(spec, d, notes):
    """The manual tests: findings.json's `manual` (the orchestrator's, English) against manual.json (the translator's
    [en, de] pairs). Returns the checked object for the page, or None for a subject without manual tests."""
    meta = spec.get('meta') or {}
    if 'manual' not in spec:
        if meta.get('subjectType', 'branch') in NO_MANUAL_TYPES:
            return None
        if meta.get('published') and 'manualPublished' not in (spec.get('notes') or {}):
            notes.append('manual missing: published before manual tests existed')
            return None
        fail('manual missing: every branch, mr, pr or patch review lists its manual test steps (null when the trace said None.)')
        return None
    m = spec['manual']
    # null: the trace found nothing to run (a docs-only or CI-only change)
    if m is None:
        return None
    if not isinstance(m, dict) or not isinstance(m.get('steps'), list) or not all(isinstance(s, dict) for s in m['steps']):
        fail('findings.json manual must be an object with a steps array of objects')
        return None
    ids = [s.get('id') for s in m['steps']]
    for i in ids:
        if not (isinstance(i, str) and MANUAL_ID.match(i)):
            fail('manual test step id %r is not M<n>' % (i,))
    dups = []
    for i in ids:
        if ids.count(i) > 1 and i not in dups:
            dups.append(i)
            fail('manual test step id %s occurs twice' % i)
    # a published id stays its step's for good: a dropped one is named in withdrawn, never reused
    withdrawn = [str(w).split(':', 1)[0].strip() for w in m.get('withdrawn') or []]
    for i in ids:
        if i in withdrawn:
            fail('%s is withdrawn and cannot be reused' % i)
    if meta.get('published'):
        for i in (spec.get('notes') or {}).get('manualPublished') or []:
            if i not in ids and i not in withdrawn:
                fail('%s was published and is missing; list it in manual.withdrawn' % i)
    for s in m['steps']:
        for k in MANUAL_TEXT:
            if not (isinstance(s.get(k), str) and s[k].strip()):
                fail('findings.json manual %s: %s is empty' % (s.get('id'), k))
    f = d / 'manual.json'
    if not f.exists():
        fail('missing manual.json')
        return None
    try:
        data = json.loads(f.read_text())
    except ValueError as e:
        fail('manual.json is not valid JSON at line %d, column %d' % (getattr(e, 'lineno', 0), getattr(e, 'colno', 0)))
        return None
    if not isinstance(data, dict) or not isinstance(data.get('steps'), list) or not all(isinstance(s, dict) for s in data['steps']):
        fail('manual.json must be an object with a steps array of objects')
        return None
    got = [s.get('id') for s in data['steps']]
    if got != ids:
        fail('manual test ids differ: findings.json %s, manual.json %s' % (ids, got))
        return None

    def pair(where, name, v, english):
        if not is_pair(v):
            fail('manual.json %s: %s is no [en, de] pair' % (where, name))
        elif untranslated(*v):
            fail('manual.json %s: %s is not translated' % (where, name))
        elif v[0].strip() != str(english).strip():
            fail('manual.json %s: the English %s differs from findings.json' % (where, name))
    pair('setup', 'setup', data.get('setup'), m.get('setup', ''))
    for s, w in zip(m['steps'], data['steps']):
        for k in MANUAL_TEXT:
            pair(s['id'], k, w.get(k), s.get(k, ''))
    # only the checked keys reach the page
    return {'setup': data.get('setup'), 'steps': [{'id': w['id'], 'do': w.get('do'), 'expect': w.get('expect')} for w in data['steps']]}


def is_count(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def check_cold_read(spec, data, notes):
    """The cold read of the GitLab comments (gitlab-comments.md, Cold read): notes.coldRead counts what a reader
    without the report named, and every item is fixed or left with a reason."""
    n = sum(len(f.get('gitlab') or []) for f in data)
    if not gitlab_on(spec) or not n:
        return
    cr = (spec.get('notes') or {}).get('coldRead')
    if cr is None:
        # a run published before the cold read existed; every later run cannot publish without it
        if (spec.get('meta') or {}).get('published'):
            notes.append('cold read missing: published before the cold read existed')
            return
        fail('notes.coldRead missing: the GitLab comments get a cold read before the first publish (gitlab-comments.md, Cold read)')
        return
    items = cr.get('items') if isinstance(cr, dict) else None
    if not (isinstance(cr, dict) and is_count(cr.get('comments')) and cr.get('rounds') in (1, 2)
            and isinstance(items, dict) and sorted(items) == sorted(COLD_READ_TYPES) and all(is_count(v) for v in items.values())
            and is_count(cr.get('fixed')) and isinstance(cr.get('left'), list)):
        fail('notes.coldRead must be {"comments": n, "rounds": 1 or 2, "items": {"ref": n, "calque": n, "mismatch": n}, '
             '"fixed": n, "left": ["F<n> <type>: <reason>"]} (gitlab-comments.md, Cold read)')
        return
    if cr['comments'] != n:
        fail('notes.coldRead.comments is %d, but data.json holds %d GitLab comments: every comment gets a cold read, '
             'a changed or added one in the second round' % (cr['comments'], n))
    known = {f.get('id') for f in spec['findings']}
    for w in cr['left']:
        m = re.fullmatch(r'(F\d+) (%s): \S.*' % '|'.join(COLD_READ_TYPES), str(w), flags=re.S)
        if not m or m.group(1) not in known:
            fail('notes.coldRead.left %r is not "F<n> <type>: <reason>" for a finding of the report' % (w,))
    if cr['fixed'] + len(cr['left']) != sum(items.values()):
        fail('notes.coldRead: fixed (%d) plus left (%d) is not the %d items the cold read named; each item is fixed or '
             'left with a reason' % (cr['fixed'], len(cr['left']), sum(items.values())))


def check_method_cold_read(root, spec):
    """The method section names the cold read in each language (report-sections.md, 4.2): how many comments were
    read, how many items were fixed (when any), and every finding with an item left. The numbers and ids are what
    the record and the text share, so a method section that never mentions the cold read fails."""
    cr = (spec.get('notes') or {}).get('coldRead')
    if not (isinstance(cr, dict) and is_count(cr.get('comments')) and is_count(cr.get('fixed'))
            and isinstance(cr.get('left'), list)):
        return
    left = sorted({m.group(1) for w in cr['left'] for m in [re.match(r'(F\d+) ', str(w))] if m}, key=lambda i: int(i[1:]))
    for lang in ['en', 'de']:
        text = ' '.join(text_of(e) for e in walk(root) if e['attrs'].get('data-lang') == lang)
        numbers = set(re.findall(r'(?<![\w.])\d+(?![\w.])', text))
        missing = []
        if str(cr['comments']) not in numbers:
            missing.append('the %d comments read' % cr['comments'])
        if cr['fixed'] and str(cr['fixed']) not in numbers:
            missing.append('the %d items fixed' % cr['fixed'])
        named = set('F' + m for m in FINDING_ID.findall(text))
        missing += ['%s, which has an item left' % i for i in left if i not in named]
        if missing:
            fail('method.html: the %s text does not name the cold read (notes.coldRead): %s (report-sections.md, 4.2)'
                 % (lang, '; '.join(missing)))


def check_method_withdrawn(root, spec):
    """The method section names every id withdrawn after publish in each language (report-sections.md, 4.2), so a
    reader who misses F<n> in the list finds why it is gone."""
    withdrawn = (spec.get('notes') or {}).get('withdrawn') or []
    ids = sorted({'F' + m.group(1) for w in withdrawn for m in [re.match(r'F(\d+)\b', str(w))] if m},
                 key=lambda i: int(i[1:]))
    if not ids:
        return
    for lang in ['en', 'de']:
        text = ' '.join(text_of(e) for e in walk(root) if e['attrs'].get('data-lang') == lang)
        named = set('F' + m for m in FINDING_ID.findall(text))
        for i in ids:
            if i not in named:
                fail('method.html: the %s text does not name %s, withdrawn after publish (notes.withdrawn; '
                     'report-sections.md, 4.2)' % (lang, i))


def placeholder_paths(v, path=''):
    """The path of every string under v that holds the placeholder; a list item with an id is named by it."""
    if isinstance(v, str):
        if PLACEHOLDER in v:
            yield path
    elif isinstance(v, dict):
        for k, x in v.items():
            yield from placeholder_paths(x, '%s.%s' % (path, k) if path else k)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            key = x['id'] if isinstance(x, dict) and isinstance(x.get('id'), str) else '%s[%d]' % (path, i)
            yield from placeholder_paths(x, key)


def check_placeholders(d, data):
    """No TODO-DE is left: a writer marks the German side of every text it changed after the translator ran, and the
    translator fills each one before the report is built (tooling.md, Translator)."""
    for f in data:
        if not isinstance(f, dict):
            continue
        fid = f.get('id') if isinstance(f.get('id'), str) else '?'
        for k, v in f.items():
            if k == 'id':
                continue
            for p in placeholder_paths(v, k):
                fail('%s: %s in data.json holds the placeholder %s: the translator fills it (tooling.md, Translator)'
                     % (fid, p, PLACEHOLDER))
    for name in SLOTS:
        f = d / (name + '.html')
        if f.exists():
            for n, line in enumerate(f.read_text().split('\n'), 1):
                if PLACEHOLDER in line:
                    fail('%s.html line %d holds the placeholder %s: the translator fills it (tooling.md, Translator)'
                         % (name, n, PLACEHOLDER))
    f = d / 'manual.json'
    if f.exists():
        try:
            m = json.loads(f.read_text())
        except ValueError:
            return  # check_manual names the parse error
        for p in placeholder_paths(m):
            fail('manual.json %s holds the placeholder %s: the translator fills it (tooling.md, Translator)'
                 % (p, PLACEHOLDER))


def triggers_of(f):
    """The finding's triggers from findings.json, worst first; None when absent or not at least two complete ones."""
    t = f.get('triggers')
    if not isinstance(t, list) or len(t) < 2:
        return None
    for x in t:
        if not (isinstance(x, dict) and all(isinstance(x.get(k), str) and x[k].strip() for k in ('trigger', 'wrong'))):
            return None
    return t


def options_of(f):
    """The finding's fix options from findings.json; None when absent or fewer than two with text."""
    o = f.get('options')
    if not isinstance(o, list) or len(o) < 2 or not all(isinstance(x, str) and x.strip() for x in o):
        return None
    return o


def list_items(text):
    """The list items of a field text as the renderer reads it: a paragraph whose every line starts with "- "."""
    return sum(len(p.split('\n')) for p in re.split(r'\n\s*\n', str(text))
               if all(l.startswith('- ') for l in p.split('\n')))


def comment_items(text):
    """The "- " lines of a GitLab comment, code blocks left out."""
    return [l for l in re.sub(r'```.*?```', ' ', text, flags=re.S).splitlines() if l.lstrip().startswith('- ')]


def check_trigger_lists(w, g):
    """A finding with several triggers lists each in fields.what.text, so no reader misses one."""
    t = triggers_of(w)
    if not t:
        return
    for lang, text in zip(['English', 'German'], g['fields']['what']['text']):
        n = list_items(text)
        if n < len(t):
            fail('%s: fields.what.text (%s) lists %d of %d triggers; each trigger is a "- " line in a paragraph of its '
                 'own (report-sections.md, Findings 3.2)' % (w['id'], lang, n, len(t)))


def addresses_person(en, de):
    en, de = strip_code(en), strip_code(de)
    # "us" before a hyphen or digit is a name (us-east-1, us2)
    if (re.search(r"\b(you|yours?|we|ours?|please|let['’]s)\b", en, re.I) or re.search(r'\b[Uu]s\b(?![-\d])', en)
            or re.search(r'(?<![\w/])I(?![\w/])', en)):
        return True
    # whole words only, so Deinstallation and unserialisierbar pass
    if re.search(r'\b(du|dein(?:e|em|en|er|es)?|dich|dir|euch|euer|eur(?:e|em|en|er|es)|ich|wir|uns|unser(?:e|em|en|er|es)?|bitte)\b',
                 de, re.I):
        return True
    # the formal forms are capitalised; a lower-case "ihr" is mostly "her" or "their", so it is not judged
    if re.search(r'\bIhnen\b', de):
        return True
    for m in re.finditer(r'\b(?:Sie|Ihr(?:e|em|en|er|es)?)\b', de):
        before = de[:m.start()].rstrip()
        # sentence-initial "Sie" may mean "it" and "Ihr…" "its" or "their"; mid-sentence they address the reader
        if before and before[-1] not in '.!?:':
            return True
    return False


COMMENT_WORDS = 100


def too_long(text, triggers=False):
    """Up to COMMENT_WORDS words in all, the label included; code blocks are exempt.
    A finding that lists several places has one list line (up to 20 words) per place, outside the total;
    the trigger lines of a finding with triggers count towards the total."""
    lines = re.sub(r'```.*?```', ' ', text, flags=re.S).splitlines()
    if triggers:
        return len(' '.join(re.sub(r'^\s*- ', '', l) for l in lines).split()) > COMMENT_WORDS
    items = [l for l in lines if l.lstrip().startswith('- ')]
    if any(len(l.split()) > 21 for l in items):
        return True
    rest = ' '.join(l for l in lines if not l.lstrip().startswith('- '))
    return len(rest.split()) > COMMENT_WORDS


def check_comments(spec, w, g):
    fid, comments = w['id'], g.get('gitlab') or []
    if gitlab_mismatch(spec):
        return
    if not gitlab_on(spec):
        if comments:
            fail('%s: GitLab comment on a %r subject (comments only for a branch, MR or PR)' % (
                fid, spec['meta'].get('subjectType')))
        return
    if not comments:
        fail('%s: no GitLab comment' % fid)
    if len(comments) > 2:
        fail('%s: %d GitLab comments, two at most' % (fid, len(comments)))
    for c in comments:
        at = comment_place(c)
        if 'at' in c:
            fail('%s: GitLab comment has "at"; its place is path, startLine and endLine (gitlab-comments.md)' % fid)
            continue
        anchor, path, start, end = c.get('anchor'), c.get('path'), c.get('startLine'), c.get('endLine')
        if anchor not in ANCHORS:
            fail('%s: anchor %r at %s is not one of %s' % (fid, anchor, at, ', '.join(ANCHORS)))
        if c.get('side') not in (None, 'old'):
            fail('%s: side %r at %s (only "old" or absent)' % (fid, c.get('side'), at))
        if path is not None and not (isinstance(path, str) and path):
            fail('%s: path %r is not a file path' % (fid, path))
        elif path is None and anchor in ('line', 'file'):
            fail('%s: a %s comment needs a path' % (fid, anchor))
        if start is not None and not is_line(start):
            fail('%s: startLine %r at %s is not a line number' % (fid, start, at))
        elif start is None and anchor == 'line':
            fail('%s: the line comment at %s needs a startLine' % (fid, at))
        elif start is not None and path is None:
            fail('%s: startLine %r without a path' % (fid, start))
        if end is not None:
            if anchor != 'line':
                fail('%s: endLine at %s on a %s comment (a range only on a line comment)' % (fid, at, anchor))
            elif not (is_line(end) and is_line(start) and end > start):
                fail('%s: endLine %r at %s is not a line number after startLine' % (fid, end, at))
        if not is_pair(c.get('text')):
            fail('%s: GitLab text at %s is not a complete [en, de] pair' % (fid, at))
            continue
        en, de = c['text']
        if untranslated(en, de):
            fail('%s: the German GitLab text at %s is the English text' % (fid, at))
        if addresses_person(en, de):
            fail('%s: GitLab text at %s addresses a person (you/your/I/we/our/us/let\'s/please, '
                 'du/dein/dich/dir/euch/euer/ich/wir/uns/unser/bitte/Sie/Ihr/Ihnen)' % (fid, at))
        if TOOL_OR_ID.search(strip_code(en)) or TOOL_OR_ID.search(strip_code(de)):
            fail('%s: GitLab text at %s names a tool name or finding id' % (fid, at))
        triggers, options = triggers_of(w), options_of(w)
        listed = min(len(triggers), 3) if triggers else 0
        for lang, t, suggestion, question in (('English', en, 'Suggestion', 'Question:'), ('German', de, 'Vorschlag', 'Frage:')):
            if triggers and too_long(t, triggers=True):
                fail('%s: %s GitLab text at %s is over the word limit (%d words, the trigger lines included)' % (
                    fid, lang, at, COMMENT_WORDS))
            elif not triggers and too_long(t):
                fail('%s: %s GitLab text at %s is over the word limit (%d words, a list line 20)' % (fid, lang, at, COMMENT_WORDS))
            if triggers and len(comment_items(t)) != listed:
                fail('%s: %s GitLab text at %s has %d "- " lines; a finding with %d triggers lists %d, one per trigger, '
                     'worst first (gitlab-comments.md)' % (fid, lang, at, len(comment_items(t)), len(triggers), listed))
            plain = strip_code(t)
            if PREFIX_START.match(t):
                fail('%s: %s GitLab text at %s starts with a label; the renderer adds the prefix from kind and sev '
                     '(gitlab-comments.md, Labels)' % (fid, lang, at))
            if w.get('kind') != 'issue':
                if suggestion + ':' in plain:
                    fail('%s: %s GitLab text at %s has "%s:", which only an issue has; a %s says its point directly '
                         '(gitlab-comments.md)' % (fid, lang, at, suggestion, w.get('kind')))
            elif (options or isinstance(w.get('fixOpen'), str)) and (question not in plain or suggestion + ':' in plain):
                fail('%s: %s GitLab text at %s needs "%s" and no "%s:": an issue with options or fixOpen asks instead '
                     'of suggesting (gitlab-comments.md)' % (fid, lang, at, question, suggestion))


# ---------------------------------------------------------------- diff and links

def unquote_path(p):
    """Git's C-style quoted path ("a/\\303\\244.ts") to text."""
    if len(p) >= 2 and p[0] == p[-1] == '"':
        p = p[1:-1].encode('latin-1', 'backslashreplace').decode('unicode_escape').encode('latin-1').decode('utf-8')
    return p


def parse_diff(text):
    """Map each file of a unified diff to the GitLab line codes of its lines.

    GitLab's anchor for a line is <sha1 of the file path>_<old>_<new>. Both counters hold the next line
    number: an added line carries the next old number, a removed line the next new number.
    Returns {new_path: {'new': {new line: (old, new)}, 'old': {old line: (old, new)}}}.
    The file path comes from the ---/+++ header lines, so quoted paths and paths with spaces both work.
    """
    files, cur, old, new, old_path = {}, None, None, None, None
    for line in text.splitlines():
        if line.startswith('diff --git '):
            cur, old, new, old_path = None, None, None, None
            # a renamed, binary or mode-only file has no +++ header and no hunk: the header's new side names the changed
            # file; the old side of a rename and a copy source are no changed files of the subject
            files.setdefault(header_path(line[len('diff --git '):]), {'new': {}, 'old': {}})
            continue
        m = re.match(r'(?:rename|copy) to (.*)$', line)
        if m and old is None:
            files.setdefault(unquote_path(m.group(1)), {'new': {}, 'old': {}})
            continue
        if old is None and line.startswith('--- '):
            old_path = unquote_path(line[4:].rstrip('\t'))
            continue
        if old is None and line.startswith('+++ '):
            path = unquote_path(line[4:].rstrip('\t'))
            path = old_path if path == '/dev/null' else path
            path = re.sub(r'^[ab]/', '', path or '')
            cur = files.setdefault(path, {'new': {}, 'old': {}})
            continue
        m = re.match(r'@@ -(\d+)(?:,\d+)? \+(\d+)', line)
        if m:
            old, new = int(m.group(1)), int(m.group(2))
            continue
        if cur is None or old is None or line[:1] not in ('+', '-', ' '):
            continue
        if line[0] == '+':
            cur['new'][new] = (old, new)
            new += 1
        elif line[0] == '-':
            cur['old'][old] = (old, new)
            old += 1
        else:
            cur['new'][new] = cur['old'][old] = (old, new)
            old, new = old + 1, new + 1
    return files


def header_path(pair):
    """The b/ side of a `diff --git a/P b/Q` header. When both sides are the same path, the header is split in the
    middle, so a path that holds " b/" stays whole."""
    n = (len(pair) - 5) // 2
    if pair.startswith('a/') and pair[2 + n:5 + n] == ' b/' and pair[2:2 + n] == pair[5 + n:]:
        return pair[5 + n:]
    m = re.match(r'("(?:[^"\\]|\\.)*"|a/.*?) ("(?:[^"\\]|\\.)*"|b/.*)$', pair)
    return re.sub(r'^b/', '', unquote_path(m.group(2))) if m else ''


def is_line(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 1


def comment_place(c):
    """A comment's place as text: path, :startLine, –endLine; '' for a general MR comment without a file."""
    start, end = c.get('startLine'), c.get('endLine')
    return '%s%s%s' % (c.get('path') or '', ':%s' % start if start is not None else '', '–%s' % end if end is not None else '')


def link_key(c):
    """The key of a comment's link, as in the template's linkKey: path:startLine, plus '|old' for a removed line."""
    return '%s:%s%s' % (c.get('path') or '', c.get('startLine') or '', '|old' if c.get('side') == 'old' else '')


def check_anchors(spec, data, diff, diff_file):
    """Every `line` anchor lies inside a hunk of the diff, every line of a range in the same hunk, and every `file`
    anchor names a file of the diff, with or without an MR."""
    if not gitlab_on(spec):
        return []
    if not diff:
        return ['%s missing or empty: line and file anchors not checked' % diff_file]
    for f in data:
        for c in f.get('gitlab') or []:
            path, start, end = c.get('path') or '', c.get('startLine'), c.get('endLine')
            if c.get('anchor') == 'line' and is_line(start):
                lines = diff.get(path, {}).get('old' if c.get('side') == 'old' else 'new', {})
                last = end if is_line(end) and end > start else start
                gap = next((n for n in range(start, last + 1) if n not in lines), None)
                if gap == start:
                    fail('%s: line anchor %s is outside the diff hunks (use anchor "file")' % (f.get('id'), comment_place(c)))
                elif gap:
                    fail('%s: line range %s leaves the diff hunk at line %d (end the range inside the hunk)'
                         % (f.get('id'), comment_place(c), gap))
            elif c.get('anchor') == 'file' and path not in diff:
                fail('%s: file anchor %s is not in the diff (use anchor "mr")' % (f.get('id'), comment_place(c)))
    return []


def gitlab_links(spec, data, diff):
    """Return {comment key: URL into the MR's diff view}, empty when findings.json has no mrUrl.

    The key is link_key; the template looks it up. A general MR comment links to the MR. A range links to its first
    line: GitLab's line code names one line, and the report's hint names the rest.
    """
    base = (spec.get('mrUrl') or '').rstrip('/')
    if not base:
        return {}  # no MR: the comments stay plain text
    links = {}
    for f in data:
        for c in f.get('gitlab') or []:
            anchor = c.get('anchor')
            if anchor == 'mr':
                links[link_key(c)] = base
                continue
            path, start = c.get('path') or '', c.get('startLine')
            href = '%s/diffs#%s' % (base, hashlib.sha1(path.encode()).hexdigest())
            pos = diff.get(path, {}).get('old' if c.get('side') == 'old' else 'new', {}).get(start) if is_line(start) else None
            if anchor == 'line' and pos:
                href += '_%d_%d' % pos
            links[link_key(c)] = href
    return links


# ---------------------------------------------------------------- report

def build_toc(page):
    """The table of contents from the parsed report: every section with an id, and in it every .subsec that
    check_subsections accepts (an id, an <h3> first), the same ones the CSS counter numbers."""
    def inner(node):
        a, b = node.get('inner', (0, 0))
        return page[a:b].strip()
    items = []
    for sec in walk(parse_html(page)):
        if sec['tag'] != 'section' or not sec['attrs'].get('id'):
            continue
        sid = sec['attrs']['id']
        h2 = next((c for c in sec['children'] if c['tag'] == 'h2'), None)
        subs = []
        for n in walk(sec):
            kids = n['children']
            if 'subsec' in n['attrs'].get('class', '').split() and n['attrs'].get('id') and kids and kids[0]['tag'] == 'h3':
                subs.append((html.escape(n['attrs']['id']), inner(kids[0])))
        li = '    <li><a href="#%s">%s</a>' % (html.escape(sid), inner(h2) if h2 else html.escape(sid))
        if subs:
            li += '\n      <ol class="toc-sub">\n' + ''.join(
                '        <li><a href="#%s">%s</a></li>\n' % (i, h3) for i, h3 in subs) + '      </ol>\n    '
        items.append(li + '</li>')
    if 'id="overview"' in page:
        items.insert(0, '    <li class="toc-top"><a href="#overview"><span data-lang="en">Overview</span>'
                        '<span data-lang="de">Überblick</span></a></li>')
    return '<ol>\n' + '\n'.join(items) + '\n  </ol>'


def title_parts(meta, notes):
    """The tab and brand line (`<name> · <subject> · <ticket>`, else `<title> · <ticket>`) and the heading per language
    (the name, else `Review of <subject>`); MR and ticket stand once each in their header rows."""
    name, ticket = str(meta.get('name') or '').strip(), str(meta.get('ticket') or '').strip()
    if ticket and not TICKET.match(ticket):
        fail('meta.ticket %r is no ticket key' % ticket)
    if len(name) > NAME_MAX:
        fail('meta.name is %d characters, at most %d' % (len(name), NAME_MAX))
    if not name:
        notes.append('meta.name missing: the title shows no name')
    line = ' · '.join(x for x in ([name, str(meta.get('subject', ''))] if name else [str(meta.get('title', ''))]) + [ticket] if x)
    if name:
        return line, [name, name]
    return line, [word + ' ' + str(meta.get('subject', '')) for word in ('Review of', 'Review von')]


def own_mr(mr_base):
    """The pattern of the MR's own number in header text (`MR !123` or `!123`), None without an MR URL."""
    m = re.search(r'/merge_requests/(\d+)$', mr_base)
    return re.compile(r'(?:MR )?!%s(?!\d)' % m.group(1)) if m else None


def state_value(meta, mr_base, suffix):
    """The reviewed-up-to row: the first sha of meta.state shortened, linked to its commit when the MR's project is
    known, with the suffix (branch head) for a branch, MR or PR; other subject types show meta.state as it is."""
    esc = html.escape(str(meta.get('state', '')))
    m = re.search(r'\b[0-9a-f]{7,40}\b', esc)
    if not m or not suffix:
        return esc
    sha = m.group(0)
    project = re.sub(r'/-/merge_requests/\d+$', '', mr_base)
    short = sha[:10]
    if project != mr_base:
        short = '<a href="%s/-/commit/%s" target="_blank" rel="noopener noreferrer">%s</a>' % (
            html.escape(project, quote=True), sha, short)
    return esc[:m.start()] + short + esc[m.end():] + ' (' + lang_pair(suffix) + ')'


def header_notes(meta, mr_base):
    """Notes for a header value that repeats what another row shows: the ticket or the head sha in the subject line,
    the subject's own MR or the ticket in the further sources."""
    out, ticket = [], str(meta.get('ticket') or '').strip()
    subject_line, reference = str(meta.get('subjectLine', '')), str(meta.get('reference', ''))
    key = re.compile(r'(?<![\w/.-])%s(?![\w-])' % re.escape(ticket)) if ticket else None
    sha = re.search(r'\b[0-9a-f]{7,40}\b', str(meta.get('state', '')))
    mr = own_mr(mr_base)
    if key and key.search(subject_line):
        out.append('meta.subjectLine names the ticket, which the Ticket row shows')
    if sha and sha.group(0)[:7] in subject_line:
        out.append('meta.subjectLine names the head sha, which the reviewed-up-to row shows')
    if mr and mr.search(reference) or key and key.search(reference):
        out.append('meta.reference names the MR or the ticket, which their rows show')
    return out


def link_tickets(text, ticket, base=''):
    """Link every key of the ticket's Jira project in escaped header text to `base`; a key inside a branch name, path or
    word stays plain, so `ab/PROJ-1-x` and `UTF-8` are never links. Without a base, keys stay plain."""
    if not ticket or not base:
        return text
    key = re.compile(r'(?<![\w/.-])%s-\d+(?![\w-])' % re.escape(ticket.split('-')[0]))
    return key.sub(lambda m: '<a href="%s%s" target="_blank" rel="noopener noreferrer">%s</a>' % (
        html.escape(base, quote=True), m.group(0), m.group(0)), text)


def slug(text):
    text = ''.join(TRANSLIT.get(c, c) for c in text)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def run_copy_name(meta):
    """The run-folder name of this review: `<key>[-<ticket>][-<name>]-<date>-<short sha or files>-<run>`; None before
    the run id is set (SKILL.md step 5)."""
    # set once at the first copy, so an update (a new sha, a new name or ticket) keeps the earlier run's folder
    if meta.get('runName'):
        return str(meta['runName'])
    if not meta.get('run'):
        return None
    if meta.get('subjectType', 'branch') in NO_MANUAL_TYPES:
        sha = 'files'
    else:
        m = re.search(r'\b[0-9a-f]{7,40}\b', str(meta.get('state', '')))
        if not m:
            return None
        sha = m.group(0)[:10]
    parts = [meta.get('key', ''), slug(str(meta.get('ticket') or '')), slug(str(meta.get('name') or '')),
             str(meta.get('date', '')), sha, str(meta['run'])]
    return '-'.join(p for p in parts if p)


def fill_template(spec, data, diff, blockers):
    """The template with every {{placeholder}} filled, before any writer content goes in."""
    page = TEMPLATE.read_text()
    meta = spec.get('meta', {})
    if not str(meta.get('worktree', '')).strip():
        page = page.replace('Worktree: <code>{{worktree}}</code>. ', '')
    if not gitlab_on(spec):
        # no comments at all for this subject type: one line instead of the filter note and the filter-empty message
        page = re.sub(r'(<div id="gitlab" class="subsec">\s*<h3>.*?</h3>\s*)<p class="note">.*?</p>', r'\1', page, count=1, flags=re.S)
        page = re.sub(r'(<p class="empty" id="gitlab-empty" hidden>).*?(</p>)',
                      lambda m: m.group(1) + lang_pair(['No GitLab comments for this subject type.',
                                                        'Keine GitLab-Kommentare für diese Art von Gegenstand.']) + m.group(2),
                      page, count=1, flags=re.S)
    _, heading, holds, where = SUBJECT_TYPES.get(meta.get('subjectType', 'branch'), SUBJECT_TYPES['branch'])
    sevs = [f['sev'] for f in spec['findings']]
    values = dict((k, str(meta.get(k, ''))) for k in META)
    values.update(subjectHeadingEn=heading[0], subjectHeadingDe=heading[1], blockerHoldsEn=holds[0], blockerHoldsDe=holds[1],
                  changesInEn=where[0], changesInDe=where[1])
    values.update(nFindings=str(len(sevs)), nBlocking=str(sevs.count('blocking')),
                  nNonBlocking=str(sevs.count('non-blocking')), verdictClass='fail' if blockers else 'ok')
    keys = [k for k, _ in CATEGORIES]
    for f in spec['findings']:
        if f['category'] not in keys:
            fail('%s: category %r is not one of %s' % (f['id'], f['category'], ', '.join(keys)))
    kinds = [k for k in KINDS if any(f.get('kind') == k for f in spec['findings'])]
    page = page.replace('        <!-- kindchips: generated by assemble.py from the findings\' kinds -->\n', ''.join(
        '        <button type="button" class="chip" data-filter="kind" data-value="%s" aria-pressed="false">%s</button>\n'
        % (k, k) for k in kinds))
    used = [(k, label) for k, label in CATEGORIES if any(f['category'] == k for f in spec['findings'])]
    chips = ''.join('        <button type="button" class="chip" data-filter="category" data-value="%s" aria-pressed="false">%s</button>\n'
                    % (k, lang_pair(label)) for k, label in used)
    page = page.replace('        <!-- categorychips: generated by assemble.py from the findings\' categories -->\n', chips)
    page = page.replace('{{categories}}', script_json(dict(used)))
    links = gitlab_links(spec, data, diff)
    page = page.replace('{{gitlabLinks}}', script_json(links))
    jira_ticket = str(meta.get('ticket') or '').strip()
    base = ticket_base(meta)
    page = page.replace('{{jiraLinks}}', script_json({'base': base, 'project': jira_ticket.split('-')[0]}
                                                     if jira_ticket and base else None))
    notes = []
    values['titleLine'], (values['headingEn'], values['headingDe']) = title_parts(meta, notes)
    page = page.replace('{{movedNote}}', moved_note(meta))
    mr_base = (spec.get('mrUrl') or '').rstrip('/')
    ticket = str(meta.get('ticket') or '').strip()
    eyebrow, subject_label, state_label, suffix = HEADER_LABELS.get(meta.get('subjectType', 'branch'), HEADER_LABELS['branch'])
    page = page.replace('{{eyebrow}}', lang_pair(eyebrow)).replace('{{subjectLabel}}', lang_pair(subject_label))
    page = page.replace('{{stateLabel}}', lang_pair(state_label))
    page = page.replace('{{stateValue}}', state_value(meta, mr_base, suffix))
    page = page.replace('{{linesChanged}}', lines_changed(meta.get('lines')))
    page = page.replace('{{categoryLegend}}', category_legend()).replace('{{kindLegend}}', kind_legend())
    page = page.replace('{{verdictLine}}', verdict_line(str((spec.get('verdict') or {}).get('word', ''))))
    ticket_row = '    <div><dt>Ticket</dt><dd>%s</dd></div>\n' % link_tickets(html.escape(ticket), ticket, base) if ticket else ''
    page = page.replace('    <!-- ticket row: assemble.py writes it when meta.ticket is set -->\n', ticket_row, 1)
    notes.extend(header_notes(meta, mr_base))
    for k, v in values.items():
        esc = html.escape(v)  # meta.key is a checked slug, so escaping leaves it unchanged
        if k == 'subjectLine' and own_mr(mr_base):
            esc, linked = own_mr(mr_base).subn(lambda m: '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (
                html.escape(mr_base, quote=True), m.group(0)), esc, count=1)
            if not linked:
                notes.append('mrUrl set but meta.subjectLine has no "!<number>" of it: the header does not link the MR')
        if k == 'reference':
            esc = link_tickets(esc, ticket, base)
        page = page.replace('{{%s}}' % k, esc)
    if not values.get('reference', '').strip():
        page = re.sub(r'[ \t]*<p class="further">.*?</p>(<!--.*?-->)?\n', '', page, count=1)
    effort = effort_line(meta)
    if effort:
        page = page.replace('{{effortLine}}', effort)
    else:
        page = re.sub(r'[ \t]*<p class="effort">\{\{effortLine\}\}</p>\n', '', page, count=1)
        if 'effort' not in meta:
            notes.append('meta.effort missing (a run older than the effort line): 4.2 shows no runs and time')
    # filled once the 3.4 fragment is read (main)
    page = page.replace('{{reviewComment}}', REVIEW_COMMENT_MARK)
    for left in re.findall(r'\{\{\w+\}\}', page):
        fail('template placeholder left unfilled: ' + left)
    return page, len(links), notes


def load_spec(path):
    """Parse findings.json, the orchestrator's record; None when it is missing or malformed."""
    if not path.exists():
        fail('missing findings.json')
        return None
    try:
        spec = json.loads(path.read_text())
    except ValueError as e:
        # the position only, as for data.json
        fail('findings.json is not valid JSON at line %d, column %d' % (getattr(e, 'lineno', 0), getattr(e, 'colno', 0)))
        return None
    if not isinstance(spec, dict) or not isinstance(spec.get('findings'), list) or \
            not all(isinstance(f, dict) for f in spec['findings']):
        fail('findings.json must be an object with a findings array of objects')
        return None
    return spec


def node_error(stderr):
    """node --check prints the file:line first and the SyntaxError a few lines later; give both."""
    lines = [l.strip() for l in stderr.splitlines() if l.strip()]
    if not lines:
        return 'node exited non-zero without a message'
    msg = next((l for l in lines if re.match(r'\w*Error\b', l)), '')
    return lines[0] + (' ' + msg if msg and msg != lines[0] else '')


# one Read call holds about 25k tokens; HTML with German text runs near 2.3 bytes per token
READ_PART_BYTES = 45000


def read_parts(text, limit=READ_PART_BYTES):
    """1-based (first, last) line ranges of at most `limit` bytes each (a longer single line is its own part)."""
    parts, start, size = [], 1, 0
    lines = text.split('\n')
    for n, line in enumerate(lines, 1):
        b = len(line.encode('utf-8')) + 1
        if size and size + b > limit:
            parts.append((start, n - 1))
            start, size = n, 0
        size += b
    parts.append((start, len(lines)))
    return parts


# a publish subagent reads its whole batch: about 100k tokens beside its own ~50k, within a 200k context
BATCH_BYTES = 230000
# a larger file is cut into parts, so the page and one part always fit a batch
CHUNK_BYTES = 180000
PUBLISH_DATA = [('findings', 'data'), ('manual', 'manual')]
# batch 1 carries these, so the first version of the page already has its style, script and manual tests
FIRST_BATCH = ['report.css', 'report.js', 'manual.js']


def pushed_files(base, items, var, tail='', limit=CHUNK_BYTES):
    """{file name: script} pushing `items` (JSON texts) onto window.<var>: one file <base>.js, or <base>-1.js,
    <base>-2.js, … of at most about `limit` bytes each when one would be larger; `tail` ends the last file."""
    groups, size = [[]], 0
    for item in items:
        b = len(item.encode('utf-8')) + 2
        if groups[-1] and size + b > limit:
            groups.append([])
            size = 0
        groups[-1].append(item)
        size += b
    names = ['%s.js' % base] if len(groups) == 1 else ['%s-%d.js' % (base, i) for i in range(1, len(groups) + 1)]
    files = {n: '(window.%s = window.%s || []).push(\n%s\n);\n' % (var, var, ',\n'.join(g)) for n, g in zip(names, groups)}
    files[names[-1]] += tail
    return files


def script_tags(files):
    return ''.join('<script src="%s"></script>' % n for n in files)


def split_page(tokenized, tokens, toc, data, manual, limit=CHUNK_BYTES):
    """The report as a page plus files, for the publish: the same document as review.html with the stylesheet, the
    main script, the findings and manual data and each slot moved into a file of its own, so a republish sends and
    reads only what changed. A file over `limit` is cut into parts. Every file keeps one item per line, as
    review.html does."""
    files = {}
    page = tokenized.replace('\x00toc\x00', toc)
    for name in SLOTS:
        var = 'REPORT_SLOT_' + name.upper()
        parts = pushed_files('slots/' + name, [json.dumps(l, ensure_ascii=False) for l in tokens.get(name, '').split('\n')],
                             var, "document.currentScript.insertAdjacentHTML('beforebegin', window.%s.join('\\n'));\n" % var,
                             limit)
        files.update(parts)
        page = page.replace('\x00slot:%s\x00' % name, script_tags(parts))
    findings = pushed_files('findings', [script_json(f) for f in data], 'REPORT_FINDINGS', '', limit)
    files.update(findings)
    files['manual.js'] = 'window.REPORT_MANUAL = %s;\n' % script_json(manual)
    for var, token in PUBLISH_DATA:
        page = page.replace('\x00slot:%s\x00' % token, 'var %s = window.REPORT_%s;\n' % (var, var.upper()))
    a = page.index('<style>')
    b = page.index('</style>', a)
    files['report.css'] = page[a + len('<style>'):b]
    page = page[:a] + '<link rel="stylesheet" href="report.css">' + page[b + len('</style>'):]
    a = page.rindex('<script>')
    b = page.index('</script>', a)
    files['report.js'] = page[a + len('<script>'):b]
    page = (page[:a] + script_tags(findings) + '\n<script src="manual.js"></script>\n<script src="report.js"></script>'
            + page[b + len('</script>'):])
    files['index.html'] = page
    return files


def read_manifest(pub):
    try:
        return json.loads((pub / 'manifest.json').read_text())
    except (OSError, ValueError):
        return {}


def write_publish(pub, files):
    """Write the publish folder and remove the files a previous assemble left that the page no longer loads; returns
    the files that differ from the last publish (manifest.json), index.html always, since every publish sends the
    page."""
    manifest = read_manifest(pub)
    for f in sorted(pub.rglob('*')) if pub.exists() else []:
        if f.is_file() and f.name != 'manifest.json' and str(f.relative_to(pub)) not in files:
            f.unlink()
    changed = []
    for name in sorted(files):
        f = pub / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(files[name])
        if name == 'index.html' or manifest.get(name) != hashlib.sha256(files[name].encode()).hexdigest():
            changed.append(name)
    return changed


def publish_batches(files, changed, limit=BATCH_BYTES):
    """The changed files in publish batches of at most `limit` bytes, one subagent each: every batch sends the page,
    since the Artifact tool takes no update without it, and batch 1 starts with FIRST_BATCH. The other files go
    largest first into the first batch with room, so few subagents run."""
    size = lambda n: len(files[n].encode('utf-8'))
    first = ['index.html'] + [n for n in FIRST_BATCH if n in changed]
    batches = [first]
    totals = [sum(size(n) for n in first)]
    for n in sorted((n for n in changed if n not in first), key=lambda n: (-size(n), n)):
        i = next((i for i, t in enumerate(totals) if t + size(n) <= limit), None)
        if i is None:
            batches.append(['index.html'])
            totals.append(size('index.html'))
            i = len(batches) - 1
        batches[i].append(n)
        totals[i] += size(n)
    return batches


def mark_published(d, names=()):
    """Record files as published: their sha256 into publish/manifest.json, for every file of the publish folder, or
    only for `names` (one batch), keeping the record of the others."""
    pub = d / 'publish'
    if not (pub / 'index.html').exists():
        fail('no publish folder in %s: run assemble.py first' % d)
        return result('assemble.py --mark-published')
    missing = [n for n in names if not (pub / n).is_file()]
    if missing:
        fail('not in the publish folder: ' + ', '.join(missing))
        return result('assemble.py --mark-published')
    paths = [pub / n for n in names] or [f for f in sorted(pub.rglob('*')) if f.is_file() and f.name != 'manifest.json']
    shas = read_manifest(pub) if names else {}
    shas.update({str(f.relative_to(pub)): hashlib.sha256(f.read_bytes()).hexdigest() for f in paths})
    (pub / 'manifest.json').write_text(json.dumps(shas, indent=1, sort_keys=True))
    print('marked %d files as published' % len(paths))
    return 0


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == '--mark-published':
        return mark_published(Path(sys.argv[2]), sys.argv[3:])
    if len(sys.argv) == 3 and sys.argv[1] == '--run-name':
        spec = load_spec(Path(sys.argv[2]) / 'findings.json')
        name = run_copy_name((spec or {}).get('meta') or {}) if spec else None
        if not name:
            fail('no run name: meta.run is not set, or meta.state holds no sha')
            return result('assemble.py --run-name')
        print(name)
        return 0
    if len(sys.argv) != 2 or sys.argv[1].startswith('--'):
        print(__doc__)
        return 2
    d = Path(sys.argv[1])
    spec = load_spec(d / 'findings.json')
    if spec is None:
        return result('assemble.py stopped: findings.json is needed for every check')
    if not complete_findings(spec):
        return result('assemble.py stopped: every finding needs an id, a sev, a kind, a category and a package')
    blockers = check_spec(spec)

    data_json = d / 'data.json'
    data = []
    if data_json.exists():
        data = load_data_json(data_json)
        check_findings(spec, data)
    else:
        fail('missing data.json')
    manual_notes = []
    manual = check_manual(spec, d, manual_notes)
    check_cold_read(spec, data, manual_notes)
    check_placeholders(d, data)

    diff_file = d.parent / 'inputs' / 'change.diff'
    diff = parse_diff(diff_file.read_text()) if diff_file.exists() else {}
    notes = check_anchors(spec, data, diff, diff_file)
    page, n_links, fill_notes = fill_template(spec, data, diff, blockers)
    notes += fill_notes + manual_notes

    # every slot becomes a token first, so writer text that quotes a slot marker can never match one
    tokens = {}
    for name in SLOTS:
        page, n = re.subn(r'<!-- slot:%s\b.*?<!-- /slot:%s -->' % (name, name), '\x00slot:%s\x00' % name, page, flags=re.S)
        if n != 1:
            fail('slot %s found %d times in the template' % (name, n))
    page, n = re.subn(r'/\* slot:data\b.*?/\* /slot:data \*/', '\x00slot:data\x00', page, flags=re.S)
    if n != 1:
        fail('data slot found %d times in the template' % n)
    page, n = re.subn(r'/\* slot:manual\b.*?/\* /slot:manual \*/', '\x00slot:manual\x00', page, flags=re.S)
    if n != 1:
        fail('manual slot found %d times in the template' % n)
    tokens['manual'] = 'var manual = %s;\n' % script_json(manual)
    toc_mark = '  <!-- toc: generated by assemble.py from the section and subsection headings -->'
    page = page.replace(toc_mark, '\x00toc\x00')
    tokens['data'] = 'var findings = %s;\n' % script_json_lines(data)

    known = [f.get('id') for f in spec['findings']]
    points = {}
    abstract = str((spec.get('meta') or {}).get('date', '')) >= VERDICT_SHORT_SINCE
    word = (spec.get('verdict') or {}).get('word', '')
    for name in SLOTS:
        f = d / (name + '.html')
        if not f.exists():
            if name == 'summary' and not abstract:
                tokens[name] = ''  # a run before the findings summary keeps its Blockers in the verdict
                continue
            fail('missing fragment ' + f.name)
            tokens[name] = ''
            continue
        frag = f.read_text().strip('\n').replace('\x00', '')
        if name == 'verdict':
            frag = strip_lead_word(frag, word)
        root = check_fragment(name, frag)
        if name == 'verdict' and root:
            check_verdict(root, word, blockers, known, ids=not abstract)
            if abstract:
                check_verdict_short(root)
                check_verdict_abstract(root)
                check_verdict_no_restate(root)
        if name == 'summary' and root:
            check_verdict_ids(root, blockers if not abstract else [], known, 'summary.html')
            if abstract:
                check_summary(root)
            frag += unchecked_line(spec['findings'])
        if name == 'good' and root:
            check_good(root)
            points = good_points(root)
        if name == 'method' and root:
            check_method_cold_read(root, spec)
            check_method_withdrawn(root, spec)
        frag = link_text(frag, set(known), str((spec.get('meta') or {}).get('ticket') or '').strip(),
                         ticket_base(spec.get('meta')))
        tokens[name] = frag
    page = page.replace(REVIEW_COMMENT_MARK, review_comment(spec, points))
    tokenized = page
    page = re.sub(r'\x00slot:(\w+)\x00', lambda m: tokens.get(m.group(1), ''), page)
    toc = '  ' + build_toc(page)
    page = page.replace('\x00toc\x00', toc)
    publish = split_page(tokenized, tokens, toc, data, manual)

    report_root = parse_html(page)
    for i in duplicate_ids(report_root):
        fail('id "%s" occurs more than once in the report (marker ids are unique per figure copy)' % i)

    de, en = lang_counts(report_root)
    if de != en:
        fail('data-lang blocks differ: de %d, en %d' % (de, en))
    scripts = re.findall(r'<script\b[^>]*>(.*?)</script\s*>', page, re.S | re.I)
    js_file = d / 'inline.js'
    js_file.write_text('\n'.join(scripts))
    try:
        chk = subprocess.run(['node', '--check', str(js_file)], capture_output=True, text=True)
        if chk.returncode != 0:
            fail('inline scripts do not parse: ' + node_error(chk.stderr))
    except FileNotFoundError:
        fail('node not found: inline scripts not checked')

    out = d / 'review.html'
    out.write_text(page)
    sevs = [f.get('sev') for f in spec['findings']]
    print('wrote %s: %d findings (%s), %d slots, de/en blocks %d/%d, %d GitLab links' % (
        out, len(sevs), ', '.join('%s %d' % (s, sevs.count(s)) for s in SEVERITIES), len(SLOTS), de, en, n_links))
    for n, line in enumerate(page.split('\n'), 1):
        size = len(line.encode('utf-8'))
        if size > READ_PART_BYTES:
            # a Read part cannot split a line, so a publish subagent could not read the line's file whole
            fail('review.html line %d is %d KB, over the %d KB one Read part holds: break it (a fragment line or one '
                 'finding of data.json)' % (n, size // 1000, READ_PART_BYTES // 1000))
    copy_name = run_copy_name(spec.get('meta') or {})
    if copy_name:
        print('run copy name: ' + copy_name)
    for name in sorted(publish):
        for n, line in enumerate(publish[name].split('\n'), 1):
            if len(line.encode('utf-8')) > READ_PART_BYTES:
                fail('publish/%s line %d is %d KB, over the %d KB one Read part holds: break the fragment line' % (
                    name, n, len(line.encode('utf-8')) // 1000, READ_PART_BYTES // 1000))
    if len(publish['index.html'].encode('utf-8')) > BATCH_BYTES - CHUNK_BYTES:
        fail('publish/index.html is %d KB, over the %d KB a batch leaves beside one part: move content into a slot' % (
            len(publish['index.html'].encode('utf-8')) // 1000, (BATCH_BYTES - CHUNK_BYTES) // 1000))
    changed = write_publish(d / 'publish', publish)
    print('changed since last publish: ' + ', '.join(changed))
    batches = publish_batches(publish, changed)
    print('publish batches: %d' % len(batches))
    for i, batch in enumerate(batches, 1):
        print('batch %d: %s' % (i, '; '.join(
            '%s %s' % (f, ', '.join('%d-%d' % r for r in read_parts(publish[f]))) for f in batch)))
    for n in notes:
        print('note: ' + n)
    if errors:
        print('FAILED, %d problem(s):' % len(errors))
        for e in errors:
            print('- ' + e)
        return 1
    print('OK: report matches findings.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
