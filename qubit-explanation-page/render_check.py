#!/usr/bin/env python3
"""Check that an explanation page has no horizontal overflow, in both languages, at 1280 and 390 px,
with every <details> open and again with every done tick (input[data-done]) set, for a page whose ticks fold a box to
its title line. Each width runs in a fresh browser profile and opens every <details> first, so stored done marks never
fold a box before it is measured.

Usage: python3 render_check.py <page.html>
Runs headless Chrome on copies of the page with a small probe script and prints only the widths
(page scrollWidth / viewport innerWidth per language) and, on an overflow, the ids of the sections, subsections
or <details> boxes that are wider than their box, so the overflow goes back to the writer of that part. Headless
Chrome clamps windows below 500 px, so 390 px
is measured inside a 390 px iframe. Exit code 1 on an overflow, 2 when Chrome is missing or the probe fails.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', 'google-chrome', 'chromium', 'chromium-browser']
# the probe measures once the web fonts are in (fonts.ready; a font that fails to load also settles it), so widths are
# the published ones; when fonts.ready never settles, a timer marks the probe incomplete, a failed probe (exit 2)
PROBE = ("<script>(function(){var ran=0;function run(){if(ran++)return;var r=document.documentElement,o=[];"
         "document.querySelectorAll('details').forEach(function(c){c.open=true});"
         "function m(pre){['en','de'].forEach(function(lg){"
         "r.setAttribute('data-lang',lg);var w=[];if(r.scrollWidth>innerWidth){"
         "document.querySelectorAll('section[id],.subsec[id],details[id]').forEach(function(e)"
         "{if(e.offsetParent&&e.scrollWidth>e.clientWidth+1){w.push(e.id)}})}"
         "o.push(pre+lg+':'+r.scrollWidth+'/'+innerWidth+(w.length?'['+w.join(' ')+']':''))})}m('');"
         "document.querySelectorAll('input[data-done]').forEach(function(b){if(!b.checked){b.click()}});m('done.');"
         "r.setAttribute('data-probe',o.join(','))}"
         "(document.fonts?document.fonts.ready:Promise.resolve()).then(run);"
         "setTimeout(function(){if(!ran){ran=1;document.documentElement.setAttribute('data-probe','incomplete')}},4000)})()</script>")
# the probe inside the iframe finishes after its fonts load, so the wrapper polls for its result
WRAP = ('<!doctype html><html><body style="margin:0"><iframe id="f" src="page.html" style="width:390px;height:800px;border:0">'
        '</iframe><script>var t=setInterval(function(){var d=document.getElementById("f").contentDocument,'
        'v=d&&d.documentElement.getAttribute("data-probe");if(v){clearInterval(t);document.body.setAttribute("data-probe",v)}},50)'
        '</script></body></html>')


def chrome():
    for c in CHROME:
        if Path(c).exists() or shutil.which(c):
            return c
    return None


def probe(binary, url, width, profile, height=900):
    try:
        out = subprocess.run([binary, '--headless=new', '--disable-gpu', '--allow-file-access-from-files',
                              '--user-data-dir=' + profile, '--window-size=%d,%d' % (width, height), '--virtual-time-budget=5000',
                              '--dump-dom', url], capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return None
    m = re.search(r'data-probe="([^"]*)"', out.stdout)
    return m.group(1) if m else None


def overflows(res):
    """The probe entries wider than their viewport or naming a box wider than itself; ValueError on a malformed line."""
    over = []
    for p in res.split(','):
        try:
            page, view = p.split(':', 1)[1].split('[')[0].split('/')
            wide = int(page) > int(view)
        except (ValueError, IndexError):
            raise ValueError('malformed probe line')
        if '[' in p or wide:
            over.append(p)
    return over


def with_probe(page):
    """The page as published (the skeleton is added at publish time, so a doctype), with the probe at its end."""
    if not page.lstrip().lower().startswith('<!doctype'):
        page = '<!doctype html>\n' + page
    i = page.rfind('</body>')
    return page[:i] + PROBE + page[i:] if i >= 0 else page + PROBE


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    binary = chrome()
    if not binary:
        print('no Chrome or Chromium found')
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / 'page.html').write_text(with_probe(Path(sys.argv[1]).read_text(encoding='utf-8')), encoding='utf-8')
        (t / 'wrap.html').write_text(WRAP)
        status = 0
        for width, name in ((1280, 'page.html'), (390, 'wrap.html')):
            # one profile per width: the first run's done ticks live in localStorage and would fold the second run's boxes
            res = probe(binary, (t / name).as_uri(), width, str(t / ('profile-%d' % width)))
            try:
                over = overflows(res) if res else None
            except ValueError:
                over = None
            if over is None:
                # no result, a Chrome timeout or a malformed line: a failed measurement, not an overflow
                print('%d px: probe failed' % width)
                status = max(status, 2)
                continue
            print('%d px: %s%s' % (width, res, ' OVERFLOW' if over else ''))
            if over:
                status = max(status, 1)
    return status


if __name__ == '__main__':
    sys.exit(main())
