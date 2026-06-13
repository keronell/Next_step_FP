# Question Revision Proposal (Patch-Ready)

## Scope
This proposal is generated from `data/reports/question_bank_beginner_quality_flags.csv` and focuses on high-impact beginner-facing issues: low discriminativeness, weak axis alignment, and near-duplicate template tails.

## Recommended bulk action
- Remove boilerplate suffixes globally:
  - `This describes me well.`
  - `This is true for me.`
  - `I can relate to this.`
- Remove scenario qualifiers unless required for construct:
  - `(at work)`, `(in a team)`, `(when learning)`, `(under time pressure)`, `(when I'm tired)`
- Keep one canonical wording per intent to reduce duplicates.

## Priority rows to revise/remove now

| ID | Current issue summary | Action | Replacement question |
|---|---|---|---|
| 418 | Too long + low discriminativeness + boilerplate | revise | I enjoy presenting solutions clearly to a small group. |
| 450 | Too long + beginner exclusion + template duplication | revise | I like discussing ideas with others to improve them. |
| 558 | Too long + low discriminativeness | revise | I prefer solving problems together rather than alone. |
| 64 | Generic wording + team-only scenario | revise | I like explaining difficult ideas in simple words. |
| 81 | Generic wording + learning-only scenario | revise | I enjoy improving the visual quality of my work. |
| 457 | Team-only scenario + duplicate tail | revise | I enjoy helping a group reach a shared decision. |
| 519 | Learning-only scenario + duplicate tail | revise | I enjoy presenting my ideas to others clearly. |
| 412 | Very long + weak alignment + boilerplate | revise | I enjoy breaking complex problems into smaller steps. |
| 5 | Hedging + duplicate tail + generic signal | revise | I enjoy turning complex ideas into simple examples. |
| 39 | Duplicate tail + weak field signal | revise | I enjoy creating new visual ways to explain information. |

## Suggested new field-discriminative items (additions)
These are beginner-friendly and intentionally more field-distinguishing.

1. I enjoy finding patterns in data tables and explaining what they mean.
2. I enjoy building interfaces that make apps easy to use.
3. I enjoy designing how services and databases work behind an app.
4. I enjoy testing software to catch bugs before users see them.
5. I enjoy automating deployments and keeping systems stable.
6. I enjoy writing clear technical guides for other people.
7. I enjoy planning product priorities based on user needs and impact.
8. I enjoy protecting systems by identifying security risks early.

## Assumption
Direct bulk edits to `data/data/question_bank.csv` are intentionally deferred to avoid risky dataset-wide changes in one pass. This file is patch-ready and can be applied in controlled batches.
