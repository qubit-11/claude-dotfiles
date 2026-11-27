# Cut

The cut turns the planner's request into tickets the team can take into a sprint without a
refinement about their shape. What stays for a refinement is business: a product question the
planner could not answer. The cut works on the planner's intent and the facts of steps 1 to 3;
it runs before any draft, because a draft of the wrong cut is wasted.

The aim is a cut without a known error, not the best cut: one maker cuts, a checker looks for
the errors below. When in doubt, cut smaller: a ticket that is too small costs little, one that
is too big goes back to a refinement (Google's guidance on small changes: one self-contained
change that does one thing; reviewers rarely complain that a change is too small).

## Kinds and levels

Every ticket has one kind; the profile maps the kinds to the issue types of its tracker.

| Kind | What it is | Value it must carry |
|---|---|---|
| Feature | new or changed behaviour | someone outside the team notices it: a user role of the profile, the support, the consumer of an interface |
| Bug | a defect in behaviour that was accepted | the defect is gone |
| Chore | needed work without behaviour change: refactoring, an upgrade, removing a deprecated API | none of its own; it states why it is needed. A chore that changes what someone notices is a feature |

(Pivotal Labs' feature, bug and chore.)

Every ticket, of any kind and level, is **one thing with an end**: one kind of change, and a
Ziel that says when it is done. A ticket that gathers fixes of one kind ("alle Rechtschreibfehler
in den Texten der Buchungsstrecke") is one thing; a ticket that gathers different kinds, or has
no end ("Diverse Fixes", "Frontend", "Bugs Q4"), is a bucket (Shape Up: a "grab bag" or "junk
drawer"). Whether small fixes of one kind go into one ticket or several is the planner's call.

The cut works one level down from the request:

| Request | Cut into | Text |
|---|---|---|
| an initiative | epics: each one capability of the product, together covering the initiative with no gap and no overlap | short (FORMAT.md) |
| an epic, a feature, a set of findings | stories, bugs and chores | FORMAT.md |
| one ticket | itself, or more when it fails a row below | FORMAT.md |

## Readiness (Definition of Ready)

The rows apply to stories, bugs and chores; a cut into epics has no readiness table,
the checker's findings stand for it. The result goes into the report, never into the
ticket, as one table with a line per ticket: the ticket, the rows not met, and one sentence of
reason for each. A ticket that meets every row says „alle erfüllt“. The request as the
planner gave it is the first line when the cut differs from it.

| Row | Applies to | Met when |
|---|---|---|
| Vertical | feature | The ticket alone gives the noticed behaviour, and someone can show it in one sentence („X öffnen, Y tun, Z sehen“). A ticket for one layer (frontend, backend, database) or one work step (design, build, test) is not vertical, unless that layer is itself the surface the person uses, such as a server rule a client sees as a rejected request. |
| Independent | all | It can be built, tested and shipped without another open ticket, and it changes no place that another ticket of the cut changes at the same time. Waiting for an earlier slice of the same cut meets this row. A dependency on another team, a partner or an outside date is named. |
| Negotiable | all | It holds no implementation plan (FORMAT.md, Rules, No implementation plan). |
| Valuable | all | Its Ziel carries the value of its kind (table above). |
| Estimable | all | No product question is open: a question whose answer changes what is built or what the Akzeptanzkriterien say. An unknown that only building or trying can answer makes it not estimable too. |
| Small | all | One thing with an end: two results that could be checked apart are two tickets. The size signals of step 2 agree: one variant (one platform, market or user role, unless the variants share every step), few servers or packages. A limit of the team (points, sprint length) applies when the profile names one. |
| Testable | all | Each Akzeptanzkriterium can be checked by someone who was not in the session (FORMAT.md, Rules, Akzeptanzkriterien); for a chore, that behaviour stays as it was. |

INVEST is Bill Wake's checklist; Vertical is listed apart, because INVEST only implies it through
Valuable. The size signals stay in the report: the ticket names no package or server.

## Questions

Sort every open question of the session into one of two kinds:

- **Produkt:** the answer changes what is built, for whom, or an Akzeptanzkriterium (which
  channel, which variants, which limit, whether a case is in scope). The planner answers it in
  the first round of questions (SKILL.md, step 5), each with the recommended answer and why.
- **Umsetzung:** the implementer answers it while building, and the answer changes no
  criterion. It goes to Offen.

An unknown that no one can answer without trying (does a platform behave like the others) is a
spike: a clarification ticket of its own, first in the cut. A spike is checked on
Independent, Small and Estimable only; its Ziel is the decision. The tickets that wait for its
decision are named in the report and cut once it is made, not drafted now.

## Code

The cut needs a short look at the code, in step 2, for two facts and no more: where each
feature slice's behaviour starts (a page, an endpoint), so its one-sentence demo is possible;
and which places two slices would both change, so they get an order or become one. Shape Up:
"you need to walk the territory before you can draw the map". The look stays in the report.

## Splitting

When Vertical, Small or Estimable is not met, or a ticket is a bucket, propose a cut. Name the
pattern of each split:

| Pattern | Split by | First slice |
|---|---|---|
| Spike | an unknown that blocks the scope | the clarification ticket, whose Ziel is the decision |
| Paths | paths through the flow (main path, error paths, special cases) | the main path |
| Interfaces | platforms, devices, channels, browsers, embedding hosts | the one with the verified case, or the one most users have |
| Data | data variants (markets, types, formats) | the simplest variant |
| Rules | business rules on the same flow | the core rule; stricter rules later |
| User roles | outcomes for different people (patients, the practice, the support) | the outcome the deadline or the problem is about |
| Kind | a bucket's items by kind (feature, bug, chore) and topic | each item with its own end |

The first five are SPIDR (Mike Cohn); Richard Lawrence's story-splitting patterns name similar
moves. A split by layer, component or work step is no pattern: it makes horizontal tickets.

The shape of the cut:

- The first slice is the thinnest path someone outside the team can use end to end; later
  slices widen it. Each slice passes the readiness rows on its own.
- Prefer the split that shows a slice the planner could defer or drop, and slices of about the
  same size (Lawrence's evaluation step); five slices with nearly all the work in one are no
  cut (Cohn).
- A blocks link joins two slices only where the later one cannot ship without the earlier.
  When two cuts are equally small, take the one with fewer links.
- A planner's request for one layer ("ein Backend-Ticket, das Frontend mache ich danach") gets
  the vertical alternative in the report: the outcome both tickets serve, as one ticket or a cut
  by another pattern.
- Too small: the change is smaller than its ticket would be. Suggest no ticket (a commit type
  that needs none), or one ticket for several such fixes of one kind.

The planner approves the cut, picks another, or keeps the request as it was. A ticket kept
against a row that is not met is still drafted; the report names the row.

## Wrong cuts

The checker (SKILL.md, step 4) looks for these errors at the level of the cut and reports each
one it finds; a cut with none is fine as it is.

| Error | Level | Sign |
|---|---|---|
| Gap | all | something the request asks for is in no ticket and not under Out of Scope |
| Overlap | all | one behaviour, or one place in the code, is in two tickets |
| Layer | all | a ticket or an epic covers one layer, one team or one work step |
| Bucket | all | a ticket or an epic gathers different kinds of change, or has no end |
| Cycle | all | two tickets wait for each other |
| Uneven | all | nearly all the work sits in one ticket of the cut |
| No demo | feature | its behaviour cannot be shown in one sentence without another open ticket |
| Too big | story, bug, chore | more than one result that could be checked apart |
| Disguised feature | chore | it changes what someone notices |
| Solution | all | the ticket prescribes the implementation |

Mike Cohn's story-splitting mistakes, Thoughtworks on horizontal slicing and epics, and Shape
Up's "grab bag" name most of these.
