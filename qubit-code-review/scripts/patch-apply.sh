#!/bin/bash
# Applies the original patch for the tests; on success writes the marker $SP/checks/patch-applied.
# Usage: patch-apply.sh SP WT NAME
SP="$1"; WT="$2"; P="$1/original/$3.patch"
[ -n "$SP" ] && [ -n "$WT" ] && [ -f "$P" ] || { echo "usage: patch-apply.sh SP WT NAME"; exit 1; }
echo "tested patch: $P" > "$SP/checks/patch-tests.txt"
if git -C "$WT" apply --whitespace=nowarn "$P" >> "$SP/checks/patch-tests.txt" 2>&1; then
  echo "$P" > "$SP/checks/patch-applied"; echo "apply ok" >> "$SP/checks/patch-tests.txt"
else
  echo "apply FAILED: suites not run" >> "$SP/checks/patch-tests.txt"
fi
tail -1 "$SP/checks/patch-tests.txt"
