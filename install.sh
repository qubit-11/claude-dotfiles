#!/usr/bin/env bash
# Wires this repository into Claude Code: a link in the skills folder for each skill and
# for _profiles, the status line link and setting, and the imports of global/*.md in the
# personal CLAUDE.md. Asks nothing and can be run again: each step skips what is already
# done, replaces only links whose target is gone and leaves a differing setup alone.
# With several config folders (CLAUDE_CONFIG_DIR), run it once per folder.
# Profiles are not created here; see _profiles/README.md.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SKILLS="$CLAUDE_DIR/skills"
mkdir -p "$SKILLS"

done_() { printf '  ok    %s\n' "$1"; }
skip()  { printf '  skip  %s\n' "$1"; }
warn()  { printf '  warn  %s\n' "$1"; }

echo "Setting up $REPO for $CLAUDE_DIR"

# Tools: python3 runs the setting and import steps, so without it nothing is set up;
# jq only the status line needs.
if ! command -v python3 >/dev/null; then
  echo "  error python3 is missing; install it and run this script again" >&2
  exit 1
fi
command -v jq >/dev/null || warn "jq is missing; the status line needs it"

# The skills folder belongs to Claude Code (it keeps synced/ and .trash/ there), so the
# repository lives elsewhere and is linked in.
if [ "$REPO" = "$(cd "$SKILLS" && pwd -P)" ]; then
  echo "  error this repository is the skills folder itself; move it out first," >&2
  echo "        as \"Move from the old layout\" in README.md says" >&2
  exit 1
fi

# link_to <link> <target>: creates the link, or replaces it when its target is gone.
link_to() {
  local link=$1 target=$2
  if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
    skip "$link"
  elif [ -L "$link" ] && [ ! -e "$link" ]; then
    ln -sfn "$target" "$link"
    done_ "relinked $link (its old target is gone)"
  elif [ -e "$link" ] || [ -L "$link" ]; then
    warn "$link exists and is not a link to $target; left alone"
  else
    ln -sn "$target" "$link"
    done_ "linked $link"
  fi
}

# 1. Skills: one link per folder with a SKILL.md, and _profiles, which the skills read
#    as ~/.claude/skills/_profiles. Links into this repository whose target is gone
#    (a renamed or removed skill) are removed.
for dir in "$REPO"/*/; do
  name="$(basename "$dir")"
  [ -f "$dir/SKILL.md" ] || [ "$name" = _profiles ] || continue
  link_to "$SKILLS/$name" "${dir%/}"
done
for link in "$SKILLS"/*; do
  [ -L "$link" ] || continue
  target="$(readlink "$link")"
  case "$target" in
    "$REPO"/*) [ -e "$target" ] || { rm "$link"; done_ "removed $link (its target is gone)"; } ;;
  esac
done

# 2. Status line: a link at the path the statusLine setting runs, and the setting, merged
#    into settings.json without touching the other settings. Skipped when the setting
#    already runs this script through another link (a settings.json shared between
#    config folders).
link="$CLAUDE_DIR/statusline.sh"
target="$REPO/statusline/statusline.sh"
runs_target="$(python3 - "$CLAUDE_DIR/settings.json" "$target" <<'PY'
import json, os, sys
path, target = sys.argv[1], sys.argv[2]
command = ''
if os.path.exists(path):
    with open(path) as f:
        command = (json.load(f).get('statusLine') or {}).get('command', '')
same = command and os.path.realpath(os.path.expanduser(command)) == os.path.realpath(target)
print(command if same else '')
PY
)"
if [ -n "$runs_target" ] && [ "$runs_target" != "$link" ]; then
  skip "statusLine setting already runs $target through $runs_target"
else
  link_to "$link" "$target"
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
fi

# 3. General working rules: one import line per global/*.md in the personal CLAUDE.md.
#    An import of the same rule whose file is gone (an older location of this
#    repository) is replaced.
python3 - "$CLAUDE_DIR/CLAUDE.md" "$REPO" "$HOME" <<'PY'
import glob, os, sys
path, repo, home = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(path).read().splitlines() if os.path.exists(path) else []
shown = '~' + repo[len(home):] if repo.startswith(home + '/') else repo
changed = False
for rule in sorted(glob.glob(os.path.join(repo, 'global', '*.md'))):
    name = os.path.basename(rule)
    line = '@%s/global/%s' % (shown, name)
    if line in lines:
        print('  skip  %s already imported' % line)
        continue
    dead = [l for l in lines if l.startswith('@') and l.endswith('/global/' + name)
            and not os.path.exists(os.path.expanduser(l[1:]))]
    if dead:
        lines[lines.index(dead[0])] = line
        print('  ok    replaced %s with %s in %s' % (dead[0], line, path))
    else:
        lines += ['', line] if lines and lines[-1] else [line]
        print('  ok    imported %s in %s' % (line, path))
    changed = True
if changed:
    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
PY

cat <<EOF

Done. Restart Claude Code to load the skills, the status line and the imports.
A working environment's values (profile, ticket links, ticket keys) come later:
see "Add a working environment" in $REPO/README.md.
EOF
