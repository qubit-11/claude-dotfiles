#!/bin/bash
# Snapshot of a checkout's state. Usage: snapshot.sh WT OUT_FILE
WT="$1"; OUT="$2"
[ -n "$WT" ] && [ -n "$OUT" ] || { echo "usage: snapshot.sh WT OUT_FILE"; exit 1; }
{ git -C "$WT" rev-parse HEAD; git -C "$WT" stash list; git -C "$WT" status --short --ignored; } > "$OUT"
