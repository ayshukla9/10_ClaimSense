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
    ├── views.py               # 2 FBVs + 2 CBVs (P1-A2)
    ├── urls.py
    └── templates/claims/bill_list.html
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
