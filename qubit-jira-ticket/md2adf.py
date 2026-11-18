"""Convert a ticket draft (FORMAT.md subset) to an ADF document for Jira.

Usage: python3 -I md2adf.py draft.md "@Name=<accountId>" ... > draft.adf.json
Each "@Name" in the draft becomes a Jira mention of that account.
"""
import json, re, sys
MENTION = dict(a.split("=", 1) for a in sys.argv[2:])
_names = "|".join(re.escape(n) for n in sorted(MENTION, key=len, reverse=True))
TOK = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\)" + ("|" + _names if _names else "") + ")")
def inline(s):
    out = []
    for part in TOK.split(s):
        if not part: continue
        if part in MENTION:
            out.append({"type": "mention", "attrs": {"id": MENTION[part], "text": part}})
        elif part.startswith("**"):
            out.append({"type": "text", "text": part[2:-2], "marks": [{"type": "strong"}]})
        elif part.startswith("`"):
            out.append({"type": "text", "text": part[1:-1], "marks": [{"type": "code"}]})
        elif part.startswith("["):
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", part)
            out.append({"type": "text", "text": m.group(1), "marks": [{"type": "link", "attrs": {"href": m.group(2)}}]})
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append({"type": "text", "text": part[1:-1], "marks": [{"type": "em"}]})
        else:
            out.append({"type": "text", "text": part})
    return out
def para(s): return {"type": "paragraph", "content": inline(s)}
def convert(md):
    blocks = [b for b in md.strip().split("\n\n")]
    doc = []
    for b in blocks:
        lines = b.split("\n")
        if b.startswith("### "): doc.append({"type": "heading", "attrs": {"level": 3}, "content": inline(b[4:])})
        elif b.startswith("## "): doc.append({"type": "heading", "attrs": {"level": 2}, "content": inline(b[3:])})
        elif all(l.startswith("- ") for l in lines):
            doc.append({"type": "bulletList", "content": [{"type": "listItem", "content": [para(l[2:])]} for l in lines]})
        elif all(re.match(r"\d+\. ", l) for l in lines):
            doc.append({"type": "orderedList", "attrs": {"order": 1}, "content": [{"type": "listItem", "content": [para(re.sub(r"^\d+\. ", "", l))]} for l in lines]})
        elif lines[0].startswith("|"):
            rows = [l for l in lines if not re.match(r"^\|[-| ]+\|$", l)]
            trs = []
            for i, r in enumerate(rows):
                cells = [c.strip() for c in r.strip("|").split("|")]
                kind = "tableHeader" if i == 0 else "tableCell"
                trs.append({"type": "tableRow", "content": [{"type": kind, "content": [para(c)]} for c in cells]})
            doc.append({"type": "table", "attrs": {"isNumberColumnEnabled": False, "layout": "default"}, "content": trs})
        else:
            doc.append(para(" ".join(lines)))
    return {"type": "doc", "version": 1, "content": doc}
print(json.dumps(convert(open(sys.argv[1]).read()), ensure_ascii=False))
