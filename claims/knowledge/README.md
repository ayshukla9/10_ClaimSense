# ClaimSense knowledge base (A9 retrieval)

These Markdown files are the documents the "Ask about my plan" feature searches
(`claims/ai/retrieval.py`). They are written by the team for the synthetic demo plans.
They are simplified, are not legal advice, and do not describe any real insurer.

File format:

```
# Document title
scope: general | PPO | HMO | EPO | OTHER

## Section heading
Section text...
```

* `scope: general` documents are searched for every user.
* Plan-type documents (`PPO`, `HMO`, `EPO`, `OTHER`) are searched only for members of a plan
  of that type (unless `RAG_FILTER_BY_PLAN=0`, the A9 "before" configuration).
* Each `##` section becomes one chunk. Long sections are split into windows of
  `RAG_CHUNK_WORDS` words with a small overlap.
* The member's own plan numbers (deductible, coinsurance, out-of-pocket maximum) are **not**
  in these files: they are generated from the `InsurancePlan` row at query time, so they can
  never go stale.

This README is skipped by the loader. After editing a document, the index rebuilds itself
automatically (the cache key includes a hash of every file).
