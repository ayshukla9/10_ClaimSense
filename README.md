# ClaimSense

Know what your insurance is actually worth -- reconciling hospital bills
against plan rules, one line item at a time. A Django web app (Team 10).

## Setup (local, with the AI features)

Needs Python 3.11-3.13, about 4 GB of free disk for model weights and 8 GB of RAM. No GPU and no paid API key.

```bash
git clone https://github.com/ayshukla9/10_ClaimSense.git
cd 10_ClaimSense
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
# Optional, Linux: CPU-only torch is much smaller than the default CUDA build
#   pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt    # Django + torch, transformers, sentence-transformers (+ optional google-genai)

cp .env.example .env               # then set SECRET_KEY (GEMINI_API_KEY is optional)
python manage.py migrate
python manage.py seed_demo_data --accounts --password <choose-a-password>   # synthetic demo plans, bills and logins
echo "LOCAL_LLM_DEVICE=mps" >> .env       # Mac with Apple silicon: ~70x faster than CPU (use cuda on NVIDIA, or leave unset for CPU)
python manage.py build_plan_index --llm   # optional: download both models now instead of on the first click
python manage.py runserver         # uses settings/development.py by default
```

**Using the AI features** (log in as a demo patient, e.g. `ecarter1` with the password you chose, or as staff):

| Feature | Where | What it does |
| --- | --- | --- |
| Ask about my plan (A9, primary) | **Ask AI** in the nav bar, `/ask/` | Question → semantic search over plan documents → local LLM answer with citations |
| Explain with AI (A6 + A9) | Any bill → **Explain with AI** | Local LLM explains and flags each charge; each charge shows the closest plan rule |
| Appeal letter (A6, optional) | Explain page → **Draft appeal letter** | Google Gemini, only if `GEMINI_API_KEY` is set |

**Model download notes.** Nothing is committed: weights download from the Hugging Face Hub into
`~/.cache/huggingface` the first time they are needed (`Qwen/Qwen2.5-1.5B-Instruct` ≈ 3 GB,
`sentence-transformers/all-MiniLM-L6-v2` ≈ 90 MB). The retrieval index is saved under `.cache/rag/`
(git-ignored) and rebuilds itself when a knowledge file changes. Set `HF_TOKEN` in `.env` for faster downloads.
Without torch (`requirements-web.txt`, `LOCAL_LLM_ENABLED=0`, `RAG_EMBEDDINGS_ENABLED=0`) the pages still work:
keyword search shows the closest plan sections and line items get the rule checks.

**Tests and evaluation**

```bash
python manage.py test claims              # offline: models are mocked (seconds)
python manage.py evaluate_ai --variant both   # real models: the A9 evaluation tables in docs/a9/results/
```

Visit `http://127.0.0.1:8000/admin/` for the admin (see docs/notes/notes.txt
or ask a teammate for credentials) and `http://127.0.0.1:8000/bills/render/`
for the bill list.

## Settings

Split into `claimsense_project/settings/`:
- `base.py` -- everything shared; reads `SECRET_KEY` and other secrets
  from environment variables via `python-dotenv`, never hardcoded.
- `development.py` -- `DEBUG=True`, fixed localhost `ALLOWED_HOSTS`. Used
  by `manage.py` by default.
- `production.py` -- `DEBUG=False`, `ALLOWED_HOSTS` read from the
  `ALLOWED_HOSTS` environment variable. Used by `wsgi.py`/`asgi.py` by
  default.

Copy `.env.example` to `.env` and fill in real values -- `.env` itself is
gitignored and must never be committed.

## Project structure

