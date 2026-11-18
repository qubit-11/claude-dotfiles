#!/bin/bash
# Reverses the patch when the marker exists, then checks cleanliness; a tree that is not clean is named, never undone.
# Usage: patch-reverse.sh SP WT
SP="$1"; WT="$2"; L="$1/checks/patch-tests.txt"
[ -n "$SP" ] && [ -n "$WT" ] || { echo "usage: patch-reverse.sh SP WT"; exit 1; }
if [ -f "$SP/checks/patch-applied" ]; then
  P=$(cat "$SP/checks/patch-applied")
  if git -C "$WT" apply --whitespace=nowarn -R "$P" >> "$L" 2>&1; then echo "reverse ok" >> "$L"; rm "$SP/checks/patch-applied"; else echo "reverse FAILED" >> "$L"; fi
fi
ST=$(git -C "$WT" status --porcelain); RC=$?
if [ $RC -ne 0 ]; then echo "status FAILED (exit $RC)" >> "$L"
elif [ -z "$ST" ]; then echo "worktree clean" >> "$L"
else echo "worktree NOT clean" >> "$L"; fi
tail -2 "$L"
