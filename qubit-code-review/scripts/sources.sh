#!/bin/bash
# Source texts for a branch, MR or PR, after branch-inputs.sh. Usage: sources.sh SP WT [MR number]
# Writes $SP/inputs/sources/commit-messages.txt and, with an MR, $SP/state/mr.json and $SP/inputs/sources/mr-description.md.
SP="$1"; WT="$2"; MR="$3"
[ -n "$SP" ] && [ -n "$WT" ] || { echo "usage: sources.sh SP WT [MR number]"; exit 1; }
[ -f "$SP/state/target.env" ] || { echo "run prepare.sh first"; exit 1; }
. "$SP/state/target.env"
cd "$WT" || exit 1
mkdir -p "$SP/inputs/sources"
BASE=$(git merge-base "$TGT" HEAD) || { echo "no merge base with $TGT: stop and ask the user"; exit 1; }
git log --format='commit %h %ad %an%n%n%B' --date=short "$BASE"..HEAD > "$SP/inputs/sources/commit-messages.txt"
echo "commit messages: $(git rev-list --count "$BASE"..HEAD)"
[ -n "$MR" ] || exit 0
glab mr view "$MR" -F json > "$SP/state/mr.json" || { echo "glab mr view $MR failed: stop and ask the user"; exit 1; }
# the JSON is read by path and argv, never spliced into program text
python3 -I -c '
import json, sys
d = json.load(open(sys.argv[1]))
head = "# MR !%s: %s\n\nURL: %s\nAuthor: %s\nSource: %s -> %s\n\n" % (
    d["iid"], d["title"], d["web_url"], d["author"]["username"], d["source_branch"], d["target_branch"])
open(sys.argv[2], "w").write(head + (d.get("description") or "") + "\n")
print("mrUrl %s\nsha %s" % (d["web_url"], d["sha"]))
' "$SP/state/mr.json" "$SP/inputs/sources/mr-description.md" || { echo "mr.json unreadable: stop and ask the user"; exit 1; }
