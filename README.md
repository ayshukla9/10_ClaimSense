# ClaimSense

Know what your insurance is actually worth -- reconciling hospital bills
against plan rules, one line item at a time. A Django web app (Team 10).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # then fill in a real SECRET_KEY
python manage.py migrate
python manage.py runserver  # uses settings/development.py by default
```

Visit `http://127.0.0.1:8000/admin/` to log in (see docs/notes/notes.txt
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
├── requirements.txt
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
pip install -r requirements.txt
echo "SECRET_KEY=<your key>" > .env
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