```
ClaimSense/
├── README.md
├── requirements.txt          # full install, incl. torch for the local AI model
├── requirements-web.txt      # server install without torch (PythonAnywhere)
├── .env.example              # safe to commit; copy to .env locally
├── manage.py
├── docs/
│   ├── wireframes/v1/        # low-fi wireframes PDF
│   ├── branching_strategy/   # git workflow this team uses
│   ├── notes/notes.txt       # weekly progress notes
│   └── screenshots/          # view-output screenshots (P1-A2)
├── claimsense_project/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── claims/                   # core app: Patient, InsurancePlan,
    │                         # Provider, Bill, BillLineItem
    ├── models.py
    ├── admin.py
    ├── views.py               # 2 FBVs + 2 CBVs (P1-A2), home + detail
    ├── summaries.py           # shared aggregations (API, charts, reports)
    ├── views_api.py           # JSON API
    ├── views_vega.py          # Vega-Lite page + PNG endpoints
    ├── views_external.py      # HCPCS lookup (external API)
    ├── views_exports.py       # CSV / JSON exports + reports page
    ├── views_ai.py            # A6/A9: explain, ask-about-my-plan, appeal letter
    ├── ai/                    # A6/A9 AI code
    │   ├── retrieval.py       #   chunking, MiniLM embeddings, plan-filtered search
    │   ├── rag.py             #   question -> retrieval -> local LLM -> checked answer
    │   ├── local_llm.py       #   Qwen2.5-1.5B-Instruct via transformers (lazy, CPU)
    │   ├── guardrails.py      #   input cleaning, injection checks, output validation
    │   ├── prompts.py         #   zero-shot explainer + RAG prompts
    │   └── gemini_client.py   #   optional appeal letters (API)
    ├── knowledge/             # A9: plan-benefit documents searched by the RAG feature
    ├── management/commands/   # seed_demo_data, build_plan_index, evaluate_ai
    ├── urls.py
    └── templates/claims/
```

## Views (P1-A2)

Four view styles against the same `Bill` model, all rendering the same
shared template (`claims/bill_list.html`):

| URL | View | Style |
| --- | --- | --- |
| `/bills/manual/` | `bill_list_manual` | FBV -- HttpResponse (manual) |
| `/bills/render/` | `bill_list_render` | FBV -- `render()` shortcut |
| `/bills/cbv-base/` | `BillListBaseView` | CBV -- base `View` |
| `/bills/cbv-generic/` | `BillListView` | CBV -- generic `ListView` |

See `docs/notes/notes.txt` for what each one is for and when we'd reach
for one over another.


## P1-A3: Data-driven pages

ClaimSense now has a home page, a shared nav bar, and bill detail pages (`/bills/<pk>/`) linked through `Bill.get_absolute_url()`. Search (GET by provider, POST by patient email), a summary page with ORM aggregations, and a Matplotlib chart at `/charts/bills-per-provider.png` are live. Styling comes from `static/css/style.css`.

**API:** `GET /api/bills/` returns JSON (`JsonResponse`). Optional query params: `provider` (name contains), `plan` (plan name contains), `since` (`YYYY-MM-DD`). `/api/bills/plain/` returns the same data via `HttpResponse` (text/html) for the MIME comparison, and `/api/bills/cbv/` is the class-based version. These historical bill endpoints are now private; bill references are not public data.

**UI note:** custom CSS (navy/gold palette, serif headings, styled header, nav bar and tables) replaces the old inline `<style>` block.

## P1-A4: APIs, Vega-Lite charts, exports, deployment

**Chart API:** `/api/summary/providers/` (one row per provider) and `/api/summary/bills/` (one row per bill, oldest first). Both return a plain JSON list with bill counts and charged / covered / patient amounts. No patient data.

**Vega-Lite:** two charts at `/vega-lite/` -- a bar chart (total charged per provider) and a line chart (charges over time). Specs are in `static/vega-lite/` and use `data.url` with the API above. PNG versions: `/vega-lite/chart1.png` and `/vega-lite/chart2.png`. Screenshots are in `docs/screenshots/` (`p1-a4-*`). To try a spec in the Vega editor, change `data.url` to the full deployed URL.

