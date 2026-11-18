#!/bin/bash
# Preparation for a branch, MR, PR or patch. Usage: prepare.sh SP WT TARGET SHA [local]
# "local" only after the user chose the local target of a repository without a remote (worktree.md).
# Writes $SP/inputs/subject.txt and $SP/state/target.env (REMOTE, TGT) for the next script.
SP="$1"; WT="$2"; TARGET="$3"; SHA="$4"; LOCAL="${5:-no}"
[ -n "$SP" ] && [ -n "$WT" ] && [ -n "$TARGET" ] && [ -n "$SHA" ] || { echo "usage: prepare.sh SP WT TARGET SHA [local]"; exit 1; }
mkdir -p "$SP/inputs/sources" "$SP/reviews" "$SP/checks" "$SP/report" "$SP/state"   # state/: orchestrator files no reviewer reads
cd "$WT" || exit 1   # every git call reads the review worktree, never the session's start directory
if [ "$LOCAL" = local ]; then
  REMOTE=; TGT="$TARGET"
else
  REMOTE=$(git config "branch.$TARGET.remote")   # the target's remote
  if [ -z "$REMOTE" ]; then   # no upstream: only a single remote is unambiguous
    [ "$(git remote | wc -l | tr -d ' ')" = 1 ] && REMOTE=$(git remote)
  fi
  [ -n "$REMOTE" ] || { echo "no upstream for $TARGET and not exactly one remote: ask the user (worktree.md)"; exit 1; }
  git fetch "$REMOTE" "$TARGET" || { echo "fetch of $TARGET failed: stop and ask the user"; exit 1; }
  TGT="$REMOTE/$TARGET"
fi
# the worktree must already be at the subject sha (for a patch: the base); never record HEAD in its place
[ "$(git rev-parse HEAD)" = "$(git rev-parse "$SHA^{commit}")" ] || { echo "HEAD is not the subject sha: stop"; exit 1; }
printf 'sha %s\ntarget %s%s\n' "$SHA" "$TGT" "$([ "$LOCAL" = local ] && echo ' (local target, not fetched)')" > "$SP/inputs/subject.txt"
printf 'REMOTE=%q\nTGT=%q\n' "$REMOTE" "$TGT" > "$SP/state/target.env"
echo "prepared: target $TGT"
