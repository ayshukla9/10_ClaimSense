# ClaimSense AI (A6)

ClaimSense now has two AI features on every bill page. Both are reached from **Bill detail → Explain with AI**.

| Feature | Where it runs | Code |
| --- | --- | --- |
| **Line-item explainer**: every charge is rewritten in plain English, sorted into a category and flagged `ok` / `review` | Local Hugging Face model on the Django server (`transformers`) | `claims/ai/local_llm.py` |
| **Appeal letter**: drafts a letter asking the insurer to review the flagged charges | Google Gemini API (`gemini-3.5-flash-lite`, free tier) | `claims/ai/gemini_client.py` |

The two form a **hybrid pipeline**. The free local model reads every line item. Only the charges it flags (and that the
patient ticks) go to the paid-tier-capable API, which writes the one piece of long-form text.

```
Bill + line items ──► preprocessing ──► local model (JSON per item) ──► output validation ──► rule checks override
   (Django ORM)       guardrails.py       local_llm.py                    guardrails.py          guardrails.rule_checks
                                                                                                        │
                                                       patient ticks items + optional note ◄────────────┘
                                                                     │  injection screen, PII removed
                                                                     ▼
                                                    Gemini API ──► letter cleaned ──► shown with "what was sent"
```

Model choice and prompting style come from the benchmark in [`llm-test/ai_prototype.ipynb`](llm-test/ai_prototype.ipynb).
The reflection on size, cost and scaling is in [`docs/notes/notes.txt`](docs/notes/notes.txt) (A6 section).

## Data input

* **Structured data already in the database.** Bills and line items are entered by staff through
  *Manage* / Django admin, or by the seed commands. Each `BillLineItem` gives description, procedure code,
  charged / covered / patient amounts, and through its bill the provider's network status. Patients never type
  the data the local model reads.
* **One free-text field:** an optional note (max 600 characters) on the appeal form, e.g. "the ER was the
  closest hospital". This is the only user-typed text that reaches a model.
* **Which charges to appeal:** checkboxes, pre-ticked for items flagged `review`.
* Both pages only accept bills from `visible_bills(request.user)`, the same ownership rule as every other page.
  Another patient's bill returns 404 and anonymous users are redirected to login.

## Preprocessing

`claims/ai/guardrails.py`:

1. **`clean_text`** normalises Unicode (NFKC), strips control characters and HTML tags, collapses whitespace and caps
   each field at 200 characters.
2. **`describe_line_item`** turns a line item into a fixed six-line fact sheet. **All arithmetic is done in
   Python** (the coverage percentage and formatted dollar amounts) because small models are unreliable at maths:

   ```
   Description: MRI imaging
   Code: IMG-101
   Provider network: In Network
   Charged: $1,200.00
   Insurance covers: $700.00 (58%)
   Patient owes: $500.00
   ```
3. **Prompt** (`claims/ai/prompts.py`): a **zero-shot** system prompt with the exact JSON schema, the allowed
   values and the flag rules, followed by the fact sheet. In the notebook's prompting comparison, zero-shot was
   best for our model (0.94 vs 0.89 with three examples). It got every ok/review flag right, resisted the
   prompt-injection test that the few-shot prompt fell for, and is the fastest because the prompt is shortest.
   The notebook imports this same file, so the benchmark tested exactly what ships.
4. **For Gemini**, `build_prompt` sends plan, provider, bill reference, date and the flagged fact sheets. **Patient
   name, email and netid are never sent.** The letter uses `[Your name]` / `[Member ID]` placeholders. The page
   shows the patient exactly what was sent.

## Safety guardrails

**Malicious input**

