#!/bin/bash
# Runs one test suite in the patched tree, only while the marker exists. Usage: patch-suite.sh SP WT COMMAND...
SP="$1"; WT="$2"; shift 2
[ -n "$SP" ] && [ -n "$WT" ] && [ $# -gt 0 ] || { echo "usage: patch-suite.sh SP WT COMMAND..."; exit 1; }
[ -f "$SP/checks/patch-applied" ] || { echo "patch not applied: suite not run"; exit 1; }
cd "$WT" || exit 1   # the patched tree, never the session's start directory
"$@"
