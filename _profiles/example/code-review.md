# Profile <name>: code review

Applies on top of `qubit-code-review` in <repository>. Leave out a section the
repository does not have; the review then skips that step and says so.

## Worktree

- <How a review worktree is created: a documented procedure, or plain
  `git worktree add`. Name any hook that must not be used because it branches off the
  default branch.>
- <Env provisioning the tests need, and which provisioned file is a secret file that must
  be deleted right after creation.>

## e2e suites without a full stack

| Package | Command |
| --- | --- |
| `<path>` | `<command>` |

<Builds that must run first, so a stale build output does not fail unrelated specs.>

## Full stack

1. <How to check that no other local stack runs, without printing any process's
   environment.>
2. <How to dump the local databases the stack writes, into `$SP/checks/db-before/`.>
3. <Builds, the start command (in the background) and the wait command.>
4. <The command that runs named e2e spec files.>
5. <How to stop the stack's processes by name and restore the databases from step 2.>