| Risk | Guardrail |
| --- | --- |
| Prompt injection in the note ("ignore previous instructions…", fake `<system>` tags, "you are now…") | `check_note` rejects it with HTTP 400 *before* any model runs. It checks the raw text too, so tags cannot hide by being stripped |
| Injection hidden in bill data (a line-item description) | The system prompt says to treat line items as data. Fields are length-capped. The notebook's test input #7 checks that models resist exactly this |
| Leaking patient identity to a third party | No personal identifiers in the Gemini prompt (covered by a test) |
| Reading other patients' bills | Same `visible_bills` scoping as the rest of the site. Both routes sit behind `private_view` |
| Cost or abuse of the external API | Max 10 letters per user per hour (`GEMINI_HOURLY_LIMIT`, HTTP 429). Max 10 line items per run. The local model only runs on POST, never on a plain GET (crawlers and link previews cannot trigger it) |
| CSRF | Both forms are POST with `{% csrf_token %}` |

**Broken output**

| Risk | Guardrail |
| --- | --- |
| Model writes prose, partial JSON or extra keys | `parse_explanation` extracts the first JSON object and validates keys and values. Near-miss categories are snapped to the allowed list (`"imaging"` → `Imaging`). Anything unusable becomes a safe fallback ("could not produce a reliable explanation", flag `review`) instead of an error |
| Model says `ok` when a charge is clearly a problem | `rule_checks` (out of network, patient pays ≥ 50%, amounts don't add up) always win. A model "ok" can never hide a real issue |
| Runaway generation | Greedy decoding that stops at the first `}` (end of the JSON object), `max_new_tokens=100`, at most 10 items per request |
| Local model unavailable (torch missing, `LOCAL_LLM_ENABLED=0`) | The page says why, still lists every line item with the rule-check flags (out of network, patient pays ≥ 50%, amounts don't add up), and appeal letters still work. No 500 |
| Gemini down, quota exceeded, safety-blocked or empty reply | Caught: 503 / 502 page with a retry message, logged server-side. Empty or blocked replies are detected |
| Markdown or odd characters in the letter | `clean_letter` strips markdown and control characters and caps the length. The template auto-escapes everything (no `|safe`) |
| Repeated cost | Explanations are cached per line item + model + content hash for 24 h, so reopening a bill is instant |

## Local LLM integration

* Model: **`Qwen/Qwen2.5-1.5B-Instruct`** (set by `LOCAL_LLM_MODEL`). See the notebook for why.
* `transformers.pipeline("text-generation", …)` is built lazily on first use and kept for the life of the process,
  behind a lock. **The weights download automatically from the Hugging Face Hub the first time you click "Explain
  this bill"** (≈ 3 GB into `~/.cache/huggingface`). Nothing needs downloading by hand, and the weights are git-ignored
  (`*.safetensors`, `*.bin`, `*.pt`, …).
* Runs on CPU. No GPU is needed.

## External API integration

* Google Gemini through the official `google-genai` SDK. Get a free key at <https://aistudio.google.com/apikey>.
* Default model `gemini-3.5-flash-lite` (free tier; paid: $0.30 / $2.50 per million input / output tokens). It can be
  changed with `GEMINI_MODEL`.

## Running it locally

```bash
python -m venv .venv && .venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt                         # includes torch, transformers, google-genai
cp .env.example .env                                    # set SECRET_KEY and GEMINI_API_KEY
python manage.py migrate
python manage.py runserver
```

Log in as a staff user (or a user linked to a patient), open any bill and click **Explain with AI**. The first click
downloads the model. After that, each line item takes a few seconds on a laptop CPU.

Tests (the model and API are mocked, so they run offline in seconds): `python manage.py test claims`.

**Deployment note:** PythonAnywhere's free tier cannot install torch (disk quota). On the server, install
`requirements-web.txt` instead of `requirements.txt` (same packages minus torch, transformers and the notebook tools)
and set `LOCAL_LLM_ENABLED=0`. Line items then show the automatic rule checks instead of AI explanations, and Gemini
appeal letters keep working with `GEMINI_API_KEY` set. Even if the variable is forgotten, a missing torch triggers the
same fallback.
