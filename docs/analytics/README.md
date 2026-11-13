# ClaimSense AI analytics dashboard (P1 analytics)

Team 10 · ClaimSense · INFO 490 MG, Fall 2026

**Where:** `/analytics/`. The nav bar shows **Analytics** to staff accounts only. Patients get HTTP 403, and anonymous
visitors are sent to log in. Filters: period (7 / 30 / 90 days / all), data (real / simulated / both), and feature
(Ask AI / Explain with AI / appeal letter).

| Piece | File |
| --- | --- |
| Log model (one row per AI request) | `claims/models.py` → `AIRequestLog`, migration `0003_ai_request_log` |
| Measuring: tokens, timing, topic | `claims/ai/usage.py` (`track()`, `log_request()`, `topic_for()`); token counts in `claims/ai/local_llm.py` → `count_tokens()` |
| Logging points | `claims/views_ai.py`: `ask_plan` (every outcome, incl. rejected / rate-limited / errors), `bill_explain`, `bill_appeal` |
| Metrics + Vega-Lite specs | `claims/analytics.py` (`QUESTIONS`, `load()`, `build()`, `specs()`) |
| Page | `claims/views_analytics.py`, `claims/templates/claims/ai_analytics.html` |
| Data | real: `docs/analytics/collect_real_logs.py` → `real_logs_2026-11-13.json`; simulated: `manage.py simulate_ai_logs` |
| Grader account | `manage.py create_staff_account <username> --password ...` |
| Tests | `claims/tests.py` → `AnalyticsTests` (8 tests) |

## 1. Questions

**System performance**
* **P1.** How is response time distributed, and how far is the slow tail (p95) from a typical request (p50)?
* **P2.** Which kinds of request are slow: model calls vs. cached answers vs. requests stopped before the model? Does
  bill size (line items) matter?
* **P3.** Does a longer answer explain the latency, and is response time stable from day to day?

**User behavior**
* **U1.** How often are the AI features used, and is usage growing?
* **U2.** What do users ask about, and which topics does the system fail to answer?
* **U3.** Which exact questions are asked most, and which ones expose gaps in our plan documents?
* **U4.** When do people use the AI (day of week × hour), so we know when load peaks?

**Cost**
* **C1.** What does one request cost on our own server, and what would the same tokens cost on a hosted API?
* **C2.** Which features and topics consume the most tokens?
* **C3.** How does cost move with usage over time, and how much does the 24-hour answer cache save?

## 2. Widgets: question → widget → data

| Q | Widget | Data (AIRequestLog fields) |
| --- | --- | --- |
| P1 | KPIs: p50, p95, p95/p50, CV, cached p50, failed %; **histogram** of latency with p50/p95 rules | `total_s` of uncached model calls (`llm_calls > 0`, `cached = False`); `status` |
| P2 | **Bar (median) + tick (p95)** per request type, with n | `feature`, `cached`, `llm_calls`, `items`, `status`, `backend`, `total_s` |
| P3 | **Scatter**: output tokens vs. seconds, with Pearson r; **line**: daily p50 and p95 | `completion_tokens`, `total_s`, `created_at` |
| U1 | KPIs: requests, per day, trend %; **stacked bar** of requests/day by feature + **7-day moving average** line | `created_at`, `feature` |
| U2 | **Stacked bar**: questions per topic, split by outcome | `topic` (keyword classifier), `status` → outcome group |
| U3 | **Tables**: most asked questions (with % answered); knowledge gaps (questions with no matching plan section) | `question`, `status` |
| U4 | **Heatmap** weekday × hour | `created_at` (server local time) |
| C1 | KPIs: $ per 1,000 requests (our server vs. hosted API), tokens per model request; **table** per feature/topic: tokens, model seconds, $ per 1,000 both ways | `prompt_tokens`, `completion_tokens`, `generation_s`, `backend` |
| C2 | **Stacked bar**: prompt vs. completion tokens per topic / feature | `prompt_tokens`, `completion_tokens`, `topic`, `feature` |
| C3 | **Line**: daily $ (our server vs. hosted API); KPI: % saved by cache | the cost columns per day; `cached` |

