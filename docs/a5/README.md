# P1-A5.1 implementation and submission status

This work extends the existing ayshukla9/10_ClaimSense repository. No new repository is required.
The available assignment preview ends at the beginning of Part 3; check the complete Canvas rubric before submission.

## Implemented

- Custom allauth username/password signup, login and POST/CSRF-protected logout templates.
- Login URL and redirect settings; password validation; Google provider and environment-only credentials.
- Protected navigation, every existing patient page, exports, chart image and API route.
- Anonymous pages redirect to login; anonymous private APIs return JSON HTTP 401. All signed-in accounts can open ordinary pages and private APIs. Nonstaff accounts see only bills belonging to their explicitly linked `Patient.user`; unlinked accounts see empty results, and other patient detail URLs return 404. Staff retain full record access. Manage and Django admin remain staff-only. Never grant staff status merely to enable ordinary navigation.
- Exactly one unauthenticated JSON API: `GET /api/public/plan-types/`. It counts `InsurancePlan` rows grouped by `plan_type`, returning an array of `{plan_type, plan_count}`. It does not disclose patient details, bill references, plan names or amounts. An empty database returns `[]`; POST returns 405. Wildcard CORS applies only to this public GET endpoint.
- A5 Vega-Lite .txt spec at `static/vega-lite/plan_types.txt`, displayed on the protected Vega-Lite page. Its relative URL queries the current deployed origin when hosted there. Existing private chart APIs remain usable by signed-in users within their record scope.
- Three runnable alternative API consumers in `examples/` and a 290-second production demo script.

## Production status — October 12, 2026

A5 was merged into `main` at `5788b1f21f278f31dcc313070fc39a79d8e6a26f` and the PythonAnywhere checkout was updated to that commit. The team supplied successful production screenshots and command output; these observations describe the captured session, not a continuous uptime guarantee.

- Website: https://okc2.pythonanywhere.com/
- Public API: https://okc2.pythonanywhere.com/api/public/plan-types/
- Real Google signup and returning login were completed. New accounts have no patient records until staff explicitly link them.
- The linked regular demo account displayed five bills; reports and private charts were populated.
- The public catalogue returned EPO 2, HMO 3, OTHER 1, PPO 1: seven plans across four types, including synthetic demonstration plans.
- `docs/a5/production_plan_types.txt` was generated on the server and rendered in the external Vega-Lite editor using the absolute production API URL. Download and rename it to `group-x-vega-lite-API-demo.txt`, replacing `x` with the official group number.
- CSV spreadsheet, external browser dashboard, and monitor PASS evidence were captured against production. See [the evidence register](evidence.md) for capture details and archive status.

Still outstanding: record the team video (maximum 300 seconds), bring its opening into line with the full rubric, and assemble the submission files. Google Auth Platform remains External / Testing; Publish app is disabled pending Branding completion. Production availability needs a fresh check after a later browser connection-refused report. Secrets and demo credentials belong only in private course notes, never this repository. Preserve the live SQLite database and private `.env` when updating the deployment.

## Local checks

Create a virtual environment, install `requirements.txt`, set a fresh `SECRET_KEY`, and run:

```sh
python manage.py test claims
python manage.py check
python manage.py migrate
python manage.py runserver
```

Tests use an isolated test database and synthetic data. Do not commit a migrated production/local database.
Tests exercise signup, password login/logout, CSRF, unsafe redirect rejection, every private route for anonymous and regular accounts, including ownership isolation across pages, exports and aggregates, staff access, public database counts, MIME/CORS/method checks, invalid dates, and Google redirect initiation with test-only credentials. Initiation does not establish a successful Google login.

## Google OAuth setup (both environments)

1. Use Google Cloud project `claimsense-511422` (ClaimSense), with an OAuth client of type **Web application**. Declare only the basic sign-in scopes: OpenID, email and profile. Complete Branding and publish when available. Google documents a Testing-mode test-user exception for apps requesting only these basic identity scopes; do not assume Testing alone blocks every grader. See [Google production readiness](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview).
2. Register exact redirect URIs:
   - `http://localhost:8000/accounts/google/login/callback/`
   - `http://127.0.0.1:8000/accounts/google/login/callback/` (if using that hostname locally)
   - `https://okc2.pythonanywhere.com/accounts/google/login/callback/`
3. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in the local and server environment or private `.env`. Never commit them, show them in screenshots or paste them into the video.
4. The configuration uses provider `APPS`; do not create a second Google SocialApp in Django admin. No Sites framework setup is necessary with this approach.
5. Run migrations and reload the server. Both custom pages then enable Continue with Google. Google authorization starts via POST with CSRF and allauth verifies OAuth state. Use the actual domain's HTTPS URL; production settings trust PythonAnywhere's forwarded HTTPS header.
6. Complete real Google authorization in localhost and production. A new Google account can immediately use ordinary pages and APIs, with the same record scope as password accounts. Do not enable automatic email-based account linking.

