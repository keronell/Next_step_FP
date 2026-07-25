# The Next Step

A career-discovery app: a questionnaire and an optional self-described profile are matched against a catalog of careers, and the chosen career opens a learning roadmap the user works through.

## Language

### Matching

**Career**:
One of the 16 occupations a user can be matched to and shown a roadmap for.
_Avoid_: job, role, field

**Assessment**:
One completed run of the questionnaire, producing a ranked set of career recommendations.
_Avoid_: quiz, test, submission

**Recommendation**:
One of the three careers an assessment matches a user to.
_Avoid_: result, suggestion, match

**Profile**:
What a user says about themselves — experience, projects and skills — offered between the assessment and the results. Optional, and English-only.
_Avoid_: CV, resume, bio

**Skill gap**:
A skill a career wants that the user's profile does not evidence.
_Avoid_: missing skill, weakness

### Roadmap

**Roadmap**:
The ordered learning path for one career, made of stages.

**Unlocked**:
A roadmap is unlocked for a user when they hold a recommendation for its career — only an unlocked roadmap can be opened.
_Avoid_: gated, entitled, permitted

**Stage**:
A named, ordered group of nodes within a roadmap — "Foundations", "Gives an Advantage". Nodes within a stage are in learning order; the job-ad stages are the exception, ranked by demand rather than sequenced. Serialized as `sections` on the wire, and referred to as a stage everywhere else.
_Avoid_: section, column, phase

**Node**:
One skill on a roadmap, shown as a card the user can open and mark complete.
_Avoid_: item, topic, card

**Status**:
Which of three states a node is in for this user: not started, skill gap, or completed. Completion is the only state the user sets directly.
_Avoid_: progress, state

**Market frame**:
The badge and frame drawn around a node whose skill was derived from real job ads, marking it as in demand or an advantage.
_Avoid_: demand badge, job-ad node

**Spine**:
The vertical gold thread running down the canvas, joining every stage in order.

**Rail**:
The dotted horizontal line above one row of nodes, from which each node hangs.
_Avoid_: trunk

**Drop**:
A short gold connector on the spine — from a stage header down to its rail, or from one stage to the next.
_Avoid_: stub, connector
