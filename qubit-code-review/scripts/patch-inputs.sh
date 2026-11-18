#!/bin/bash
# Inputs for a patch, after prepare.sh (SHA = the base). Usage: patch-inputs.sh SP WT PATCH_FILE NAME
SP="$1"; WT="$2"; SRC="$3"; NAME="$4"
[ -n "$SP" ] && [ -n "$WT" ] && [ -f "$SRC" ] && [ -n "$NAME" ] || { echo "usage: patch-inputs.sh SP WT PATCH_FILE NAME"; exit 1; }
. "$(dirname "$0")/secrets.sh"
mkdir -p "$SP/original"   # outside $SP/inputs: not passed to reviewers, never copied to the run folder
P="$SP/original/$NAME.patch"
cp "$SRC" "$P"
# git lists every path the patch touches, NUL-separated and unquoted; forward lists a rename's or copy's target,
# reverse its source. A secret file among them, or a patch git cannot list, stops the review: ask the user, never dispatch
{ git -C "$WT" apply --whitespace=nowarn --numstat -z "$P" && git -C "$WT" apply --whitespace=nowarn --numstat -z --reverse "$P"; } \
  > "$SP/original/paths.z" || { echo "git cannot list the patch's files: stop and ask the user"; exit 1; }
# exit 0 only when no file name matches a secret file's name or glob; a match (1) or any error stops
python3 -I -c '
import fnmatch, os, sys
paths = [r.split(b"\t", 2)[2] for r in open(sys.argv[1], "rb").read().split(b"\0") if r]
names = {os.fsdecode(p.rsplit(b"/", 1)[-1]) for p in paths}
sys.exit(1 if any(fnmatch.fnmatchcase(n, s) for n in names for s in sys.argv[2:]) else 0)
' "$SP/original/paths.z" "${SECRET_FILES[@]}"; RC=$?
[ $RC -eq 0 ] || { echo "the patch touches a secret file, or the check failed (exit $RC): stop and ask the user"; exit 1; }
cp "$P" "$SP/inputs/change.diff"   # no secret file in it: the reviewers get the patch as it is
git -C "$WT" apply --numstat "$SP/inputs/change.diff" > "$SP/inputs/change.numstat.txt"
git -C "$WT" apply --summary "$SP/inputs/change.diff" > "$SP/inputs/change.summary.txt"
cut -f3 "$SP/inputs/change.numstat.txt" > "$SP/inputs/change.files.txt"   # one path per line; the summary names created and deleted files
: > "$SP/inputs/inflators.txt"   # a patch is reviewed whole: nothing hidden
git -C "$WT" apply --whitespace=nowarn --check "$P" > "$SP/checks/apply-check.txt" 2>&1; echo "apply-check exit $?"
