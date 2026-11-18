# Ticket format

The ticket is German. It serves three readers, top to bottom. Everyone, the PM included,
reads the title and the first section: the Zusammenfassung of a story or bug, the
Kontext and Ziel of an epic or initiative. The developer and the AI agent read on
to the end. QA checks the Akzeptanzkriterien under Ziel, with fresh eyes and without
test steps; the MR's "Tested" section later records what the author checked.

## Size

Judge the size against the type the planner intends, and warn; never split or retype:

- **Too big for a story or bug**: Ziel is more than one outcome (two results that could
  be checked apart), its sentence does not fit in two lines, or the description stays
  over 600 words after cutting. Suggest two tickets, or an epic (team rule: at most five
  stories).
- **Not ready**: the outcome depends on a decision nobody has made yet ("measure, then
  decide"). Suggest a clarification ticket whose Ziel is that decision; the follow-ups
  wait for it.
- **Too small**: the change is smaller than its ticket would be. Suggest no ticket (the
  `dev` commit type needs none), or one ticket for several such fixes.

An epic or an initiative may have a wide scope; its text stays short.

## Skeleton

A reader sees the structure before reading a word: sections are `##` headings without
numbers, the groups inside a section are `###`, and below them stand short lists or tables. One
skeleton serves every type: a type leaves parts out, never moves them. The skeleton
shows the shape to copy.

```md
## Zusammenfassung                                            <- story and bug

<Two or three sentences: what happens or is missing today, what that means for the
user, and what is true afterwards (Rules, Zusammenfassung).>

## Kontext

<Epic and initiative: only this paragraph, no groups. Initiative: two or three
sentences: what the work is for, what exists already, what a reader must know. Epic:
one or two sentences: what is missing today, in the words of the business. Never the
Ziel in the negative.>

**User Story:** Als <Rolle> möchte ich <Funktion>, damit <Nutzen>.   <- a real user

### Problem                                          <- something goes wrong today

- <What goes wrong, for whom, beyond the Zusammenfassung.>
- <The consequence.>

### Beobachtet                                                      <- bug only

<date>, <environment>, <device, browser>.

1. <step on the page where it was found, e.g. a customer's page>
2. <step>

- **Gesehen:** <what was seen>

### Reproduktion                                                    <- bug only

**Voraussetzungen:**

- <a setting, and where in the UI it is set>
- <the data needed, with example values marked „z. B.“>

1. <step>
2. <step>

- **Erwartet:** <behaviour>
- **Tatsächlich:** <behaviour>

### Befund                                          <- bug, when a cause is known

*geprüft*: <how>, <date>   or   *Vermutung*

- <the cause, one fact per bullet>

## Ziel

<One sentence: what is true afterwards. This is the definition of done.>

### Akzeptanzkriterien                                       <- story and bug

- <One whole sentence: what happens, for whom, and where it shows.>
- <The behaviour that must stay unchanged, when there is one.>

### Umfang                                             <- epic and initiative

- <epic: what the epic means, as a group of behaviours in general words; never a list
  of its stories (they show under the epic) and never a ticket key. Initiative: the
  principles the outcome follows; no detail that belongs to an epic or story, no
  enumeration in parentheses; Out of Scope at the same level>
- <each level stays at its own altitude: what a level below already says is not
  repeated above>


### Voraussetzungen                                               <- story only

- <a setting, a version or the data a tester needs to see the criteria>

### Entscheidungen                                <- agreements with others only

- <what was agreed> (abgestimmt mit <@person, a team or a document>)

### Out of Scope

- <behaviour a reader would expect in this ticket, left out> (<story/bug: the ticket that covers it>)

## Abhängigkeiten

- <what must come first and why, when it is no ticket; a ticket goes in as a Blocks link>

## Offen

- <A question the implementer must answer.>
- <At most one item "Vermutete Lösung: …", marked as such.>
```

Leave out each line in angle brackets that does not apply, and a heading with nothing
under it. A story or bug always has Zusammenfassung and Ziel; Kontext holds at least
the User Story or the Problem, or a bug's Beobachtet and Reproduktion, else its heading
goes. A bug states its Voraussetzungen under Reproduktion, never a second time under
Ziel.

Out of Scope draws the border to what a reader would expect in this very ticket, in
any type; for an epic, that is mostly the border to its sibling epics. It does not
repeat what one level up already leaves out: an epic does not repeat its initiative's
Out of Scope. In an epic or initiative each line names the left-out behaviour in the
words of the product (such as the topic a sibling epic is named after), never a ticket
key: that level stays strategic, and where the behaviour lives shows in the plan. In a
story or bug, the detail level, each line may name the ticket that covers the
behaviour; that is the one place for a ticket key in the text (Markup).

An epic or initiative starts with a short Kontext paragraph, then the Ziel; it has no
Zusammenfassung and no groups under Kontext. The Ziel is one sentence, and one sentence
is only understood with its context, so the Kontext gives that context: for an
initiative, what the work is for, what exists already and what a reader must know;
for an epic, what is missing today. It says something the Ziel does not: a sentence
that only states the Ziel in the negative ("heute buchen sie noch nicht mit
der neuen Buchungsstrecke") is cut, and so is a sentence about the state of the children, which
goes stale as soon as the next one is done ("die erledigten Epics stammen aus der Zeit
vor dem Neuzuschnitt"). An epic or initiative has no Beobachtet, Reproduktion, Befund or Akzeptanzkriterien, makes no
claim about the code (no *geprüft* line, branch, route or service name: that evidence
belongs to its stories), and never lists its child tickets: Jira shows them under the
parent, and a copy in the text goes stale.

The skeleton is the minimum, not the limit. When the topic needs something the skeleton
has no place for (requirements, screenshots, stored data, a rollout order, a partner
interface), add a `##` section with a plain German heading, after Ziel. The rules below
and the budget apply to it as to every other section.

## Layout

- **Heading levels.** The Jira summary is the page title, so the description has no `#`.
  Sections are `##`, groups inside a section are `###`; no level is skipped and none is
  deeper than `###`.
- **No numbers.** Neither `##` nor `###` headings carry numbers: the heading already
  names the section, and a section keeps the same heading in every ticket, whichever
  sections a ticket leaves out. Lists are bullets too, Offen included: an answered
  question is removed, and numbers would shift under the comments that cite them. Only
  steps whose order matters (Beobachtet, Reproduktion) are numbered.
- **Headings in normal case**, never in capitals: „Out of Scope“, not „OUT OF SCOPE“.
- **At most five bullets in a list.** A section with more items splits them into `###`
  groups by topic (for requirements, e.g. "Wer entscheidet", "Während einer Buchung",
  "Links und Parameter").
- **Facts with the same shape go into a table**: two or more items that each name the same
  attributes (a beta flag with channel and action; a rollout gate with its ticket; a
  release phase with its start and end). A table has at most four columns, and every cell holds
  a whole statement, never a keyword the reader must decode.
- **One thought per bullet**, said so that a reader who was not in the investigation
  understands it.

## Markup

| What | Markup | Example |
|---|---|---|
| Anything one types or searches for in code: identifiers, files, packages, branches, commits, routes, query parameters, fields, beta flags, env variables, error codes, commands | `inline code` | `referrerCode`, `POST /api/users/:id/referrer`, `booking-web` |
| Text the user sees in the UI: buttons, messages, menu entries | „German quotes“ | „Jetzt kostenpflichtig buchen“ |
| A label at the start of a bullet or line | **bold** | **Erwartet:**, **User Story:** |
| The status of a claim | *italic* | *geprüft*, *Vermutung* |
| Console or log output | a code block of at most five lines, in Reproduktion or Befund | the first lines of a stack trace |
| A link | `[text](url)` | [Buchungsseite](https://app.example.com/…) |

Product names stay plain text (the profile's `jira-ticket.md` names them).

**Ticket keys only in the Out of Scope of a story or bug.** A relation to another
ticket is a Jira link (`Blocks` for an order, the profile's relates link type otherwise), and the parent is
the `parent` field; the text names no key for them. A story's or bug's Out of Scope is
the exception: its line answers where the left-out behaviour is done instead, Jira has
no link type for that, and a key in the text stays valid and becomes a link. An epic or
initiative names no key at all.

## Rules

The rules follow the ticket from top to bottom; the last three hold for all of it.

1. **Title.** A bug: the symptom and the condition under which it occurs ("Chat-Widget
   startet nicht auf Wix-Seiten, die globale Browser-Objekte sperren"). A story: the
   outcome. A clarification ticket: the decision that is pending ("Klären, ob die
   native Einbettung das iframe ablöst"), never an outcome nobody has decided. Never
   the fix. About ten words.
2. **Zusammenfassung** (story, bug, clarification ticket; an epic or initiative has a short
   Kontext instead, Skeleton). Two or three sentences, about 40 to 80 words; the reader may
   stop after it, and for many readers it is the whole ticket. A bug tells where and
   when it happens, what the user does and then sees, what that means for them, and
   what is true afterwards. A story tells what is missing or goes wrong today, what
   that costs, and what is true afterwards. A clarification ticket tells what is to be
   decided and why it is still open. The words are those of the UI and of the user: a
   name only developers use (a code area, a service, an error code, an internal step)
   is said in plain words or moved to Kontext. Every statement agrees with Kontext.
3. **User Story.** Only when a real user gains something: a customer, or a user of the
   practice. Never a developer as the role. One sentence in the form of the skeleton.
4. **Problem**, in any type, whenever something goes wrong today and has a consequence
   for someone; when something is only missing, there is no Problem group. It holds
   what the Zusammenfassung does not already say: numbers, who else is hit, the
   mechanism.
5. **Beobachtet and Reproduktion** (bug) are two things. Beobachtet says where the bug
   was found, often production or a customer's page, where nobody may change data,
   with the steps that led to it, so anyone can look at it again.
   Reproduktion says how anyone provokes it on an instance of their own: the settings
   and data it needs, then the steps. A Reproduktion always runs on one's own instance
   (local or a test server), so it does not say so. It names no one's own instance and
   no local data state, since nobody else has them; it describes what to set up
   instead. The admin UI comes first; a direct data change only when the UI has
   no way, always with how to undo it. Neither carries a status line: the bug was
   reproduced before the ticket (SKILL.md, Verify).
6. **Ziel is an outcome, not a place, in one sentence.** "Jede erfolgreiche Zahlung
   wird erfasst", not "die Webhook-Hooks im Zahlungsserver". A code location appears only
   inside Befund, as where the cause was seen. Details go below it (Akzeptanzkriterien,
   Umfang), never into a second sentence; the context goes into the Kontext or
   Zusammenfassung above it. In an epic or initiative the Ziel names who gains what, in
   the words of the business
   („Alle Kunden buchen im Web mit der neuen Buchungsstrecke statt mit der alten
   und verlieren dabei keine Funktion (Feature Parity).“). A term the
   ticket uses later (a phase gate, a criterion) is introduced in the Ziel, as a label in
   parentheses; what it means goes under Umfang, never as a group of its own, and
   whatever it excludes goes under Out of Scope.
7. **Akzeptanzkriterien.** Each is one whole sentence that someone who was not in the
   investigation understands: what happens, for whom, where it shows, and why when
   that is not obvious. No internal words ("Submit", a collection, a job name), no test
   steps, no code. Each has a source: the Ziel, an Entscheidung (in this ticket or in a
   ticket linked in Jira), behaviour that stays unchanged, or a
   requirement the planner set in the session. A criterion with no source becomes a
   question under Offen. Bullets, never checkboxes.
8. **Voraussetzungen** (story) say what a tester needs to see the criteria: settings
   and where they are set, versions, data. No steps.
9. **Entscheidungen hold only agreements with others**: with another developer, the
   PM, a designer, another team, or a document such as an ADR. Each names who took
   part; no date. What the planner fixed alone is no Entscheidung but the requirement
   itself: it goes into the Akzeptanzkriterien or Out of Scope, without a name. A
   decision about the implementation goes into the MR, where it holds once the MR is
   merged. Never write an agreement the skill inferred; with none, leave the heading
   out. A person is a Jira mention of their account (`@Name` in the draft), so Jira
   links and notifies them; a team or a document stays plain text. The account ID
   comes from `atlassianUserInfo` for the user, `lookupJiraAccountId` for anyone else;
   with no unique match, write the name as plain text.
10. **Every claim about the code or a cause carries its status**: *geprüft* with how
    and when, *Vermutung*, or it is a question under Offen. A claim without a status is
    cut. The status line under a heading covers its bullets; a bullet whose status
    differs starts with its own (*Vermutung*: …). An epic or initiative makes no such
    claim at all (Skeleton).
11. **No implementation plan**: no file lists, no steps to change the code, no
    components to change, no test scripts, no decisions about the implementation.
12. **Budget**: a story or bug aims at 500 words; an epic or initiative at 200.
    Count the description without table pipes and divider rows:
    `sed -e 's/|/ /g' -e '/^[ -]*$/d' draft.md | wc -w`.
    - Over 500: cut in this order: bullets that repeat another section, code detail
      outside Befund and Reproduktion, then Kontext down to the Problem's consequence.
      Cut whole bullets; never shorten sentences into fragments to save words.
    - Over 600 after cutting: stop cutting and report the ticket as too big (Size).
      Suggest the split; the planner decides.

## Example (bug, shortened)

```md
## Zusammenfassung

Auf manchen Kunden-Websites, die mit Wix gebaut sind (z. B. shop.example.com),
startet das Chat-Widget nicht: Besucher sehen nur die eingeklappte Leiste, sie klappt
nicht auf, und nach 30 Sekunden bricht der Start ab. Die Besucher erreichen so den
Support des Kunden nicht. Danach startet das Widget auf diesen Seiten wie auf
allen anderen.

## Kontext

### Beobachtet

2026-10-28, Produktion, Desktop, Chromium.

1. shop.example.com öffnen.
2. Auf das Widget warten.

- **Gesehen:** die Leiste bleibt eingeklappt, nach 30 s Timeout.

### Reproduktion

**Voraussetzungen:**

- eine Testseite mit eingebundenem Chat-Widget, die vor dem Laden des Widgets
  `EventTarget.prototype` nicht beschreibbar macht, wie Wix.

1. Die Testseite öffnen.
2. Auf das Widget warten.

- **Erwartet:** das Widget klappt auf.
- **Tatsächlich:** die Leiste bleibt eingeklappt, nach 30 s Timeout.

### Befund

*geprüft*: Wix-Viewer-Modell und Konsole, 2026-10-28

- Wix macht u. a. `EventTarget.prototype` nicht beschreibbar.
- `zone.js` wirft beim Laden des Cores.

## Ziel

Das Widget startet auf Seiten, die globale Browser-Objekte sperren.

### Akzeptanzkriterien

- Auf shop.example.com klappt das Widget auf Desktop und mobil auf.
- Auf Seiten, die keine Browser-Objekte sperren, startet das Widget wie bisher.

## Offen

- Prod liefert das Widget von `stable` aus: braucht es auch dort einen Fix?
```

The example has no Problem group: the Zusammenfassung already says what goes wrong and
what it means, and Beobachtet shows it.

## Jira facts

- Through the API with `contentFormat: "markdown"`, `##` and `###` headings, tables,
  inline code, code blocks, numbered and bulleted lists, bold and italic arrive as
  formatting.
- `- [ ]` does not become a checkbox; it arrives as a bullet with the text "[ ]".
  Checkboxes exist only in ADF (`taskList`), and the tickets use none: the
  Akzeptanzkriterien are bullets.
- Markdown has no mention: `@Name` arrives as plain text, and the tools accept only
  `markdown` and `adf` (no `html`). A description with a mention goes as ADF, on create
  and on edit alike: save the draft, run
  `python3 -I md2adf.py draft.md "@Name=<account ID>"` (this folder) and pass its
  output with `contentFormat: "adf"`. Never invent an account ID. Read the ticket back
  once: the mention returns as the account, not as text.

## Paste rules (Markdown output only)

For text the user pastes into Jira: headings `#` and `##` only, with a blank line before
and after, so each `###` becomes a **bold** line; short lines; no inline backticks (write
identifiers in **bold** instead), no code blocks, no `<` or `>`, no `|` outside tables,
no `---`. A pasted `@Name` stays text: write the name plain, and the user types the
mention in Jira. Direct creation through the API needs none of this.

## Checklist (run it on the draft)

- The title names symptom and condition, the outcome, or the pending decision; no fix.
- Story or bug: the Zusammenfassung alone tells someone who knows only the UI what
  happens, what it means for the user, and what is true afterwards; it agrees with
  Kontext.
- Epic or initiative: a short Kontext paragraph (initiative two or three sentences, epic one
  or two) that says something the Ziel does not, then the one-sentence Ziel; no
  Zusammenfassung, no Kontext, no claim about code.
- No `#`; sections `##`, groups `###`, none numbered; headings in normal case; no list
  longer than five bullets.
- Every set of same-shaped facts is a table, and every cell is a whole statement.
- Every identifier, route, flag or error code is in inline code; every UI text is in
  „quotes“.
- A User Story names a real user, never a developer.
- A bug's Reproduktion works on any own instance: settings and data, no personal
  instance, no local data state; production or customer pages only under Beobachtet.
- Beobachtet has numbered steps and what was seen; neither group has a status line.
- Ziel is one outcome in one sentence. Each Akzeptanzkriterium is a whole sentence
  without internal words, with where it shows, and has a source.
- Every Entscheidung is an agreement with others and names who took part; a person as
  an `@` mention. None is the planner's own choice or about the implementation.
- Every claim about code or a cause has a status, or sits under Offen.
- Ticket keys appear only in the Out of Scope of a story or bug; an epic or initiative
  has none; other relations are Jira links. Out of Scope repeats nothing the parent
  already leaves out.
- No file lists, steps or test scripts outside Befund and Reproduktion.
- The word count, counted, is at most 500, or the report says why it is over and, over
  600, that the ticket is too big.
