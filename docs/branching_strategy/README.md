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

For P1-A2, the work was done on `feature/p1-a2-fullstack` (settings split,
env vars, four views, templates) and merged back into `main` once the four
view URLs were verified working and the empty/non-empty template states
were confirmed.
