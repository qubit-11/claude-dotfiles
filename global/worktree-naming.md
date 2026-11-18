## Git worktree naming

Name a worktree directory `<TYPE>-<ticket>-<name>`:

| part | meaning | example |
| ---- | ------- | ------- |
| `<TYPE>` | why the worktree exists, UPPERCASE (see below) | `DEV` |
| `<ticket>` | ticket id, lowercase; `noticket` when there is none | `proj-123` |
| `<name>` | short human-readable description | `login-retry` |

Full example: `REVIEW-proj-123-login-retry`

| `<TYPE>` | meaning | lifetime |
| -------- | ------- | -------- |
| `DEV` | own code, based on the main branch (feature or fix alike) | keep until merged |
| `REVIEW` | someone else's code, no own commits | remove after the review |
| `SPIKE` | exploration, not merged as is | remove once findings are recorded |
| `HOTFIX` | own code, based on the release branch | keep until merged and back-merged to the main branch |

A type says what to do with the worktree, not what the ticket is about: the
ticket already says feature or bug. `HOTFIX` means "based on the release
branch", not "fixes a bug"; a bug fix on the main branch is `DEV`.

Always include all three parts. The uppercase type leads, so the purpose of a
worktree jumps out when several exist side by side, and worktrees group by
purpose in a directory listing.

This applies to the worktree directory only. Branch names follow the
repository's own convention.
