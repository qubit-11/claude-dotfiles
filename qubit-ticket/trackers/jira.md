# Tracker: Jira

How the skill works with Jira through the Atlassian MCP tools. The profile's `ticket.md`
holds the values of one site: cloud ID, project, issue types, fields and link types.

## Calls

| Step | What | Call |
|---|---|---|
| 3, Revising 1 | search for duplicates, a home and neighbours | `searchJiraIssuesUsingJql` on the key terms and the module's open epics |
| Revising 1 | read a ticket with its comments and links | `getJiraIssue`, `listJiraIssueComments` |
| 7 | the user's account, the default assignee | `atlassianUserInfo` |
| 8 | create a ticket | `createJiraIssue`: the content format below, one `additional_fields` object (component by its live name, story points), `parent` when approved, the assignee |
| 8 | link tickets | `createIssueLink`: `Blocks` for an order, the profile's relates link type otherwise |
| Revising 6 | change a ticket | `editJiraIssue`, in the content format below |

## Content

- Through the API with `contentFormat: "markdown"`, `##` and `###` headings, tables,
  inline code, code blocks, numbered and bulleted lists, bold and italic arrive as
  formatting.
- `- [ ]` does not become a checkbox; it arrives as a bullet with the text "[ ]".
  Checkboxes exist only in ADF (Atlassian Document Format, `taskList`).
- Markdown has no mention: `@Name` arrives as plain text, and the tools accept only
  `markdown` and `adf` (no `html`). A description with a mention goes as ADF, on create
  and on edit alike: save the draft, run
  `python3 -I md2adf.py draft.md "@Name=<account ID>"` (this folder) and pass its
  output with `contentFormat: "adf"`. Read the ticket back once: the mention returns as
  the account, not as text.
- The account ID comes from `atlassianUserInfo` for the user and from
  `lookupJiraAccountId` for anyone else (through `discover` when it is not listed as a
  tool). Never invent an account ID.

## Paste rules (Markdown output only)

For text the user pastes into Jira: headings `#` and `##` only, with a blank line before
and after, so each `###` becomes a **bold** line; short lines; no inline backticks (write
identifiers in **bold** instead), no code blocks, no `<` or `>`, no `|` outside tables,
no `---`. A pasted `@Name` stays text: write the name plain, and the user types the
mention in Jira. Direct creation through the API needs none of this.
