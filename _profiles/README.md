# Profiles

A profile holds everything about one working environment that the skills must not
contain: URLs, project keys, secret files, neighbour repositories, user roles, and the
commands and procedures of its repositories. The skills stay general; a profile makes
them fit one place.

Only `example/` is in the repository. It is the template: copy it to a folder of your
own (`_profiles/<name>/`), fill in the values, and remove what you do not need. Every
other folder here is ignored by git and stays on this machine.

## How a skill finds its profile

Every skill asks one script, run from inside the repository or one of its worktrees:

```bash
python3 ~/.claude/skills/_profiles/profile.py                 # name and folder, or "none"
python3 ~/.claude/skills/_profiles/profile.py get <key>       # a value of config.json as JSON
python3 ~/.claude/skills/_profiles/profile.py doc <skill>     # path of <skill>.md, or "none"
python3 ~/.claude/skills/_profiles/profile.py secret-files    # secret file names or globs
python3 ~/.claude/skills/_profiles/profile.py secret-excludes # the same as git pathspec excludes
python3 ~/.claude/skills/_profiles/profile.py neighbours [out] # neighbour repositories as Markdown
```

A profile matches when one of its `remotes` names a remote of the repository, as
`<host>/<project path>` or a shorter prefix (`git.example.com/group` matches every
project of that group; the remote's name does not matter). In a folder without any git
remote, `get`, `doc` and `neighbours` use the only profile when exactly one exists, so
a Jira ticket can be drafted there. A repository whose remotes match no profile has
none: another project on the same host never gets this one's rules.

**Secret files never fall back to another profile.** Without a matching profile they
are a broad set (`.env`, `.env.*`, `*.env`, `.envrc`, key and certificate files and
more; `FALLBACK_SECRETS` in `profile.py`). A review of an unknown repository then
leaves out more files, never fewer.

## config.json

| Key | Used by | Meaning |
| --- | --- | --- |
| `remotes` | all | `<host>/<project path>` (or a prefix) of each repository this profile is for |
| `ticketBrowseUrl` | multi-agent-review | Jira browse URL; a ticket key is appended to it. Without it, keys in reports stay plain text |
| `secretFiles` | multi-agent-review, explanation-page | names or globs of the files that hold real secrets, in any folder. Every other env file is treated as code |
| `neighbourRepos` | multi-agent-review (`high`) | `{dir, role}` of each repository the code calls or is deployed by, checked out beside the main checkout; `reposRoot` overrides that folder |
| `userRoles` | multi-agent-review | the end-user roles of the product, for the attacker lens |

## Documents per skill

`<skill>.md` holds what a skill needs as prose: the worktree route and the e2e
commands for the review (`multi-agent-review.md`), the merge and push rules for merge
requests (`merge-request.md`), the Jira facts and team rules for tickets
(`jira-ticket.md`). A skill without its document uses its general rules and says what
it skipped.
