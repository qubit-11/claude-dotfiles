# GitLab comments

For a branch, MR or PR, every finding gets the comment a team member will post
on the MR: the finding's `gitlab` field (format in
[report-sections.md](report-sections.md)). The findings writer writes it in
step 6, from the settled finding in `findings.json`, after its severity is set.
Posting happens only when asked. The renderer adds the prefix from the
finding's kind and severity (`**issue (blocking):**`,
`**nitpick (non-blocking):**`; Labels, below), so a reader sees at once what
holds the merge and what can be skipped.

## Labels

The comments follow [Conventional Comments](https://conventionalcomments.org):
`**<label> (<decoration>):** <subject>`, then the discussion. This section
and the two maps in the template are the convention's only place: the
review decides severity and kind (SKILL.md §4), and a change of convention
changes only the maps below and the renderer's `LABEL` and `DECORATION` in
`review-report-template.html`; `test_assemble.py` keeps them the same.
Conventional Comments labels a comment; the skill labels a finding, and
each of its comments carries the finding's label.

| Kind | Label |
| --- | --- |
| `issue` | `issue` |
| `question` | `question` |
| `chore` | `chore` |
| `suggestion` | `suggestion` |
| `nitpick` | `nitpick` |
| `note` | `note` |

| Severity | Decoration |
| --- | --- |
| `blocking` | `blocking` |
| `non-blocking` | `non-blocking` |

The prefix always carries the decoration, and it stays English in the
German text too: label and decoration are the convention's keywords, and a
re-review reads them back ([re-review.md](re-review.md)). `text` never
starts with a prefix; `assemble.py` fails one that does.

## Where it goes

Read the anchor off the inflator-free diff in the scratchpad. A hunk header
`@@ -a,b +c,d @@` covers new-side lines c to c+d-1.

A comment's place is `path`, `startLine` and `endLine`, named as in SARIF's
`region`. `path` is the file's path from the repository root, as the diff
names it without `a/` or `b/` (the new path of a renamed file, the old path
of a deleted one).

| The line that causes the finding | `anchor` | Place |
| --- | --- | --- |
| an added line, or a context line inside a hunk | `line` | `path`, `startLine`: the new line |
| a removed line | `line`, `side: 'old'` | `path`, `startLine`: the old line |
| in a file of the diff, outside every hunk | `file` | `path`, `startLine`, the line also named in the text; the path must be in the diff (a renamed, binary or mode-only file counts, without `startLine`) |
| in a file outside the diff | `mr` | `path`, `startLine`, named in the text |
| in no file (a missing test, a description that does not match the change) | `mr` | none |

When the cause is a block of adjacent lines (a statement over several lines,
a condition, a function head), a `line` comment gets `endLine`: the last line
of the block, on the same side as `startLine`. The range stays tight around
the cause, and every line of it lies in one hunk, since GitLab selects only
shown lines. A second place in the same file is named in the text, not
covered by a longer range. The link opens `startLine`; the report names the
lines to select in GitLab ("select lines 11–13").

One entry per finding, on the line where the cause sits; two at most. The
second only for a second file of the diff that the author has to edit and
would not reach from the first comment. A finding that lists several small
places (stale docs, wrong names) is one list entry: one line per place, the
place in backticks and what is stale in a few words, then the `Suggestion:`.

When posting through the API (Posting, below): a context line needs both `old_line` and
`new_line` in the position; an added line needs only `new_line`.

## What it says

Every comment exists in English and German. The report shows the one that
matches the language switch, and Copy copies the one on screen: the team
discusses in both languages, the reviewer picks per thread. The findings
writer writes the English; the translator writes the German by the same
rules, word limit included, shortening the German rather than dropping a
fact. The translator writes the German from the finding, with the English
comment as the template for its facts, not sentence by sentence: German word
order, no English technical idiom carried over word for word (a field that
"carries" a value "enthält" it, a "consumer" of a field is the code that
reads it), and the German gender of a loanword (das Literal, das Array).

The comment is generated, not written by the person who posts it, so it
describes and never speaks for anyone, in either language. Short, precise,
on point and neutral: the code is the subject of every sentence that
describes it ("`x` resets …", "The route responds …"; "`x` setzt … zurück",
"Die Route antwortet …"); the change a `suggestion`, a `chore` or a
`nitpick` names, and the change after `Suggestion:`, is an infinitive
("Read the limit from …"; DE "Das Limit aus … lesen"), never an address.
No word addresses the reader or includes the writer (the forbidden words in
"Check before publishing"). The renderer adds the prefix (Labels, above);
`text` starts directly with the subject.

The parts follow the kind. Each starts with its subject, the point in one
sentence, then the discussion:

| Kind | Subject | Then |
| --- | --- | --- |
| `issue` | the finding: what goes wrong | the effect, then `Suggestion:` or `Question:` (the parts below) |
| `suggestion` | the improvement itself ("Read the limit from `config.maxRetries`.") | its benefit, one sentence |
| `question` | the question, ending in "?" | its basis: what in the code or the description raises it |
| `chore` | the step outside the repository ("Update Redis to 7.2 before this release.") | why: what fails without it |
| `nitpick` | the change ("`cnt` → `count`.") | nothing, or the rule it follows |
| `note` | the information | nothing |

`Suggestion:` (DE `Vorschlag:`) stands only in an `issue`: there it marks
the way out after the problem, while a `suggestion` is the way out itself.
100 words at most in all (code blocks do not count). An `issue` is these
parts, in this order:

1. **Finding** (DE Befund): what the commented code does and where that
   goes wrong, the identifier in backticks; where the cause lies in another
   file, that one place as `path:line`. When the cause is the shape of a
   key, field name or record, that shape in backticks (`<sessionId>:<itemId>`).
   An Architecture or Design finding (one with a `principle`) also says here
   why the code should be different. The reason is the concrete
   consequence: what goes wrong, gets harder or has to be kept in step
   ("…, so a changed `timezone` moves the openings but not the
   announcements"). The principles, by their acronym where one exists (DRY,
   KISS, YAGNI), else by the name a developer can look up, join that
   sentence at most as a short mention ("…, a second source next to
   `User.timezone` (single source of truth)", "… (DRY, KISS)"); they stand
   as the reason only when the finding has no concrete consequence. Never a
   sentence or paragraph of its own, never a label per clause: a principle
   standing apart reads as a slogan, and one that carries the argument
   reads as dogma.
   A finding with `before` ends this part with one sentence on when the
   target branch already gave the wrong result ("On the target branch this
   already happened with `LANG=en`."; DE "Auf dem Zielbranch trat das
   bereits mit `LANG=en` auf."), so the author sees that the fix covers those cases too.
2. **Effect** (DE Folge), one sentence: the concrete case in which it goes
   wrong and what then happens. For a non-blocking issue, that case is when it starts
   to hurt: "Once `X` is enabled, …" (DE "Sobald `X` aktiv ist, …").
   A finding with `triggers` (two or more) has a list here instead: a blank
   line, then one line per trigger, each starting with "- ", the case and
   its wrong result in one or two short sentences, the worst first, three
   at most. Further triggers stay in the report.
3. A blank line, then **`Suggestion:`** (DE **`Vorschlag:`**) and the change as a
   short hint: what to change and where, the code in backticks. A finding
   with `removes` says what its change also removes, in plain words ("this
   also removes both daylight-saving errors of the planned timer"); a
   finding another one removes names that change as the alternative ("the
   error disappears when the planned timer is replaced by the 30 s
   `setInterval`"). Never a finding id, never "see the other comment": the
   author reads each comment alone. The change is a sentence, or a plain
   example code block (```` ```ts ````) the author checks and adapts. A GitLab
   `suggestion` block, which the author can apply with one click, only when
   the change is tiny and certain and only rewords the commented lines (a
   comment, docs, a string, a `nitpick`) and replaces them exactly; on a
   range it holds every line from `startLine` to `endLine`. A change to code
   logic is never a `suggestion` block.
   A finding with `fixLeaves` adds one sentence after the suggestion: the
   cases the change leaves ("The login page keeps the browser language.").
   A finding with `options` or `fixOpen` has **`Question:`** (DE
   **`Frage:`**) instead of the suggestion, since the review cannot pick
   the fix and the author decides. With `options`, one question in the
   order of `options` that names each option and, where the words allow,
   what it fixes ("Should the pick get its own cookie name, which fixes
   both cases, or is the one-time effect accepted and stated in the
   description?"), then one sentence with the recommended option and its
   reason when the check gave one ("The own cookie name is the safer
   choice, since it also covers returning visitors."); a finding with `removes` says it in the option that
   removes the other error. With `fixOpen`, one question on what is open,
   from `fixOpen`. These two labels, `Suggestion:` (always one fix) and
   `Question:`, are the only ones of this part; they name its content, not
   the severity. An `issue` with an open fix stays an `issue`: the problem
   is certain, only the way out is open. A `question` is one where only the
   author can say whether there is a problem at all.

The comment uses the author's words, so the author understands it without
the report. Every noun that names a thing of the code or the domain is one
of these:

- an identifier from the code, in backticks;
- a term from the glossary of the package (`CONTEXT.md`, copied to
  `inputs/sources/glossary/`); a German comment uses the German word the
  glossary gives for it, else a plain German word for the same thing;
- a plain word for a general thing (calendar, customer, request, field);
- for the person who uses what the subject changes, "a user" or "the user"
  (DE "ein User", "der User"), never a collective word such as "staff"
  or "Personal"; another role in the same text keeps its own name (a
  customer);
- a value chosen only to illustrate (a date, a name, a number that the code
  does not contain) is marked as an example: "e.g. 01.01.2027" (DE "z. B.
  01.01.2027"); a value the code holds stands without it;
- a key combination names every platform the code binds ("Ctrl+Z / Cmd+Z",
  DE "Strg+Z / Cmd+Z"), or the action itself ("undoes once");
- in the finding part of an Architecture or Design comment, the names in the
  finding's `principle`, by acronym where one exists (DRY, KISS, YAGNI),
  else as a developer looks it up (single source of truth, dependency
  inversion, an ADR by its title); a German comment keeps the name German
  developers use, often the English one.

Where the finding's text uses a word that is none of these, such as a word
pair the review formed by putting a flavor, package or module name in front
of a general noun, the comment uses the identifier or the glossary term that
word stands for.

The comment stands without the report. A general word that names one
specific thing (the formula, the page, the group, the row) names that thing
at its first mention: its identifier or its value in backticks, or its UI
label in quotes. The author reads the comment beside the code, not beside
the report, so a thing only the report introduced has no referent there.

```text
Unclear: `Row.type` becomes `string`, so the row can carry its formula.
Clear:   `Row.type` becomes `string`, so the row 'Total' can store its formula `a + b - c` there.
```

Each sentence carries one statement, with no semicolon chains. The comment
names one cause. With one trigger it names that trigger's worst effect.
With two or more `triggers` it lists them, since together they show why the
suggested change is the right one: with one trigger named, the author can
fix that case and close the thread. The trigger lines count towards the 100
words. Further callers, numbers, second effects of one trigger and
alternatives stay in the report. Every identifier and path in
backticks. The comment of a finding no investigator could settle
(`unchecked`) asks instead of stating: the observed fact, then one sentence
starting with "Why" or "Should" (DE "Warum" or "Sollte"); its kind and
severity, and so its prefix, stay as decided.

A finding with `tickets` gets `Ticket: <keys>` as the comment's last line,
which the renderer appends; the writer never writes it.

## Example

A blocking `issue`, posted as `**issue (blocking):** ` and the text:

```text
`retryCount` is reset to `0` in the `catch` instead of incremented. If the target server stays unreachable, the loop in `sendWithRetry` never ends and blocks the queue.

Suggestion: increment `retryCount` in the `catch` and stop at `MAX_RETRIES`.
```

```text
`retryCount` wird im `catch` auf `0` gesetzt statt erhöht. Ist der Zielserver dauerhaft nicht erreichbar, endet die Schleife in `sendWithRetry` nie und blockiert die Queue.

Vorschlag: `retryCount` im `catch` erhöhen und ab `MAX_RETRIES` abbrechen.
```

A blocking Design `issue` with two `triggers` and a `principle`; the principle is the
reason inside the first sentence:

```text
`openSeats` is stored as `capacity - booked`, a derived value kept beside the bookings against the single source of truth, so every write path has to keep it in step. It goes wrong in two cases:

- A booking cancelled by the payment provider is removed without a write to `openSeats`. The course shows one seat too few.
- Two bookings at the same moment both read the old value. The course is overbooked.

Suggestion: drop `openSeats` and count the bookings of the course when it is read.
```

```text
`openSeats` wird als `capacity - booked` gespeichert, ein abgeleiteter Wert neben den Buchungen entgegen der Single Source of Truth, den jeder Schreibpfad nachziehen muss. Das geht in zwei Fällen schief:

- Eine vom Zahlungsanbieter stornierte Buchung wird ohne Schreiben in `openSeats` entfernt. Der Kurs zeigt einen Platz zu wenig.
- Zwei gleichzeitige Buchungen lesen beide den alten Wert. Der Kurs ist überbucht.

Vorschlag: `openSeats` entfernen und die Buchungen des Kurses beim Lesen zählen.
```

A non-blocking `suggestion`, posted as `**suggestion (non-blocking):** ` and the text;
the subject is the improvement, no `Suggestion:`:

```text
Read the retry limit from `config.maxRetries` instead of the literal `3` in `sendWithRetry`. The queue's other senders already take it from there, so one setting tunes all of them.
```

```text
Das Retry-Limit aus `config.maxRetries` lesen statt aus dem Literal `3` in `sendWithRetry`. Die anderen Sender der Queue nehmen es schon von dort, so stellt eine Einstellung alle ein.
```

A non-blocking `nitpick` on a comment line, a tiny and certain rewording, so a
GitLab `suggestion` block:

````text
The comment names the old limit.

```suggestion
// retries up to MAX_RETRIES times, then gives up
```
````

## Check before publishing

`assemble.py` checks the mechanical rules and fails the report: `line` and
`file` anchors inside the diff, a range in one hunk with `endLine` after
`startLine` and on a `line` comment only, the place fields each anchor needs, at most two entries, the word limit,
forbidden words, finding ids and tool names. For a finding with `triggers`,
each language has one "- " line per trigger, three at most, and the trigger
lines count towards the word limit. No text starts with a prefix
(`**…:**`). `Suggestion:` (DE `Vorschlag:`) stands only in an `issue`; an
`issue` with `options` or `fixOpen` has `Question:` (DE `Frage:`) in each
language and no `Suggestion:`. With GitLab comments, `notes.coldRead`
records the cold read (below), its counts adding up. The forbidden words, as whole
words:

- English: `you`, `your`, `yours`, `I`, `we`, `our`, `ours`, `us` (not
  followed by a hyphen or a digit, so `us-east-1` passes), `let's` (also with a curly apostrophe), `please`.
- German: `du`, `dich`, `dir`, `ich`, `wir`, `uns`, `euch`, `euer`, `bitte`;
  `dein`, `deine`, `deinem`, `deinen`, `deiner`, `deines`; `unser` with the
  same endings; `eure`, `eurem`, `euren`, `eurer`, `eures`; and the formal `Sie`, `Ihr…`, `Ihnen`, which
  count only capitalised. A sentence-initial `Sie` or `Ihr…` (at the start, or
  after a full stop, an exclamation or question mark, or a colon) passes, since it may mean "it" or "its"; `Ihnen` always fails; a lowercase `ihr` passes.

The writer still checks the facts:

- Every `line` anchor lies inside a hunk of the diff, a range in one hunk.
- Every noun that names a thing of the code or the domain is an identifier,
  a glossary term or a plain word (What it says).
- A general word that names one specific thing names it at its first
  mention (What it says).
- The text reads as the finding's `what`, `why`, `principle` and `fix` cut
  to their core, with the same facts and no new ones; no condition is
  dropped from a case and none is added, and no word such as "every" or
  "all" and no general term ("the browser language") reaches further than
  in the finding ("an English browser"); a finding with a
  `principle` names it inside its finding part as the reason, never in a
  sentence of its own; one without names none.
- No value from a secret file, no finding id, no reviewer or tool name.
- Both languages say the same, and neither contains a forbidden word from
  the list above.

## Cold read

The writer and the translator know the report, so neither notices a word
that only the report explains, and a check by its own author never does.
After the translator and before `assemble.py`, one reader without the report
reads every comment as the author will: beside the code at its place,
without the finding. Brief: [tooling.md](tooling.md), Claude subagents,
Cold reader.

- **Input.** `python3 <skill dir>/cold_read_input.py "$SP/report" <worktree>`
  writes `$SP/state/cold-read-input-en.md`: per comment a neutral label
  (`C1`, `C2`, … in list order, no finding id, no severity), its place, the
  code around it (12 lines before and after, the commented lines marked; a
  removed line from the old side of the diff; an `mr` comment without a path
  gets the MR title and description from `inputs/sources/mr-description.md`
  when it exists) and the English text. It also writes
  `$SP/state/cold-read-labels.json`, which maps each label to its finding;
  the reader never gets it. The German packet, `cold-read-input-de.md`,
  comes from the same script with `--de`, and only once the reader's English
  notes (`$SP/state/cold-read-en.md`) exist: the reader paraphrases every
  English comment before it sees a German one, so a gap in one language is
  never filled from the other.
- **What the reader names**, per label and language: the claim in its own
  words; `ref`, a word whose referent it finds neither in the comment nor in
  the code shown (the name of a design principle, pattern or ADR is no
  `ref`: a developer looks it up, the code never shows it), or a pronoun or
  demonstrative ("it", "this method") that two things of the comment fit; `calque`, German only, a sentence that reads as translated
  (an English idiom word for word, a wrong gender, English word order), with
  an idiomatic rewrite. Then, per label, `mismatch`: a difference between the
  English and the German claim. A label without an item is `ok`.
- **Routing.** The orchestrator maps the labels to findings with the labels
  file. A `ref` in the English goes to the findings writer; a `ref` in the
  German only and every `calque` go to the translator; a `mismatch` goes to
  the writer when the English is wrong, else to the translator. A changed
  English text then goes to the translator with its German set to `TODO-DE`,
  as for any fix ([tooling.md](tooling.md), Translator). The orchestrator
  never fixes a comment in place.
- **Second round, the last.** The comments these fixes changed get one more
  cold read: `cold_read_input.py "$SP/report" <worktree> --name cold-read-2
  --since cold-read` takes only the comments whose text changed since the
  first round, under their first-round labels. What that round names is
  fixed or left; there is no third round.
- **Record.** `notes.coldRead` in `findings.json`, both rounds together:
  `{"comments": <n>, "rounds": 1 | 2, "items": {"ref": <n>, "calque": <n>,
  "mismatch": <n>}, "fixed": <n>, "left": ["F<n> <type>: <reason>"]}`.
  `comments` is the number of comments in `data.json`, all of them read;
  `fixed` plus the entries of `left` is the sum of `items`. The method
  section names it ([report-sections.md](report-sections.md), 4.2).
  `assemble.py` fails a report with GitLab comments without it, unless the
  report was published before the cold read existed.

## Posting (only when asked)

The skill posts nothing on its own; a team member copies the comments from
the report. When the user explicitly asks to post them through the API, read
the MR's head right before the first post (`glab mr view <n> -F json`, field
`sha`) and compare it with the reviewed sha (`meta.state`). A different head
posts nothing: tell the user both shas and let them choose between
reviewing the new commits first and posting anyway, since a comment on a
moved MR can land on the wrong line or on code that is gone. The same head:
post each comment once, at its anchor, in the language the user names. A
comment with `endLine` gets a `line_range` with `start` and `end` in its
position, each with its `line_code`, `type` (`new`, or `old` for removed
lines) and line numbers.
