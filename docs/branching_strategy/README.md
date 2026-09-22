# Branching Strategy

We use a simple trunk-based workflow:

```
main  ----o----o----o----o----o----o----o------->
           \        /      \          /
            \      /        \        /
   feature/*  o---o    feature/*  o--o
```

- **`main`** is always deployable. Nothing is committed to it directly once a
  feature branch exists for the work.
- **`feature/<short-description>`** branches hold one piece of work each
  (e.g. `feature/p1-a2-views`, `feature/p1-a2-settings-split`). Branch off
  `main`, commit frequently with meaningful messages, then open a PR back
  into `main` and merge once it's reviewed and working.
- We delete a feature branch after it's merged, to keep the branch list
  meaningful.
- Commit message style: short imperative summary line (e.g. "Add split
  settings pattern for dev/prod", "Wire up four Bill views + templates"),
  not "fix", "update", "wip".

## This assignment's branches

For P1-A2, work was split across the team by section, with each person branching off `main` and merging back via their own PR:

| Branch | Author | PR | Covers |
| --- | --- | --- | --- |
| `feature/p1-a2-templates` | omkarchougule19 | #1 | Section 3: base template + list template |
| `feature/p1-a2-settings` | aagamshah15 | #2 | Section 1B: split settings + env-based secrets |
| `feature/p1-a2-docs` | ayshukla9 | #3 | README, docs/ (wireframes, notes, branching strategy), screenshots |
| `feature/p1-a2-views` | Pseudopooja | #4 | Section 2: four view styles + URLs |

All four branches were merged into `main` once their piece was verified working.