References: [allauth quickstart](https://docs.allauth.org/en/latest/installation/quickstart.html), [Google provider configuration](https://docs.allauth.org/en/latest/socialaccount/providers/google.html).

## Deploy to the existing PythonAnywhere app

After review/merge of the feature branch into main:

1. Back up the live SQLite database to a private server directory. Preserve the live `.env`, accounts and patient records. Prefer a private database path outside the checkout via `DATABASE_PATH`; migrate the existing data there without replacing it with the repository sample database.
2. In the existing server checkout: `git pull --ff-only origin main`.
3. Activate the existing web app virtualenv; `pip install -r requirements-web.txt` (since A6, `requirements.txt` also includes torch for the local AI model, which does not fit PythonAnywhere's free disk; see README_AI.md).
4. Configure a strong SECRET_KEY, the exact `ALLOWED_HOSTS=okc2.pythonanywhere.com`, and Google credentials in private environment configuration.
5. Ensure the existing PythonAnywhere WSGI file adds this checkout to `sys.path` and sets `DJANGO_SETTINGS_MODULE=claimsense_project.settings.production` before importing Django's WSGI application. Retain existing host-specific paths.
6. Run `python manage.py migrate --settings=claimsense_project.settings.production`, then `python manage.py collectstatic --noinput --settings=claimsense_project.settings.production`. Map `/static/` to this checkout's `staticfiles/` directory in the Web tab. Reload the existing web app.
7. Test in a fresh anonymous browser: home has no patient data; bills redirect; `/api/bills/` returns 401; only `/api/public/plan-types/` returns public JSON.
8. Test internal signup/login/logout, regular-account navigation and empty results, linked-patient access and cross-patient isolation, and staff-only management. Test Google login and logout on the actual production URL.
9. Generate the external-editor submission spec:
   `python docs/a5/build_vega_spec.py https://okc2.pythonanywhere.com`
   This creates `docs/a5/production_plan_types.txt`. Paste the JSON into the Vega Editor, verify it fetches production data, and save the chart screenshot. Do not submit the relative-URL spec to an external editor.
10. Record production date/time, deployed commit SHA, actual URLs, actual outcomes and screenshots in `evidence.md`. A failed check remains failed until retested.

## Three alternative API uses and screenshot guidance

Set `ORIGIN` to the actual production origin. All consumers use the same single public endpoint without cookies.

1. **Reporting / CSV export:** `python docs/a5/examples/catalogue_csv.py "$ORIGIN" > plan-catalogue.csv`. Open CSV in a spreadsheet and screenshot the header and live rows alongside a visible production API browser tab. Explain that another reporting tool can consume database-backed JSON without access to patient records.
2. **External browser dashboard:** open `docs/a5/examples/catalogue_dashboard.html`, enter the production origin and press Load live counts. Screenshot the resulting counts and visible source URL. Explain the API's public-only CORS header and JSON parsing; distinguish this simple dashboard from Vega-Lite.
3. **Automated catalogue health check:** `python docs/a5/examples/catalogue_monitor.py "$ORIGIN"`. Screenshot the terminal command, production source URL and PASS/FAIL result. Explain empty catalogue detection and exit status for automation. A network failure is not a passing health check.

For each example preserve the code, screenshot filename, production URL, capture time and interpretation in `evidence.md`. Compare row counts against the production API. Never present test fixture results as production evidence.

## Patient ownership migration

Apply migration `claims.0002_patient_user` before reloading the deployed app. Existing records remain unlinked and private to staff; this migration does not assign or expose records automatically. In Django admin, a staff administrator can edit a Patient and select the verified account in the new User field. Never assign ownership from a matching signup email alone. New password and Google accounts do not need staff status to navigate. For a populated grader/video experience, explicitly link a permitted synthetic demonstration patient to the demonstration account. Real records must only be linked to their verified owner.

## Populate the public chart for the assignment

On the deployed assignment database, after migrating, run:

```sh
python manage.py seed_demo_catalogue --settings=claimsense_project.settings.production
```

This explicit command adds six clearly labelled synthetic insurance plans (3 HMO, 2 EPO, 1 OTHER). It is safe to repeat, does not overwrite existing plans, and creates no accounts, patients or bills. An existing PPO plan gives the public chart four categories with counts 2, 3, 1 and the existing PPO count. The public API, chart specification and three consumers keep their existing URLs and response format. The chart reads the database; without running this command on the server its data will not change. Explain in the video/submission that the catalogue includes synthetic demonstration plans; do not describe the counts as real insurance-market statistics.

For private-page demonstrations, use a dedicated regular account linked by staff to a verified synthetic patient. Keep credentials in the course's private submission notes; never publish them in GitHub. Do not give a grader staff credentials for a database containing real records. Demonstrate fresh signup/Google login with visible navigation first, then the linked demo account for populated bills and charts.
