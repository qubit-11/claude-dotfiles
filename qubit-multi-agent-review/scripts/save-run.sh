#!/bin/bash
# Copies the report and run state into the worktree's run folder. Usage: save-run.sh SP WT R N yes|no [RAW]
# R: run folder relative to the worktree; N: the name `assemble.py --run-name <report dir>` prints; yes = republish of this review
# RAW: for an update of an earlier report, the subfolder for this run's raw outputs, state and diff
# (rerun-<run id>), so the earlier run's stay; the consolidated report/ stays at the run folder's top
SP="$1"; WT="$2"; R="$3"; N="$4"; REPUBLISH="$5"; RAW="$6"
[ -n "$SP" ] && [ -n "$WT" ] && [ -n "$R" ] && [ -n "$N" ] && [ -n "$REPUBLISH" ] || { echo "usage: save-run.sh SP WT R N yes|no"; exit 1; }
f=$(git -C "$WT" rev-parse --path-format=absolute --git-path info/exclude) || exit 1
grep -qxF "$R/" "$f" || echo "$R/" >> "$f"   # shared by the main checkout and every worktree
mkdir -p "$WT/$R"
mkdir "$WT/$R/$N" 2>/dev/null || [ "$REPUBLISH" = yes ] || { echo "$N exists: another review's folder, stop"; exit 1; }
# a run without a report has no review.html yet; `publish-report` for it later is a republish (yes)
[ -f "$SP/report/review.html" ] && { printf '<!doctype html>\n'; cat "$SP/report/review.html"; } > "$WT/$R/$N.html"
mkdir -p "$WT/$R/$N/$RAW"
cp "$SP"/reviews/*.md "$WT/$R/$N/$RAW/"
# the report inputs and run state, so a resumed session can republish after macOS clears the scratchpad
rsync -a --exclude review.html --exclude inline.js "$SP/report/" "$WT/$R/$N/report/"
# the run's own state and diff: an update keeps the earlier run's and puts its own beside its raw outputs
rsync -a "$SP/state/" "$WT/$R/$N/$RAW/state/"
[ -f "$SP/inputs/change.diff" ] && mkdir -p "$WT/$R/$N/$RAW/inputs" && cp "$SP/inputs/change.diff" "$WT/$R/$N/$RAW/inputs/"
echo "saved to $R/$N"
