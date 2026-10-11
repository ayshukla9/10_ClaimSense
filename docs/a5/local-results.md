# Actual local validation — October 11, 2026

- Eight Django test methods passed on Python 3.14.8, Django 5.2.12, django-allauth 65.19.7. Tests cover all 23 existing private routes as anonymous users and nonstaff users, including GET/POST anonymous protection.
- Development and production settings system checks: no issues. No model migration changes required.
- Allauth migrations succeeded on a separate disposable local SQLite database; the tracked database was unchanged.
- Production static collection succeeded locally: 133 files copied and post-processed.
- Vega-Lite .txt specification rendered to PNG with synthetic data; production-origin generator accepted an HTTPS test hostname and rejected invalid origins. No test hostname was saved as a production deliverable.
- CSV and monitoring consumers fetched localhost synthetic catalogue rows: PPO, 1; monitor returned PASS.
- Browser dashboard served on localhost:8001 fetched localhost:8000 JSON with credentials omitted and displayed PPO: 1 plans. This verifies cross-origin loading locally.
- Login/signup and anonymous home checked in the browser. Final custom login screenshot and local dashboard screenshot are in local-evidence/. They are LOCAL evidence, not production screenshots. Google button is disabled until real environment credentials are configured.
- Real OAuth completion, production deployment/testing and video: not performed; credentials/domain/access were unavailable.

See [raw test output](local-evidence/tests.txt), [local login](local-evidence/local-login.jpg), and [local dashboard](local-evidence/local-dashboard.jpg).
