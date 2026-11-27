# Profiles

A profile holds everything about one working environment that the skills must not
contain: URLs, ticket projects, branch names, secret files, related repositories, user
roles, and the commands and procedures of its repositories. The skills stay general; a
profile makes them fit one place.

A profile has two levels:

```text
_profiles/<company>/
  config.json               the company's values: its hosts, tracker, ticket projects
  <skill>.md                the company's rules for one skill (how tickets are written, reply language)
  repos/<repo>/
    config.json             one repository's values: branches, secret files, related repositories
    repo.md                 its procedures by topic: worktree, builds and tests, e2e, commits, …
```

Every repository is equal: there is no main repository. A company folder holds as many
`repos/` entries as it has repositories; an entry may also stand for a repository that
is only read, never worked in (one without `remotes`, reached through `related`).

Only `example/` is in the repository. It is the template: a company with three
repositories. A profile is a copy of it in a new folder (`_profiles/<company>/`), with the
values filled in and the unused parts removed. Every other folder here is ignored by git
and stays on this machine.

## How a skill finds its profile

Every skill asks one script, run from inside the repository or one of its worktrees:

```bash
python3 ~/.claude/skills/_profiles/profile.py                  # <company>/<repo> and folder, <company> and folder, or "none"
python3 ~/.claude/skills/_profiles/profile.py get <key>        # a value as JSON, the repository's over the company's
python3 ~/.claude/skills/_profiles/profile.py doc <skill>      # the company's <skill>.md, then repo.md: one path per line, or "none"
python3 ~/.claude/skills/_profiles/profile.py secret-files     # secret file names or globs
python3 ~/.claude/skills/_profiles/profile.py secret-excludes  # the same as git pathspec excludes
python3 ~/.claude/skills/_profiles/profile.py related [out]    # the related repositories as Markdown
```

An entry matches when one of its `remotes` names a remote of the repository, as
`<host>/<project path>` or a shorter prefix (`git.example.com/group` matches every
project of that group; the remote's name does not matter). The longest matching entry
wins, so a repository entry beats its company's host; at equal length the repository
entry wins. When the remotes (a fork, a mirror, a second remote) match two repository
entries or two companies, `profile.py` names them on stderr and uses the longest; the
secret files then come from all of them. A repository of the company's host without an entry of its own gets the
company's values only. In a folder without any git remote, `get`, `doc` and `related` use
the only company when exactly one exists, so a ticket can be drafted there; they never
pick a repository there. A repository whose remotes match nothing (another host, a local
path) has no profile.

**Secret files never fall back to another profile.** They are the repository entry's
`secretFiles`, else a broad set (`.env`, `.env.*`, `*.env`, `.envrc`, key and certificate
files and more; `FALLBACK_SECRETS` in `profile.py`), plus the company's `secretFiles`.
Without a matching profile they are the broad set alone. A review of an unknown
repository then leaves out more files, never fewer. Read them with `secret-files`, not
`get secretFiles`, which shows one level's raw value.

## One fact, one place

- **Values** (`config.json`) are read by skills and scripts; **text** (`<skill>.md`,
  `repo.md`) is read by the model. No text names a branch, a ticket key or a project key:
  it refers to the key that holds it (`productionBranches`, `ticketProjects`).
- **Each section lives on one level.** What holds for the whole company goes in
  `<skill>.md`; what differs per repository goes in `repo.md`. When a section of the same
  name appears on both, the repository's applies, and `profile.py doc` writes a warning
  to stderr: that is a mistake to clean up, not a way to configure.
- **Nothing is copied from a source that has it.** The tracker knows its projects' names
  and descriptions, so the profile lists only the keys; a repository's own documents hold
  its rules, so a section may be a pointer to them.

## Company config.json

| Key | Used by | Meaning |
| --- | --- | --- |
| `remotes` | all | `<host>` or `<host>/<group>` prefixes: every repository there belongs to the company |
| `ticketBrowseUrl` | code-review | the tracker's browse URL; a ticket key is appended to it. Without it, keys in reports stay plain text |
| `ticketProjects` | ticket | the keys of the tracker projects the team works in. Tickets and repositories are many-to-many, so no repository holds a key; to pick a project, `qubit-ticket` reads each key's name and description from the tracker |
| `secretFiles` | code-review, explanation-page | secret files every repository of the company may have; added to each repository's |
| `reposRoot` | code-review (`deep`) | the folder that holds the checkouts named by `dir`; default: the folder beside the main checkout |

## Repository config.json

| Key | Used by | Meaning |
| --- | --- | --- |
| `remotes` | all | `<host>/<project path>` of this repository; without it the entry is only a target of `related` |
| `dir` | code-review (`deep`) | the folder name of its checkout under `reposRoot`; it may differ from the remote path |
| `role` | code-review (`deep`) | one line: what this repository is to the others |
| `mainBranch` | ticket-start, claim-check | the branch development happens on; default: the remote's `HEAD` |
| `productionBranches` | ticket-start, claim-check | what customers run now, and the base of a hotfix; several for several countries or variants |
| `candidateBranches` | claim-check | the next version under test, when there is such a branch |
| `versionTags` | claim-check | `git tag -l` patterns for a version, with `{version}` for the number (`v{version}.*`) |
| `secretFiles` | code-review, explanation-page | names or globs of the files that hold real secrets, in any folder. Every other env file is treated as code |
| `userRoles` | code-review | the end-user roles of the product, for the attacker lens |
| `related` | code-review (`deep`) | names of other entries under `repos/`: the repositories this one calls or is deployed by |

**Choosing a branch.** The main branch is the default. "Production", "customers",
"hotfix" mean the one entry of `productionBranches`; with several, the one the source
names (a country, a variant), else the skill asks. "Next release" means
`candidateBranches` the same way; "since version X" the tags `versionTags` yields for X.
Without the key, the skill asks; it never guesses from branch names.

## Documents

Company `<skill>.md` holds the company's rules for one skill: the tracker and the team
rules for tickets (`ticket.md`), how to read a ticket (`ticket-start.md`), the ticket line
of a merge request (`merge-request.md`), the platform's review-thread calls and the reply
language (`code-review-response.md`), the re-review calls (`code-review.md`).

Repository `repo.md` holds its procedures by topic. The section names are fixed, so
skills find them; each skill names the ones it reads:

| Section | Read by |
| --- | --- |
| `Worktree` | ticket-start, claim-check, code-review |
| `Review worktree` | code-review |
| `Branch name`, `Hotfix`, `Ignored folders` | ticket-start |
| `Build and tests` | ticket-start, claim-check |
| `e2e` | ticket-start, claim-check, code-review, merge-request |
| `Full stack` | code-review |
| `Commits` | merge-request, code-review-response |
| `Merge requests` | merge-request |
| `Review threads` | code-review, code-review-response |

The `e2e` table marks each suite that needs the full stack; only the others run on their
own, the rest only by the steps of `Full stack`. A skill reads every path `doc <skill>`
prints, in order. Without a document or a section
it uses its general rules and says what it skipped.
