#!/usr/bin/env bash
# Wires this repository into Claude Code: the status line link and setting, and the
# imports of global/*.md in ~/.claude/CLAUDE.md. Asks nothing and can be run again:
# each step skips what is already done and leaves a differing setup of the user alone.
# Profiles are not created here; see _profiles/README.md.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
mkdir -p "$CLAUDE_DIR"

done_() { printf '  ok    %s\n' "$1"; }
skip()  { printf '  skip  %s\n' "$1"; }
warn()  { printf '  warn  %s\n' "$1"; }

echo "Setting up $REPO"

# 1. Status line: a link at the path the statusLine setting runs.
link="$CLAUDE_DIR/statusline.sh"
target="$REPO/statusline/statusline.sh"
if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
  skip "status line link exists"
elif [ -e "$link" ] || [ -L "$link" ]; then
  warn "$link exists and is not a link to $target; left alone"
else
  ln -s "$target" "$link"
  done_ "linked $link"
fi

# 2. statusLine setting, merged into settings.json without touching the other settings.
python3 - "$CLAUDE_DIR/settings.json" "$link" <<'PY'
import json, os, sys
path, command = sys.argv[1], sys.argv[2]
settings = {}
if os.path.exists(path):
    with open(path) as f:
        settings = json.load(f)
current = settings.get('statusLine')
if current == {'type': 'command', 'command': command}:
    print('  skip  statusLine setting exists')
elif current:
    print('  warn  statusLine is set to something else in %s; left alone' % path)
else:
    settings['statusLine'] = {'type': 'command', 'command': command}
    with open(path, 'w') as f:
        json.dump(settings, f, indent=2)
        f.write('\n')
    print('  ok    statusLine setting added to %s' % path)
PY

# 3. General working rules: one import line per global/*.md in the personal CLAUDE.md.
claude_md="$CLAUDE_DIR/CLAUDE.md"
touch "$claude_md"
for rule in "$REPO"/global/*.md; do
  line="@~/.claude/skills/global/$(basename "$rule")"
  if grep -qxF "$line" "$claude_md"; then
    skip "$line already imported"
  else
    [ -s "$claude_md" ] && [ -n "$(tail -c1 "$claude_md")" ] && echo >> "$claude_md"
    printf '\n%s\n' "$line" >> "$claude_md"
    done_ "imported $line in $claude_md"
  fi
done

cat <<EOF

Done. Optional, later:
  - A profile for a company's repositories: ask Claude to create one from
    _profiles/example/ (see _profiles/README.md), or copy _profiles/<name>/
    from the old computer. Without one the skills use general defaults.
  - Ticket links in the status line: $CLAUDE_DIR/statusline.local.env
    (format in the header of statusline/statusline.sh).
  - The values a rule in global/ asks for (e.g. ticket keys for worktree
    naming) go beside its import in $claude_md.
EOF
