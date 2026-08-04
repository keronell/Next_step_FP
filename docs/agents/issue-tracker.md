# Issue tracker: Jira

Issues and PRDs for this repo live in the Jira project **DEV** ("The Next Step") on
`s-team-at2qc4hd.atlassian.net`. All operations go through the Atlassian Rovo MCP
tools — there is no CLI for this tracker.

## Constants

- **cloudId**: `7f49f85a-0a8c-430e-a5c3-4bb248e43ec3`
- **projectKey**: `DEV`
- **Issue types**: `Epic` (hierarchy level 1), `Task` (0), `Subtask` (-1). There is no
  Bug or Story type — file bugs as `Task`.
- Ticket keys look like `DEV-66`; branches are named `feature/dev-66-<slug>`.

## Conventions

- **Create an issue**: `createJiraIssue` with `projectKey: "DEV"` and an issue type from
  the list above.
- **Read an issue**: `getJiraIssue` on the `DEV-nn` key, including its comments.
- **List / search issues**: `searchJiraIssuesUsingJql`, e.g.
  `project = DEV AND labels = "needs-triage" AND statusCategory != Done ORDER BY created DESC`.
- **Comment on an issue**: `addCommentToJiraIssue`.
- **Apply / remove labels**: `editJiraIssue` with `fields.labels`. Jira **replaces** the
  whole array rather than merging, so read the issue's current labels first and send the
  merged set. Jira labels cannot contain spaces.
- **Close**: `transitionJiraIssue`, using a transition id from
  `getTransitionsForJiraIssue`. Never set `status` directly — it is not a writable field.

## Pull requests as a triage surface

**PRs as a request surface: no.**

Pull requests live on GitHub (`keronell/Next_step_FP`) and are not part of the triage
queue. Code review runs through PRs and `/code-review`; only Jira issues are triaged.

## When a skill says "publish to the issue tracker"

Create a DEV issue with `createJiraIssue`.

## When a skill says "fetch the relevant ticket"

`getJiraIssue` on the `DEV-nn` key, with its comments.

## Wayfinding operations

Used by `/wayfinder`. The **map** is an Epic with **child** Tasks as tickets.

- **Map**: a single `Epic` in DEV labelled `wayfinder-map`, holding the Notes /
  Decisions-so-far / Fog body.
- **Child ticket**: a `Task` with `parent` set to the map Epic. Labels:
  `wayfinder-research` / `wayfinder-prototype` / `wayfinder-grilling` / `wayfinder-task`.
  Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: `createIssueLink` with link type `Blocks` (`is blocked by` / `blocks`),
  where **`inwardIssue` is the blocker and `outwardIssue` is the blocked ticket**. A
  ticket is unblocked when every blocker is in `statusCategory = Done`.
- **Frontier query**:
  `project = DEV AND parent = <EPIC-KEY> AND statusCategory != Done AND assignee IS EMPTY ORDER BY rank`,
  then `getJiraIssue` on each candidate and drop any whose `issuelinks` holds an
  `is blocked by` link to an issue not in statusCategory Done — JQL can't filter on link
  targets' status. First in rank order wins.
- **Claim**: `editJiraIssue` setting `assignee` to yourself (`atlassianUserInfo` for your
  accountId) — the session's first write.
- **Resolve**: `addCommentToJiraIssue` with the answer, `transitionJiraIssue` to Done,
  then append a context pointer to the map Epic's Decisions-so-far.