**Cost model** (`settings/base.py`, all overridable in `.env`). The local model has no per-call fee, so we estimate
two numbers:
1. **Our server:** model-busy seconds × `ANALYTICS_COMPUTE_USD_PER_HOUR`. The default of $0.30/h is an assumed price
   for an 8 vCPU / 32 GB cloud VM; set it to your host's real price.
2. **Hosted API equivalent:** the same tokens at gpt-oss-120b prices, $0.037 in / $0.17 out per 1M tokens. That's
   the hosted model from our A6 benchmark, priced from the A7 snapshot `llm-test/results/api_pricing_snapshot.csv`.

Cache savings = cached requests × the mean cost of an uncached request of the same feature.

## 3. Statistical thinking

* **Percentiles, not just means.** Latency is right-skewed (cold starts, long answers), so we report p50 and p95 and
  their ratio (tail heaviness). The mean is shown only in tooltips.
* **Distribution:** a histogram of latency shows its shape (clusters by feature, the long tail).
* **Consistency:** coefficient of variation (std ÷ mean) is one number for "how predictable is response time".
* **Group comparisons:** median and p95 per request type (P2), outcome shares per topic (U2), and cost per
  feature/topic (C1).
* **Correlation:** Pearson r between output tokens and latency (P3). In the real logs r = 0.79, so answer length
  drives latency, and the 120-token cap bounds it.
* **Trends:** a 7-day moving average smooths weekday/weekend swings, the growth % compares the 2nd half of the
  period with the 1st, and daily p50/p95 separate "occasionally slow" from "slower overall".
* **Normalized cost:** $ per 1,000 requests and tokens per request, so periods and features of different sizes compare.

## 4. Data

* **Real logs (27 requests).** `collect_real_logs.py` uses the app as five demo patients (their own plans): Ask AI
  questions, including repeats (cache), questions our documents don't cover, an off-topic question and an injection
  attempt, plus Explain with AI on six bills. All of it runs through the real views and the real local models on the demo PC (CPU,
  bfloat16). Exported, with user links removed, to `real_logs_2026-11-13.json` (pks 900001+).
* **Simulated logs.** `python manage.py simulate_ai_logs [--days 30 --seed 490]` creates ~400 rows with
  `simulated=True`, calibrated on the real logs: ~390 prompt tokens per question, ~0.1 s per output token,
  ~7 s per bill line item, 25–30% cache hits, 2% cold starts, and usage growing from 10 to 22 requests/day with
  quieter weekends. The same seed gives the same data. Real rows are never touched. Filter **Data → Real logs only**
  to see only measured data.
* **Production** (PythonAnywhere, no torch): real requests there are logged as `model_off` / search-only, so the
  dashboard also shows how the hosted web version behaves.

## 5. Run it

```bash
python manage.py migrate
python manage.py loaddata docs/analytics/real_logs_2026-11-13.json   # the 27 real requests
python manage.py simulate_ai_logs                                     # simulated history
python manage.py create_staff_account <username> --password '<password>'
python manage.py runserver   # log in as a staff user → Analytics
```

## 6. Deploy to PythonAnywhere

In a Bash console on the PythonAnywhere account:

```bash
cd ~/10_ClaimSense && git pull origin main          # (or wherever the repo lives)
workon <virtualenv>                                 # if the web app uses one
python manage.py migrate
python manage.py loaddata docs/analytics/real_logs_2026-11-13.json
python manage.py simulate_ai_logs
python manage.py create_staff_account mohitg2 --password '<the password from the assignment>'
python manage.py collectstatic --noinput            # only if the site serves collected static files
```

Then **Reload** the web app on the Web tab. There are no new Python dependencies (Vega-Lite loads from the CDN, as on
the Insights page).
