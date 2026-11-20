# Cut

The cut turns the planner's request into tickets the team can take into a sprint without a
refinement about their shape. What stays for a refinement is business: a product question the
planner could not answer. The cut works on the planner's intent and the facts of steps 1 to 3;
it runs before any draft, because a draft of the wrong cut is wasted.

## Readiness (Definition of Ready)

Every ticket of the cut is checked against these rows. The result goes into the report,
never into the ticket, as one table with a line per ticket: the ticket, the rows not met,
and one sentence of reason for each. A ticket that meets every row says „alle erfüllt“.
The request as the planner gave it is the first line when the cut differs from it.

| Row | Met when |
|---|---|
| Vertical | The ticket alone gives a behaviour someone outside the team can see or use: a user role of the profile, the support, or the consumer of an interface (a partner calling an API). A ticket for one layer (frontend, backend, database) or one work step (design, build, test) is not vertical, unless that layer is itself the surface the person uses, such as a server rule a client sees as a rejected request. |
| Independent | It can be built, tested and shipped without another open ticket. Waiting for an earlier slice of the same cut meets this row. A dependency on another team, a partner or an outside date is named. |
| Negotiable | It holds no implementation plan (FORMAT.md, Rules, No implementation plan). |
| Valuable | Its Ziel names who gains what. |
| Estimable | No product question is open: a question whose answer changes what is built or what the Akzeptanzkriterien say. An unknown that only building or trying can answer makes it not estimable too. |
| Small | One outcome: two results that could be checked apart are two tickets. The size signals of step 2 agree: one variant (one platform, market or user role, unless the variants share every step), few servers or packages. A limit of the team (points, sprint length) comes from the profile. |
| Testable | Each Akzeptanzkriterium can be checked by someone who was not in the session (FORMAT.md, Rules, Akzeptanzkriterien). |

INVEST is Bill Wake's checklist (2003); Vertical is listed apart, because INVEST only implies it
through Valuable. The size signals stay in the report: the ticket names no package or server.

## Questions

Sort every open question of the session into one of two kinds:

- **Produkt:** the answer changes what is built, for whom, or an Akzeptanzkriterium (which
  channel, which variants, which limit, whether a case is in scope). The planner answers it in
  the first round of questions (SKILL.md, step 6), each with the recommended answer and why.
- **Umsetzung:** the implementer answers it while building, and the answer changes no
  criterion. It goes to Offen.

An unknown that no one can answer without trying (does a platform behave like the others) is a
spike: a clarification ticket of its own, first in the cut. A spike is checked on
Independent, Small and Estimable only; its Ziel is the decision, so Vertical, Valuable and
Testable do not apply. The tickets that wait for its decision are named in the report and
cut once it is made, not drafted now.

## Splitting

When Vertical, Small or Estimable is not met, propose a cut. Name the pattern of each split:

| Pattern | Split by | First slice |
|---|---|---|
| Spike | an unknown that blocks the scope | the clarification ticket, whose Ziel is the decision |
| Paths | paths through the flow (main path, error paths, special cases) | the main path |
| Interfaces | platforms, devices, channels, browsers, embedding hosts | the one with the verified case, or the one most users have |
| Data | data variants (markets, types, formats) | the simplest variant |
| Rules | business rules on the same flow | the core rule; stricter rules later |
| User roles | outcomes for different people (patients, the practice, the support) | the outcome the deadline or the problem is about |

The first five are SPIDR (Mike Cohn); Richard Lawrence's story-splitting patterns name similar
moves; User roles is a common addition. A split by layer,
component or work step is no pattern: it makes horizontal tickets.

The shape of the cut:

- The first slice is the thinnest path that someone outside the team can use end to end; later
  slices widen it. Each slice passes the readiness rows on its own.
- A `Blocks` link joins two slices only where the later one cannot ship without the earlier.
  When two cuts are equally small, take the one with fewer links: Small and Independent pull
  against each other.
- A planner's request for one layer ("ein Backend-Ticket, das Frontend mache ich danach") gets
  the vertical alternative in the report: the outcome both tickets serve, as one ticket or a cut
  by another pattern.
- Too small: the change is smaller than its ticket would be. Suggest no ticket (a commit type
  that needs none), or one ticket for several such fixes.
- An epic or initiative is not cut into stories here; its own text stays short (FORMAT.md).

The planner approves the cut, picks another, or keeps the request as it was. A ticket kept
against a row that is not met is still drafted; the report names the row.
