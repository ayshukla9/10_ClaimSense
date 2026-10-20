# ClaimSense AI features (P1-A6)

ClaimSense has two AI features, plus a hybrid of the two:

| Feature | Where | Model | Runs on |
|---|---|---|---|
| **Bill parser**: pasted bill text → structured line items | `/ai/parse/` ("AI Parser" in the nav) | `Qwen/Qwen3-0.6B`, one-shot prompt (Hugging Face, chosen in `llm-test/ai_prototype.ipynb`) | Our Django server, via `transformers` |
| **Bill explainer**: plain-English explanation of a saved bill | "Explain this bill (AI)" button on every bill page, `/bills/<id>/explain/` | gpt-oss-120b (`openai/gpt-oss-120b`, OpenAI's open-weight 117B model) | Groq's API (free tier) |
| **Hybrid**: parse with the local model, then explain the parsed charges | Tick "Also explain it in plain English" on `/ai/parse/` | Both | Both |

The local model is cheap and private but small, so it only does the narrow, checkable job (extract numbers into a
fixed schema). The external model is larger and better at writing, so it only does the open-ended job (explanation),
and it only ever sees bill facts that our code has already validated.

## Workflow

```
 user pastes bill text ──► clean + limit ──► local Qwen3 0.6B ─► extract + validate JSON ──► line-item table
                              (guardrails)      (one-shot prompt)     (guardrails)                │
                                                                                                  ▼ (optional)
 saved bill (owner only) ──► facts without patient identity ──────────────────► gpt-oss-120b on Groq ──► cleaned text
```

### Data input

* **Bill parser:** a logged-in user pastes bill text into a Django form (`BillTextForm`, a `<textarea>` capped at
  4,000 characters, CSRF-protected POST). Nothing is saved to the database; the result is shown for the user to check.
* **Bill explainer:** uses a bill already stored in ClaimSense (patient, provider, plan and line items entered by
  staff). It only works on bills the user may see (`visible_bills()`), so another patient's bill returns 404 and is
  never sent anywhere.

### Preprocessing

`claims/ai/guardrails.py → clean_bill_text()` runs before anything reaches a model:

1. Unicode NFKC normalisation (turns look-alike characters and full-width digits into plain ones).
2. Removes control characters except newlines and tabs (they can hide text or confuse tokenizers).
3. Collapses runs of spaces, trims each line, and squeezes blank lines.
4. Rejects empty text, text over 4,000 characters, and text with no digits (a bill always has amounts).
5. Wraps the bill in `<<< >>>` delimiters inside the prompt and adds one worked example first (one-shot). In the
   notebook one example lifted Qwen3-0.6B from 0.78 to 0.96 and got every amount right on all 9 test bills; more
   examples only made prompts longer.

For the explainer, `claims/ai/explainer.py → describe_bill()` builds a short fact sheet: provider and network status,
plan type, deductible, coinsurance, out-of-pocket max, and each line item's charged / covered / patient amounts.
**Patient name, netid, email and the bill reference number are never included.**

### Safety guardrails

| Risk | What we do |
|---|---|
| Prompt injection inside the bill ("ignore previous instructions…") | System prompt says the bill is data, not instructions; the bill is fenced with delimiters; common injection phrases are detected and the page shows a warning; the notebook's injection test bill showed why the second layer matters (1 of 31 runs, a small model with many examples, replied only "APPROVED"). The output is still forced through the schema below, so an "APPROVED"-style reply is rejected. |
| Broken or chatty model output | `extract_json_object()` strips code fences/chatter and parses the outermost `{…}`; anything else is an error message, not a crash. |
| Wrong or absurd values | `validate_parsed_bill()` requires 1–40 line items, a description for each, amounts that are numbers between $0 and $1,000,000 (rounded to cents), text fields cut to 200 characters, and an ISO date (an impossible date is dropped rather than shown). |
| Unsafe HTML or markdown in output | All model text is rendered through Django's autoescaping (`{{ }}`/`linebreaks`), so `<script>` shows as text; markdown symbols are stripped from explanations, and replies are capped at 3,000 characters. |
| Abuse / runaway cost | Login required (all `/ai/` and `/bills/` routes are private), per-user limit of 20 AI calls per 10 minutes (`AI_RATE_LIMIT`), explanations only run on POST (link prefetchers and crawlers can't spend quota), explanation calls time out after 30 s. |
| Privacy | Only the owner (or staff) can explain a bill; no identifying fields are sent to Groq; the parser does not store pasted text. |
| Service failures | Missing `torch`/`transformers`, a model that can't download, a missing API key, API timeouts, HTTP 429 rate limits and malformed replies each show a clear message; the rest of the site keeps working. |
| Over-trust | Every result says AI output can be wrong; explanations are labelled as generated by gpt-oss-120b and "not medical or financial advice". |

## Running it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # includes torch, transformers, accelerate, python-dotenv
```

Create `.env` in the project root (it is git-ignored):

```
SECRET_KEY=any-long-random-string
GROQ_API_KEY=your-key-from-console.groq.com   # free; needed for explanations only
```

```bash
python manage.py migrate
python manage.py runserver
```

Log in, open **AI Parser**, paste a bill and click **Parse bill**. The first request downloads the model weights
(about 1.5 GB for Qwen3-0.6B) into `~/.cache/huggingface` through `transformers`, then loads them once per server
process; later requests take about 1 s on a laptop GPU or about 3-4 s on CPU only. To pre-download, run the first cell of
`llm-test/ai_prototype.ipynb`.

Optional settings (environment variables): `LOCAL_LLM_MODEL` (any chat model from the notebook, e.g.
`Qwen/Qwen3-4B-Instruct-2507`, the most accurate in our tests but 4x slower and GPU-only in practice), `EXPLAIN_MODEL`
(any Groq chat model, default `openai/gpt-oss-120b`), `AI_RATE_LIMIT`.

## Production note

Our PythonAnywhere free accounts have 512 MB of disk, and `torch` alone is larger than that, so production servers
install `requirements-production.txt` (everything except the local-model stack). There, the AI Parser page says the
local model isn't installed, and the explainer still works if the server can reach `api.groq.com` (free
PythonAnywhere accounts can only reach allow-listed sites). `notes.txt` discusses what it would take to host the
local model in production.

## Files

| Path | What it is |
|---|---|
| `llm-test/ai_prototype.ipynb` | Part 1: model research, 15-model matrix test, prompting strategies, evaluation |
| `llm-test/results/*.csv` | Raw outputs and summary tables produced by the notebook |
| `claims/ai/guardrails.py` | Input cleaning, injection flags, JSON extraction and validation |
| `claims/ai/local_parser.py` | Local Hugging Face model: lazy loading, prompt, generation |
| `claims/ai/explainer.py` | Groq API client and privacy-safe bill fact sheets |
| `claims/views_ai.py` | The two views and the per-user rate limit |
| `claims/tests.py` (`TextIntelligenceTests`) | Tests with the models mocked: guardrails, escaping, privacy, errors, rate limit |
| `docs/notes/notes.txt` | Part 3: production reflection |
