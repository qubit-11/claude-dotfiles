#!/bin/bash
# Diff inputs for a branch, MR or PR, after prepare.sh. Usage: branch-inputs.sh SP WT BRANCH
SP="$1"; WT="$2"; BRANCH="$3"
[ -n "$SP" ] && [ -n "$WT" ] && [ -n "$BRANCH" ] || { echo "usage: branch-inputs.sh SP WT BRANCH"; exit 1; }
[ -f "$SP/state/target.env" ] || { echo "run prepare.sh first"; exit 1; }
. "$SP/state/target.env"
. "$(dirname "$0")/secrets.sh"
cd "$WT" || exit 1
if [ -n "$REMOTE" ]; then   # only a pushed branch is fetched; exit 2 means not pushed, any other failure stops
  git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null; RC=$?
  if [ $RC -eq 0 ]; then
    git fetch "$REMOTE" "$BRANCH" || { echo "fetch of $BRANCH failed: stop and ask the user"; exit 1; }
  elif [ $RC -ne 2 ]; then
    echo "ls-remote failed (exit $RC): stop and ask the user"; exit 1
  fi
fi
printf 'branch %s\n' "$BRANCH" >> "$SP/inputs/subject.txt"
BASE=$(git merge-base "$TGT" HEAD) || { echo "no merge base with $TGT: stop and ask the user"; exit 1; }
# run from the repository root; no "." in the pathspec, it would restrict the diff to the current directory
git diff "$BASE" HEAD -- "${INFL[@]}" > "$SP/inputs/change.diff"
git diff --name-status "$BASE" HEAD -- "${INFL[@]}" > "$SP/inputs/change.files.txt"
git diff --numstat "$BASE" HEAD -- "${INFL[@]}" > "$SP/inputs/change.numstat.txt"
# what the inflators hide, for the report's line count: changed lines per hidden file, secret files by name only
git diff --numstat "$BASE" HEAD | awk -F'\t' 'FILENAME == ARGV[1] { keep[$3]; next } !($3 in keep)' "$SP/inputs/change.numstat.txt" - > "$SP/inputs/inflators.txt"
git log --format='%h %ad %an %s' --date=short "$BASE"..HEAD > "$SP/inputs/change.commits.txt"
git log --format='%h %ad %an %s' --date=short "$BASE".."$TGT" > "$SP/inputs/target.commits.txt"   # the other side
git merge-tree --write-tree "$TGT" HEAD > "$SP/checks/merge-tree.txt"; echo "merge-tree exit $?"
