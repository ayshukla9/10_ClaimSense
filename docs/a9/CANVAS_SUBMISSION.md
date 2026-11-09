# P1-A9 Canvas submission – Team 10 (ClaimSense)

**GitHub repository:** https://github.com/ayshukla9/10_ClaimSense
(A9 work: branch `feature/p1-a9-integration`, merged into `main` via pull request)

**Team:** Ayush Shukla (ashukla9), Omkar Chougule (okc2), Pooja Sahu (poojads2), Aagam Shah (aps22)

## AI feature summary

ClaimSense helps patients check medical bills against their insurance plan. Our primary A9 feature, **Ask about my
plan** (`/ask/`, nav bar → Ask AI), is a retrieval-augmented question-answering flow that runs entirely on public
models inside the Django app: the question is embedded with `sentence-transformers/all-MiniLM-L6-v2`, matched
against chunked plan-benefit documents filtered to the member's plan type (plus their own deductible / coinsurance /
out-of-pocket numbers from the database), and the top 3 sections are passed to a local
`Qwen/Qwen2.5-1.5B-Instruct`, which answers in plain English with citations. Answers are checked for invalid
citations and numbers not found in the sources; off-topic questions never reach the LLM. The A6 **Explain with AI**
page (local Qwen line-item explanations and flags) now also shows the matching plan rule for every charge. Gemini
remains only as an optional appeal-letter feature. Model choice comes from our A6 benchmark (Qwen2.5-1.5B: 0.94
score, 100% correct flags, ~14 s/item on CPU vs 58–70 s for 3–4B models). Our evaluation
(`python manage.py evaluate_ai --variant both`) covers 11 realistic inputs: 8/11 correct and useful by our reading,
answers in 1.3–3.3 s on the laptop's Apple GPU. Improvements, each measured before/after: plan-type filter +
similarity threshold (retrieval check 5/9 → 9/9, wrong-plan chunks 4 → 0), an injection filter that no longer
blocks ordinary questions (3/4 → 0/4 wrongly blocked), and running on the GPU (196 s → 2.8 s per answer). A stronger
citation prompt was also tried, made answers worse, and was rolled back.

Documentation: `README.md` (setup, models, how to run), `README_AI.md` (workflow, architecture, model rationale,
evaluation, failure analysis, improvements), `docs/a9/demo.md` (demo script).

## 1v1 demo

Scheduled: **‹day, date, time›** – office hours slot booked at the Box sign-up sheet. *(Team TODO: fill in.)*
