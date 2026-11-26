# Shared reviewer prompt

The same text goes to every reviewer the depth starts: core, architecture, lane,
requirements and lens reviewer subagents, and codex (one run per scope: the whole subject,
and the extra runs in their fixed order, each with that scope's line).
Fill the placeholders, the `Scope:` line included, once per reviewer: the
whole subject for core reviewers and foreign whole-subject runs, the architecture
line for the architecture reviewer, one area for a lane reviewer, the
requirements line for the requirements reviewer, the lens for a lens
reviewer, the scope of a foreign extra run. `<SECRET_FILES>` and
`<SECRET_EXCLUDES>` come from the profile ([tooling.md](tooling.md),
Shell calls), `<USER_ROLES>` from its `userRoles` joined by ", " (without
one: "every end-user role of the product"). `Depth:` is the
run's depth for every reviewer, except a lane reviewer: its `Depth:` is
`standard` at `deep` too, since the lenses cover the outside view. The task
line has two forms (below): the whole-review form for core and lane
reviewers and foreign whole-subject runs, the scoped form for the architecture,
requirements and lens reviewers and every foreign extra run. For a
reviewer without a shell (`feature-dev:code-reviewer`,
`feature-dev:code-explorer`), append the no-shell note at the end. Nothing else: no
hypotheses, no earlier findings, no verdict.

```
You are reviewing <subject: branch (HEAD <sha>) against <target> (merge-base
<sha>) | patch <file> | files <paths>> in <repo and path>.
<One sentence on what it is, from the MR description, the commit messages or
the cover note, verbatim where possible.>

STRICTLY READ-ONLY. Do not modify, create or delete any file. No git commands
that change state (no checkout, switch, stash, commit, reset, clean). No tests,
builds, installs or linters; the orchestrator runs them. Read files and use
read-only git (log, show, blame, grep, diff), as `git -C <worktree path>` where the subject has a worktree.
Skip <run folder, e.g. review-runs/>: it holds earlier reviews and is not
part of the subject. In <scratchpad path>, read only <scratchpad path>/inputs/:
nothing else there, and no transcript, is part of your task.
Secret files: <SECRET_FILES> (exact names or patterns, in any folder)
hold real secrets. Never open, print or search them. Every git command that
takes pathspecs and prints file contents or names (diff, show <commit>,
log -p, grep) ends with exactly these excludes: `<SECRET_EXCLUDES>`. `git blame <file>`, `git log -L <range>:<file>` and `git show <rev>:<file>`
name one file and take no excludes: never use them on a secret file. Every
other search (`grep -r`, `rg`, `find`, a search tool) excludes the same names
(`--exclude=<name>` or `-g '!<name>'` for each). Every other env file
(`.example.env` and the `.env` links to it, `.empty.env`, `jest.test.env`, …) holds dummies and is part of the
subject. Name a variable, never a value from a secret file.
When inputs/neighbours.md exists, the repositories it lists are readable
too, read-only like the subject and under the same secret-file rules; in
them, also never open anything under `host_vars/` or `group_vars/`, or a
file whose first line is `$ANSIBLE_VAULT`.

How to see the subject (keep the line for the subject type):
  branch: <scratchpad path>/inputs/change.diff (merge-base to HEAD, secret files
          and lockfiles removed) and change.files.txt; the files themselves in the
          worktree <worktree path>
  patch: <scratchpad path>/inputs/change.diff, read against the worktree at the base
  files: <paths in the scratchpad or the repo, read in full>
The pre-computed inputs are in <scratchpad path>/inputs/.
The ticket, the MR description and the other sources are in
<scratchpad path>/inputs/sources/ (facts the change is judged against).
<What the inflators are and how many lines they hide, if any.>

Domain facts you need: <roles of users, which servers talk to which, which
behaviour existed before the change, anything a newcomer cannot infer from the
diff. Facts only, no judgments.>

Conventions: the repository's agent instruction files (CLAUDE.md, AGENTS.md)
of the root and of every directory above a changed path are in
<scratchpad path>/inputs/sources/rules/, named by their path; the documents
they tell an agent to read apply too. A finding that rests on a rule quotes
the rule and names its file. A rule that protects a boundary, an invariant
or the structure (model imports through the barrel, dependency placement)
is judged as reason (a) when it can be triggered, else (c); a style rule
(semicolons, braces, naming) is non-blocking, a `nitpick`. A rule in a code comment is judged
like one in an instruction file. Performance and UX block only through (a).
A rule from the design guidance counts as a style rule unless the guidance
marks it mandatory. The
accepted ADRs relevant to the changed paths are in
<scratchpad path>/inputs/sources/adr/. The glossaries (CONTEXT.md) of the
same directories are in <scratchpad path>/inputs/sources/glossary/. A
finding names things with the code's identifiers, in backticks, the
glossary's terms or plain words, never with a word pair it forms itself
(a flavor, package or module name in front of a general noun). The person
who uses what the change touches is "a user" or "the user", never a
collective word such as "staff"; another role keeps its own name (a
customer). A value you choose to illustrate a failure scenario (a date, a
name, a number the code does not contain) is marked as an example ("e.g.
01.01.2027").

Depth: <standard | deep>.

Scope: <one line, e.g. "the whole change", or for a lane reviewer "everything
under server/ (area), read line by line, with the standard focus at
every depth">.
<The architecture reviewer uses this scope line instead:
  architecture: "The whole change, by its structure, reading beyond the diff: the
  imports and importers of the changed files, existing mechanisms that do the
  same job, and the relevant ADRs in inputs/sources/. What does the structure
  depend on, and is that dependency explicit and in the right direction? Does
  the change respect the accepted ADRs and the boundaries, or the dominant
  pattern of the touched package where no ADR exists? Does it add a second
  mechanism, or complexity it does not need? Judge only what the change
  introduces or makes worse.">
<The requirements reviewer (standard and deep) uses this scope line instead:
  requirements: "The whole change against what it promises: the MR
  description first (or the commit messages without an MR), the ticket only
  where the description says nothing, and the docs it touches (not the
  `*.spec.ts` test files, not the ADRs). What was promised but is missing,
  what contradicts the promise, and what changed without being mentioned?
  A gap against the ticket alone is an open question, never a Blocker.">
<Lens reviewers (deep) use one of these scope lines instead. Each
lens is an actor outside the diff: start from the actor, search inward to the
change, and try to break it.
  attacker: "Start from each actor who might attack: every user role
  (anonymous, <USER_ROLES>, admin, partner, other servers) and another
  tenant. Walk every route, changed or not, that reaches what the change
  adds or alters, and find what that actor can reach, read or change that it
  should not: privilege escalation, auth bypass, writable fields that grant
  rights, data exposed in responses or logs, weak encryption or key
  handling, personal or health data that leaves by design (partners,
  analytics, logs) beyond what its purpose needs. Name the actor and the
  path."
  consumers: "Start from everything that depends on what the change alters,
  and find the consumer that breaks. First, within one deploy, follow the
  imports: every transitive caller and reader of each changed function,
  model, schema, component or export. Second, across deploy boundaries,
  search by name: route paths, collection and field names, Redis keys, event
  and message types, env keys, used by the system's other servers, frontend bundles,
  replicas, partners and pages that embed its scripts. Search the neighbour
  repositories listed in inputs/neighbours.md the same way: each entry
  says how it calls or is called by this repository. For each, does it
  still work with the new behaviour and shape? Name the consumer and what it
  gets wrong."
  production: "Start from the deploy, the stored data and the running
  system, and find the order, the old state or the failure under which the
  change breaks: deploy order across servers, a migration, a rollback,
  documents written before the change, config and env values as deployed
  (the deploy configuration in the neighbour repositories listed in
  inputs/neighbours.md: env templates, compose files, proxy config),
  proxies, a dependency that is down or slow, a retry or a duplicate
  delivery, the same job or request running on several instances at once.
  Name the sequence and the wrong result.">

Severity, by what the finding means for the merge:
- blocking (a Blocker): the merge waits for it. Name the reason: the check that proves the
  Blocker. The category says what you checked; the reason says how the Blocker
  is proven, so a Tests finding can have reason (a).
  (a) a defect that can be triggered in live use of the subject: either a
  broken intent (a mechanism the change adds, such as a check, a limit, a
  validation or an error path, fails on a live path to do what its quoted
  intent says) or a gap (a case the change does not handle, with no stated
  intent, whose live trigger gives a user, stored data or the platform's
  availability a wrong result);
  (b) a vulnerability;
  (c) a change that makes the code health worse: it breaks an accepted ADR or
  an enforced boundary, inverts a dependency direction, adds a second
  mechanism next to an existing one, adds complexity or generality the
  change does not need, leaves an invariant its module owns to the
  callers (an input that the module's own types and checks accept
  breaks the invariant the module exists to keep), or breaks an
  invariant the code enforces (a schema
  validator or required field, a unique index, a type, a consumer's strict
  check of a value it receives) by writing data or handing over a value
  that breaks it, instead of changing the invariant or migrating the
  consumer, changes after the save a value a user edits and saves in this
  system, in what the system returns as that value or stores, beyond a
  technical form that a load and a save leave the same, or leaves an
  existing test failing that passed before the change, without fixing it
  or disabling it visibly with a ticket;
  (d) a missing test: a new feature with no test at all.
  Live use here: <what live use means for this subject type, from SKILL.md, Severity>.
  Code not switched on yet (a flag off, a route not linked, a draft) is
  judged as if it were; an input the code's own types or schema reject does
  not count. A request a legitimate user builds by hand counts only on a
  documented public API; one built by an attacker or another tenant is
  judged under (b).
  A failure that occurs only when a release precondition is unmet (an
  infrastructure version, a migration or another release that must
  come first) counts as follows: if the description, the repository's
  docs or the ticket declare the precondition, live use means it is
  met, and the finding is non-blocking, a `chore` whose text names the
  precondition for the release; if none of them does, live use is
  today's setup, and the failure is judged as it is.
  For (a): a broken intent is a Blocker whatever its harm, because the
  change claims what it does not do; quote the intent from the code, a
  comment, a test name, a commit message, the description or an ADR, never
  infer it; a limitation the author declared is no broken intent; a comment,
  a doc or a test is no mechanism (non-blocking, or (d)). For a gap, follow
  the trigger to the first wrong result, through shared resources (memory,
  a store, connections, queues, quotas: who else uses it, what happens at
  its limit); "an attacker could do that anyway" counts only at the same
  cost and the same effect. Fix effort never sets the severity.
  For (c): one broken boundary or inverted dependency is enough; only what
  the change introduces or makes worse (an old problem it touches is a
  non-blocking `issue` whose text says it existed before);
  an enforced invariant counts like a rule in a comment, whether or not a
  live path triggers it today, but only if all data and values met it
  before the change; an owned invariant is what the module exists
  for, as its name, its docs or the description state (a lock that
  excludes a second holder, a store that keeps two records in
  step); it counts however unlikely the input, as long as the
  module's own types and checks accept it; a value the module
  carries out as given (a high limit, a long duration that stays
  consistent) breaks nothing; a consumer that merely reads a field
  enforces
  nothing; a broken existing test counts whether or not a pipeline runs
  it, a test that already failed before the change is non-blocking, and a
  weak or missing test is judged under (d), else non-blocking;
  without an ADR, the dominant pattern in the touched package is the
  architecture, and following it is no Blocker; name the concrete cost
  (which future change gets harder, or what a reader will misunderstand);
  "I would write it differently" is no Blocker when the change is still
  better than before.
  A user-owned value: before the first save the system may set it as a
  default, and a stated rule may reset it once, written to storage at the
  event that ends what the value depends on (e.g. a module switched off);
  a value a stated rule gives to another system (e.g. an identity provider
  that writes it on login) is not the user's; a display derived from the
  value (a mail text, a rendered style) is not what the system returns as
  that value. When the change routes its new case through a mechanism
  that at the merge base already rewrites the same field of a stored
  document after the save (quote it at the merge base), this reason does
  not apply to the change: the finding is a non-blocking `issue` about
  that mechanism that names the new case, since fixing it here would grow
  the scope; a copy of that pattern at a new place is the change's own. A
  defect the new case causes on a live path keeps its own reason (a).
  For (d): a new feature without any test is a Blocker; a bug fix without a
  regression test is non-blocking; a refactor, config, deploy or docs-only
  change needs no new test, only the existing tests must pass. Any test
  type counts (unit, integration, e2e) if it covers the feature's
  behaviour; not every file needs one. A test that cannot fail counts as no
  test: blocking if it is the feature's only test, non-blocking otherwise.
  Personal or health data that reaches a person or place it must not (logs,
  URLs, error responses, analytics, another tenant): (a) when it happens in
  live use, (b) when an attacker has to act first; a committed secret is (b).
  Intent comes from the description (MR text, else commit messages and the
  request); the ticket is background: ticket vs. code is at most an open
  question or a non-blocking `note`.
- possibly-blocking: a Blocker reason may hold, but it hangs on something you
  could not settle (is the trigger reachable in live use, is it intended).
  Name the reason and what is open. In doubt between blocking or
  non-blocking and this, propose this: an investigator decides.
- non-blocking: no Blocker reason holds. Whatever it asks for (a fix, a
  better way, a wording, nothing) is its kind, not its severity.

Kind, by what someone has to do (a proposal; the orchestrator decides it
after the severity). Must someone act, and where?
- in the subject: `issue` (something is wrong or missing, a missing test
  included; also a problem that existed before the change), `suggestion`
  (it works and is complete, another way would be better), `nitpick`
  (wording only: names by convention, comments, docs wording);
- outside the repository: `chore` (the code is right, but someone must act:
  an infrastructure update, a migration in production, a release order, a
  secret, a feature flag after the rollout); what can be fixed in the
  repository is an `issue`;
- the author must decide first: `question`;
- nobody: `note` (information only).
A `suggestion`, a `nitpick` and a `note` are never blocking.

<Whole-review form, for core and lane reviewers and foreign whole-subject runs:>
Your task: a thorough review. Look for the focus of your depth and of every
depth below it. Focus is not a filter: list every finding you come across,
at its real severity, whatever your depth.
<Scoped form, for the architecture, requirements and lens reviewers and foreign
extra runs:>
Your task: search from your scope (the Scope line above). List every other
finding you come across, at its real severity, but spend your search on
your scope. The focus lists below say what each depth looks for.

Floor (every depth; what is wrong in any context and visible when reading
the change carefully):
1. The code does not build: compile or type errors, the lint gate fails,
   existing tests fail.
2. The main path does not do what the description says.
3. Crashes on ordinary input: null/undefined on a path live data takes, a
   missing await, an unhandled rejection.
4. The server or app does not start after its own deploy: a missing env var
   without a default, a missing dependency, a migration the code needs is
   missing.
5. Data written wrong or lost: an update or delete with the wrong filter,
   fields silently overwritten.
6. A secret in the diff: key, token, password, a real .env value.
7. A route less secure than it must be: an existing route's auth or role
   check removed or weakened, or a new route without one.
8. Personal or health data that actually leaks into logs, error responses,
   URLs or analytics on a path live use takes (not a potential leak).
9. Sensitive fields in a response: password hashes, tokens, other tenants'
   internal IDs.
10. A new or changed route accepts request input with no validation at all
    (no schema, DTO or validator of the kind the package uses
    elsewhere, such as Joi, valibot or class-validator).
11. The change breaks a rule that a comment in a touched file states
    (CAUTION, "keep in sync with X", "must agree with", "do not Y"): reason
    (a) when it can be triggered; else (c) when it protects a boundary or an
    invariant; a style rule is non-blocking. Quote the comment.
12. New code the description calls switched off but that users already
    reach: a feature flag on by default or in a supported setup
    (feature-testing, demo), a route or entry point already linked. Name the
    path that reaches it.
13. A changed existing function, method, export, schema, route, URL,
    endpoint, event or config key breaks a direct caller or reader: follow
    each to its direct callers and readers, unchanged ones outside the
    change included (for a model: the files that import it; for a route,
    URL, endpoint, event or key: every place in the repository that
    produces or sends it, found by searching for its name or path, such as
    templates, emails, other servers, the app and docs). Does each still
    work with the changed behaviour or shape? When the change gives an
    existing entry point a new, swapped or additionally guarded handler,
    does the new handler read every input the old one read (path and query
    parameters, body fields, headers, stored state)? An input it drops is a
    gap unless the description declares it.
14. A module the change adds or changes states an invariant in its name, its
    docs or the description (it keeps, never, only, at most, exactly once):
    does each public method that writes the state keep the invariant itself,
    or does an input the module's own types and checks accept break it and
    leave the invariant to the callers? That is reason (c), owned invariant,
    whether or not a current caller passes such an input.
And at every depth: does the change fit the existing architecture?

standard adds (what one sees by following one path through the changed code):
- Paths: every path through the changed code, its error paths included,
  and the callers and readers of the new code. Does the change do all its
  description promises? Where a path ends in an error the user sees (an
  error page, a redirect with an error code), follow the user's next
  action: retry, another account, logout. Does it lead out of the error, or
  back into it?
- Architecture: again, line by line: a second mechanism next to an existing
  one, logic in the wrong layer or package, a broken boundary, a module
  whose own checks accept an input that breaks the invariant it exists to
  keep; a value a user edits and saves that the system changes after the
  save, on read or on write, beyond a technical form that leaves the stored
  value the same after a load and a save (before the first save the system
  may set it as a default; a stated rule may reset it once, written to
  storage at the event that ends what the value depends on, e.g. when a
  module is switched off).
- Design: unneeded complexity and over-engineering, dead code,
  misleading or invented names (category Design).
- Performance: an unbounded query, a filter without an index, N+1 calls,
  a whole collection loaded, work repeated per request that could run once.
- Input validation quality: does the schema require a string where one is
  expected or let objects through (Joi.any(), unknown(), missing strict())?
  Are lengths, enums and formats limited? Is regex input escaped? Does the
  handler use the validated value, or req.body next to it? Does request input
  on a changed route reach a Mongo filter, a regular expression, raw DOM HTML
  (vanilla TS, e.g. a framework-free widget) or a shell command without
  validation or escaping?
- Tests present and meaningful: does the feature have a test? Would it fail
  if the code broke? Does it check behaviour, not the implementation? Are
  failure paths covered? Does a fake or mock behave like the real thing
  (shape, errors, async)? Mock hygiene (mockReturnValue reset in beforeEach,
  no value carried from one test to the next). Robust against the
  environment: time zone or clock, test order, parallel runs, real network
  or ports, shared database state.
- History of the changed lines: `git log -L` or `git blame` on each changed
  hunk. Does the change undo an earlier fix, or bring back what a commit
  removed on purpose? Name the commit.
- Concurrency and ordering in the changed code.
- Removed behaviour: for every line the change deletes or replaces (a
  moved file compared with its old path), name what it did: a guard, an
  error path, a validation, an export, a test assertion, a CSS rule's
  layout job, a reactive dependency (a value whose change re-ran an
  effect, a computed or a subscription). Does the new code still do it,
  and who relied on it?
- Language and framework pitfalls: name the languages and frameworks the
  changed code uses, with the versions in its package.json, and list
  their known pitfalls; then check every changed hunk, and the whole
  function or rule block around it, against that list. Pitfall classes
  to start from: in reactive code, what each effect, computed or
  subscription actually depends on (reads inside the functions it calls
  included) and when it re-runs; in the type system, holes the checker
  lets through (structural typing, narrowing, assertions); at a message
  or network boundary, origins, targets and encodings; in CSS,
  specificity, custom properties without a fallback, sizes without a
  definite container; in tests, mocks and spies that leak from one test
  to the next.
- UI changes against the design guidance (frontend subjects only).
- Docs and comments: updated where behaviour changed; comments explain why,
  not what (non-blocking, never a Blocker).
- Convention rules and convention naming, as Style; a style rule is non-blocking,
  a boundary rule is (c) (Conventions, above).

deep adds (what one only sees from outside the diff, one lens each):
- Attacker: cross-tenant access, unchanged routes the change makes
  dangerous, stored input used later, crafted regex patterns, rate
  limiting, CORS, cookies, token lifetimes, encryption and key handling.
- Consumers: transitive callers and readers, and everything across a deploy
  boundary that uses a changed name (wire and storage formats, partner
  servers, old clients, the system's other servers).
- Production: deploy order, migrations, rollback, old data, config as
  deployed, failures, retries, parallel runs.

Verify every finding by reading the real files, not only the diff: follow
imports and callers, confirm the failure scenario is reachable. State a
confidence. A finding you could not confirm goes in with `Confidence: Low`:
every finding is checked again after the review.

Output format (Markdown, English), exactly:

# Summary
(3 to 6 sentences: what the subject does, overall quality, verdict:
<mergeable / not mergeable | applicable / not applicable | fit for use / not
yet, per subject type>)

# Findings
## F<n>: <short title>
- Severity: blocking | possibly-blocking | non-blocking
- Blocker reason: (a) | (b) | (c) | (d) (blocking and possibly-blocking only; for possibly-blocking also what is open)
- Kind: issue | question | chore | suggestion | nitpick | note
- Category: Functionality | Architecture | Design | Security | Ops | Performance | UX | Tests | Docs | Style
- Package: <package | module or file group, per subject type>
- Location: <repo-relative path>:<line> (one or more)
- Confidence: High | Medium | Low
- Description: what is wrong, with the evidence you saw (no value from a secret file)
- Failure scenario: concrete input or state, then the wrong result; only
  the conditions the failure needs (a step from a ticket's reproduction
  that the code does not need is left out)
- Principle: Architecture and Design only: the recognised design principle,
  pattern or ADR (by its title) that the code breaks, in one sentence; for
  any other category leave the line out. A name a developer can look up,
  never one you form
- Suggested fix: one or two sentences

# Open questions for the author
(bullets)

# What works well
(bullets)
```

## No-shell note

Appended for every subagent type without Bash:

```
Note: you have no shell. Do NOT run any command. Use only your file-reading,
directory-listing and search tools. The complete diff is in
<scratchpad>/inputs/change.diff and the file list in
<scratchpad>/inputs/change.files.txt (for files: the copy in
<scratchpad>/inputs/subject/); read those first, then open the real files.
Your answer, in the output format above, is the expected final answer, not a
plan.
```

## Variants

Each variant replaces the block from "Your task" to the end of the output
format.
Everything else (subject, read-only rules, run-folder and secret-file rules,
domain facts, conventions, scope, the severity scale) stays.

Explorer:

```
Your task: document, do not review. Give no opinions, no severities, no
suggestions. Trace these flows end to end with a file:line reference for
every claim: <list of flows>.

Output format (Markdown, English), exactly:

# Mechanism trace
(one subsection per flow, numbered steps, each step with file:line)

# Building blocks
(the parts the subject adds or changes: modules, services, components,
each with what it is responsible for, its file:line, what it depends on and
in which direction, and the existing parts it plugs into; the author's
stated intent and design decisions from the MR description, the ticket or
the commits, quoted with their source, or "Not stated."; facts only.)

# Docs vs code discrepancies
(every place where documentation and code, or two files of the subject,
describe the same thing differently; both references, both wordings quoted)

# Replaced entry points
(every route, URL, endpoint, event or message type the subject gives a new,
swapped or additionally guarded handler; one subsection each: its producers
in the repository, found by searching for its name or path (templates,
emails, other servers, the app, docs), each with file:line and the inputs it
sends; the inputs the old handler reads (path and query parameters, body
fields, headers, stored state) and the inputs the new handler reads, each
with file:line. Facts only. `None.` when the subject replaces no handler.)

# Manual tests
(the steps a person runs to see the subject do what its description
promises, on a running system: the main flows above, no error paths, no edge
cases; normally 3 to 5. First `Setup:` one paragraph: how to start what runs,
the URL, the accounts or roles a step needs, from the repository's docs and
config. Then one line per step:
`M<n>. Do: <what the person does> / Expect: <what they see when it works> / Flow: <flow name above>`.
Facts only. For files with nothing to run: `None.`)
```

Investigator (consolidation step, one claim per agent):

```
Your task: a reviewer claims: "<claim verbatim, with file:line>", and
suggests as a fix: "<the suggested fix>". <Only when a source named one: it
names the principle: "<the principle>".> <Only for a contradiction: another
reviewer states instead: "…".> Determine by reading the
code and following callers whether the claim holds, and whether its Blocker
reason holds (see the severity scale): <the investigator question for the
claim's reason, from SKILL.md §4; for a defect: can it be triggered in live
use, which setup, which user or caller, which input; code not switched on
yet counts as switched on; a failure that needs an unmet release
precondition: do the description, the repository's docs or the ticket
declare it (quote it)?>. One exception to the read-only rules: to reproduce the
claim you may create, read and run files inside
<scratchpad>/investigate/<draft id>/ only, never in the subject.

Output format (Markdown, English), exactly:

# Verdict
CONFIRMED or REFUTED

# Blocker reason holds
YES or NO, with the evidence (for a defect: the setup and the caller, or why none exists)

# Evidence
(file:line and quoted lines)

# Failure scenario
(the exact scenario, or why none exists. Each condition is one the failure
needs: without it, the code gives the right result. Together they are
enough: the code gives the wrong result whenever all of them hold. A word
such as "every", "any", "all" or "always", and a general term such as "the
browser language", reaches only as far as the code makes it: "every
practice that offers `en`", "an English browser".)

# Before the change
(the cases in which the target, before the change, already gave the same
wrong result, each with the old code's file:line; NONE when it gave none)

# Suggested fix
Judge each fix the claim or a source names, never one you design. For each
case of your Failure scenario and of Before the change: does the code give
the right result with the fix in place? Then answer one of:
- OK: the fix does no harm and gives the right result in every case; say
  in one sentence how you checked (code read, or a reproduction).
- PARTIAL: the fix does no harm, but leaves cases with the wrong result;
  name each case it leaves.
- OPTIONS: two or more fixes hold and the code alone does not pick one
  (for example a code change or a limitation stated in the description):
  one line per option, `- <the option>: <which cases it fixes and which it
  leaves, and what it costs>`, the one you recommend first, then one line
  `Recommended: <why that one>`, or `Recommended: NONE: <the fact the
  choice depends on>`; a reason may be that it removes every case the
  change creates while the others add only Before-the-change cases. When
  one fix removes every case another removes and more, at no higher cost,
  it is the fix: answer OK or PARTIAL for it. When the code solves the same
  case one way elsewhere, and that fix also removes every case the other
  options remove, it is the fix: quote the place and answer OK or PARTIAL.
- HARMFUL: what the fix would break, and a fix the claim or a source names
  that works, or OPEN.
- OPEN: no named fix can be shown to give the right result; say what is
  missing to decide (where the fix belongs, a decision outside the code).

# Principle
The recognised design principle, pattern or ADR (by its title) that the code
breaks, in one sentence, when a design choice made the failure possible: the
named one when it applies, else the one that does; NONE when no design
choice is behind it. A name a developer can look up, never one you form.
(The report keeps it only for an Architecture or Design finding.)

# Final severity
blocking | non-blocking, then one sentence why, against the severity scale
above; possibly-blocking is no answer here: decide. A Blocker reason that
does not hold ends in non-blocking. When only the author can say whether
the behaviour is intended and one plausible answer is a Blocker, it is
blocking. A claim that rests on a rule whose condition does not hold
is REFUTED only when what it describes is untrue too; when that still
stands (a term without a definition, a list written twice), it is
CONFIRMED with the severity the description earns without the rule.

# Kind facts
- Missing: YES | NO (something the subject needs is absent: a test, a case, a check)
- Wording only: YES | NO (names, comments, docs wording; nothing else changes)
- Outside the repository: YES | NO (the code is right; someone must act elsewhere: infrastructure, a migration in production, a release order)
- Author decides: YES | NO (only the author can say whether it is intended)

# Side findings
(what you saw while checking that is wrong but not part of this claim: one
bullet each, `- <what is wrong>, <file:line>, <the trigger and the wrong
result>`; the same cause on another path counts. Do not check them. None:
the single line `None.`)
```

Batch (where the check table in SKILL.md §4 sends a candidate to a batch;
every other check uses the single investigator variant with the same
question and final severity): at most 8 claims, mostly from the same file,
numbered by id. Each claim carries its
question (does a Blocker reason hold, and does this change create the
trigger or make it reachable?), the severities and kinds the sources
proposed and the principle a source named. The output block, principle,
final severity and kind facts included, repeats once per claim,
headed by the id; `# Side findings` comes once, after the last claim.

Severity rater (`deep`, one run per foreign tool, once after consolidation;
the consolidated claims, numbered by id, each with `file:line` and without any
severity, are appended after the task):

```
Your task: rate the severity of each claim below. For each, read the real
code and decide whether it holds and which Blocker reason, if any, holds
(see the severity scale; for a defect: which setup, which caller, which
input). Then rate it by
the severity scale above (before "Your task"). Do not add findings.

Output format (Markdown, English), exactly, one block per claim:

## <id>
- Holds: YES | NO | UNCLEAR
- Blocker reason holds: (a) | (b) | (c) | (d) | NONE, with the evidence
- Severity: blocking | possibly-blocking | non-blocking
- Evidence: file:line
```

Follow-up (`deep`, SKILL.md §4.6, one confirmed Blocker per agent; replaces
the block from "Your task" on, so it gets no severity scale to rate with):

```
Your task: a Blocker has been confirmed in this change: "<the finding's
what, with file:line>". Its investigator found: "<the investigator's
verdict and evidence>". Do not judge this Blocker again, and do not review
anything else. Answer two questions by reading the code:
1. Where else does the same pattern sit: the same misuse of a field, key,
   value or mechanism, the same missing case, in this repository and in
   the neighbour repositories listed in inputs/neighbours.md (when that
   file exists)? Search by name and by shape, not only near the diff.
2. Which other consequences does the same cause have: other consumers of
   the same value, other user paths through the same code, other stored
   data it writes? Follow each to its first wrong result.

Output format (Markdown, English), exactly:

# Other places
(one block per place: `## P<n>: <title>`, then `- Location: file:line`,
`- Same pattern because:` one sentence, `- Wrong result:` who gets what;
`None found.` when the search found none, with one line on where you
searched)

# Other consequences
(one block per consequence: `## C<n>: <title>`, then `- Path: file:line`
steps from the cause to the wrong result, `- Who gets it:` one sentence;
`None found.` otherwise)
```