**External API:** `/api/procedures/?q=imaging` searches HCPCS procedure codes (NLM Clinical Tables, no key) and returns them together with our own line items for that keyword (count, average, min/max, coverage %). `/procedures/` is the same thing as a page. Errors: no `q` -> 400, timeout -> 504, anything else from their side -> 502.

**Exports + reports:** `/reports/` has the totals, a per-provider table, an in/out of network table and the Download CSV / Download JSON buttons (`/exports/bills.csv`, `/exports/bills.json`). Filenames are timestamped, e.g. `bills_2026-10-05_19-32.csv`.

### Deploying on PythonAnywhere

```bash
git clone https://github.com/ayshukla9/10_ClaimSense.git
cd 10_ClaimSense
mkvirtualenv myenv-django --python=python3.12
pip install -r requirements-web.txt   # A6+: not requirements.txt -- torch does not fit the free disk
echo "SECRET_KEY=<your key>" > .env
echo "LOCAL_LLM_ENABLED=0" >> .env     # plus GEMINI_API_KEY=... for appeal letters
python manage.py collectstatic --noinput --settings=claimsense_project.settings.production
```

Then in the Web tab:
- Virtualenv: `/home/<username>/.virtualenvs/myenv-django`
- Static files: `/static/` -> `/home/<username>/10_ClaimSense/staticfiles`
- WSGI file: add the project folder to `sys.path` and set `DJANGO_SETTINGS_MODULE` to `claimsense_project.settings.production`

Run migrations for each deployment, including the A5 patient ownership migration. Preserve and back up the live database; do not replace it with the repository database. Production settings accept any `*.pythonanywhere.com` host unless `ALLOWED_HOSTS` is set in `.env`.


## P1-A5.1: authentication and public API

Custom signup/login/logout is served at `/accounts/`. Google OAuth uses django-allauth and private environment credentials. All authenticated accounts can use ordinary pages and protected APIs. Patient records are scoped to an explicit `Patient.user` link assigned by staff; unlinked accounts see empty results. Staff retain full record access and exclusive access to Manage. Navigation and all existing record routes are protected. The one public JSON API is `GET /api/public/plan-types/`, a database count of catalogue plans by type with no patient or bill information.

See [A5 setup and deployment](docs/a5/README.md), [290-second team demo](docs/a5/demo.md), and [evidence register](docs/a5/evidence.md). The live website is https://okc2.pythonanywhere.com/ and the public API is https://okc2.pythonanywhere.com/api/public/plan-types/. A5 was merged into `main` and deployed on October 12, 2026; the team completed real Google signup/login and captured production Vega-Lite and three API-consumer demonstrations. The server-generated `docs/a5/production_plan_types.txt` uses the absolute production API URL and is the external-editor submission source; `static/vega-lite/plan_types.txt` is the relative-URL hosted version. The video and submission packaging remain unfinished. Google publishing and a fresh availability check remain follow-ups; see the evidence register for precise verification limits.


## P1-A6: Hugging Face LLMs + Gemini

Bill pages now have **Explain with AI**: a local Hugging Face model (via `transformers`) explains and flags each
line item, and Google Gemini drafts an appeal letter for the flagged charges. See [README_AI.md](README_AI.md) for
the workflow, preprocessing and guardrails, [`llm-test/ai_prototype.ipynb`](llm-test/ai_prototype.ipynb) for the
15-model benchmark and prompting comparison, and the A6 section of `docs/notes/notes.txt` for the cost reflection.


## P1-A9: integrated AI (local models)

The primary AI feature is now **Ask about my plan** (`/ask/`): a retrieval-augmented question-answering flow that runs
entirely on public models on the Django server (sentence-transformers for search, Qwen2.5-1.5B-Instruct for the
answer). Each line item on the **Explain with AI** page also shows the plan rule that applies to it. Gemini stays an
optional, secondary feature. See [README_AI.md](README_AI.md) for the workflow, architecture, model rationale,
evaluation, failure analysis and the before/after improvement, and [docs/a9/demo.md](docs/a9/demo.md) for the demo script.
