# ClaimSense UI/UX Redesign Plan

Status: draft for team review · Scope: Django templates + `static/css` only (no model or view-logic changes unless noted)

## 1. Why the current UI feels bad

Taken from the app as it stands (`templates/base.html`, `static/css/style.css`, the screenshots in `presentation_screenshots/`).

| # | Problem | Where | Why it matters |
|---|---------|-------|----------------|
| 1 | **12 flat nav links**, most of them named after assignments (Search, Lookup, Summary, Charts, Vega-Lite, Procedures, API) | `base.html` | A patient can't tell where to go. The nav shows how the course was structured, not what a patient needs to do. |
| 2 | **Nothing says "what do I owe / what looks wrong"** | Home | The headline number on the home page is "13 bills tracked". The patient's real question (how much do I owe, and which charges should I dispute?) never gets answered. |
| 3 | **Serif body with sans nav, gold-on-navy links, header boxed in at 900px** | `style.css` | Looks dated and inconsistent, and the dark header bars stop short of the window edges. |
| 4 | **Money is hard to read**: `$1800.00`, no thousands separators, not right-aligned, not tabular | bill detail, reports | The core data of the app is the hardest thing to scan. |
| 5 | **Bill metadata is a stack of bold labels**, and "Out of Network" is hidden in parentheses | bill detail | The most important risk signal looks like every other line. |
| 6 | **Developer copy shown to users**: model names, `LOCAL_LLM_DEVICE=mps`, `GEMINI_API_KEY`, retrieval ms, match scores | Explain, Ask AI | It feels like a debug console and makes users trust it less. |
| 7 | **Explain page is a 6-column table** with a checkbox first, a plain-text "review" pill and warnings in brown | `bill_explain.html` | It's cramped, and the action (appeal) comes before the reason (the flags). |
| 8 | **Flash messages are plain paragraphs** ("Successfully signed in as ecarter1.") | `base.html` | They're easy to miss and look like page content. |
| 9 | **No mobile layout**: tables overflow, nav wraps into a wall | everywhere | The viewport meta tag is set, but nothing actually responds to screen width. |
| 10 | **Accessibility gaps**: no visible focus style, no skip link, unverified contrast for gold on navy, color-only flags | everywhere | Needed for WCAG 2.1 AA. |

## 2. Goals and principles

1. **Answer the patient's three questions on every screen:** *What do I owe? What looks wrong? What can I do about it?*
2. **Lead with the money.** Large, tabular, right-aligned currency, with the patient's share as the hero number.
3. **Flags first, then actions.** Every "review" flag shows a reason, the plan rule, and a next step (Ask AI or appeal).
4. **Hide the plumbing.** Model names, timings, scores and env vars go behind a "How this works" disclosure, or are shown to staff only.
5. **Calm, trustworthy, clinical.** One sans-serif family, plenty of white space, color used only for meaning.
6. **No build step.** Keep plain Django templates and a single hand-written CSS system so PythonAnywhere deploys stay the same.

## 3. Information architecture

### New primary nav (patient)
```
[ClaimSense]   Dashboard   Bills   Ask AI   Insights            [Emma Carter ▾]
                                                                  Account · Log out
```
Staff also get **Manage**.

### Where every current page goes

| Current nav item / route | New home |
|---|---|
| Home `/` | **Dashboard** |
| All Bills `/bills/render/`, Search `/bills/search/`, Lookup `/bills/lookup/` | **Bills** (one list page with a search box and filters; Lookup becomes "jump to reference #" in the search box) |
| Bill detail + Explain `/bills/<pk>/`, `/bills/<pk>/explain/` | **Bill detail** with an "AI review" tab/section (the Explain route stays as its own URL) |
| Ask AI `/ask/` | **Ask AI** |
| Summary, Reports, Charts, Vega-Lite | **Insights** (one page: KPI tiles, charts, per-provider tables, CSV/JSON export) |
| Procedures `/procedures/` | Link from Bill detail ("Look up this procedure") and from Insights |
| API, CBV variants, public plan API | **Developer** page linked from the footer (the routes don't change) |

> **Every URL keeps working.** Graders and `claims/tests.py` hit these routes directly. Only the links and layout change.

## 4. Visual design system

Lives in `static/css/` split into `tokens.css`, `base.css`, `components.css` (or sections inside one `style.css` if we want a single file).

**Color tokens**
| Token | Value | Use |
|---|---|---|
| `--ink` | `#0f172a` | body text |
| `--muted` | `#64748b` | secondary text |
| `--surface` / `--canvas` | `#ffffff` / `#f6f7fb` | cards / page |
| `--border` | `#e5e7eb` | dividers |
| `--brand` | `#13294b` (keep the Illini navy) | header, primary buttons |
| `--accent` | `#ffb612` (gold, **logo only**, never body links) | brand mark |
| `--link` | `#1d4ed8` | links |
| `--ok` / `--ok-bg` | `#15803d` / `#dcfce7` | covered, no issues |
| `--warn` / `--warn-bg` | `#b45309` / `#fef3c7` | needs review |
| `--danger` / `--danger-bg` | `#b91c1c` / `#fee2e2` | out of network, denied |

Add dark mode later; it isn't in the first pass.

**Type**: Inter (Google Fonts) or the system UI stack everywhere. Scale: 12 / 14 / 16 (body) / 20 / 24 / 32. Use `font-variant-numeric: tabular-nums` on all money.

**Spacing**: 4px base (4, 8, 12, 16, 24, 32, 48). Radius is 8px on cards and 6px on inputs and buttons.

**Layout**: full-bleed header, content max-width 1120px, 12-column CSS grid that collapses to one column below 768px.

**Template filter**: add a `money` filter (`claims/templatetags/money.py`) that renders `$1,800.00`, and use it everywhere instead of `${{ x }}`.

### Components (one Django `{% include %}` partial each, in `templates/components/`)
- `app_header` + responsive nav (a hamburger `<details>` on mobile, no JS needed)
- `flash` (toast-style alerts: success / info / warning / error, `role="status"`)
- `kpi_tile` (label, big number, optional delta or sub-label)
- `status_badge` (In network / Out of network / Needs review / OK, always with an icon and text, never color alone)
- `money_table` (right-aligned numbers, sticky header, cards on mobile)
- `bill_card` (for lists on mobile and the dashboard)
- `empty_state` (icon, one sentence, primary action)
- `callout` (info / warning; replaces `.ai-notice`)
- `disclosure` ("How this works" / "Sources", wrapping `<details>`)
- Buttons: primary / secondary / ghost, with a visible `:focus-visible` ring

## 5. Screen-by-screen redesign

### 5.1 Dashboard (`home.html`)
- Greeting + plan chip: "Hi Emma · IlliniCare Student PPO".
- **KPI row:** *You owe* (hero) · *Plan covered* · *Charges flagged* · *Out-of-network bills*.
- **"Needs your attention"** list: bills with flagged or out-of-network items, each with a one-line reason and a "Review" button.
- **Recent bills** as cards (provider, date, you owe, status badge).
- **Ask AI** prompt box with 3 example chips.
- Logged-out version: hero ("Know what your insurance is actually worth"), 3 benefit tiles, Log in / Sign up.
- *Needs:* view adds the aggregated totals plus a flagged count, reusing `summaries.py`.

### 5.2 Bills (`bill_list.html`, merges search/lookup)
- Search box ("Search provider, reference #, or procedure"), filter chips (Network, Date range, Has flags), sort.
- Table on desktop; `bill_card` stack on mobile.
- Columns: Reference · Provider (+ network badge) · Date · Charged · **You owe** · Status.

### 5.3 Bill detail (`bill_detail.html`)
- Header: provider name (big), reference # and date (muted), network badge, plan chip.
- **Summary strip:** Charged → Covered → **You owe**, with a stacked bar showing the split.
- Line items table using the `money` filter, right-aligned, with a totals row in a light (not navy) style.
- Primary CTA **"Review this bill with AI"**; secondary "Ask about a charge", "Look up procedure".
- Breadcrumb `Bills / CLM-1004` replaces "← Back home".

### 5.4 AI review (`bill_explain.html`)
- Intro is one sentence. The model and tech details go in a "How this works" disclosure.
- **One card per line item** instead of a 6-column table:
  - Title, amounts, status badge (OK / Needs review)
  - Plain-English explanation
  - "Why we flagged it" bullets (the current `issues`)
  - "Your plan says…" disclosure (plan rule)
  - Checkbox "Include in appeal" at the **bottom** of the card
- Sticky bottom bar: "2 charges selected · Draft appeal letter".
- Loading state for the slow local model: disable the button, show "Reviewing 2 charges… this can take up to a minute".
- When Gemini isn't configured, patients see "Appeal letters aren't available on this server yet". The env-var hint is shown to staff only.

### 5.5 Appeal letter (`bill_appeal.html`)
- Letter in a paper-style card, with **Copy** and **Download .txt** buttons and highlighted placeholders (`[Your name]`) to fill in.

### 5.6 Ask AI (`ask_plan.html`)
- Chat-like layout: the question at top, the answer card below with inline citation chips `[1]` that jump to sources.
- Example questions as clickable chips (pre-fill the textarea; tiny inline JS, or links with `?q=`).
- Warnings become a `callout` ("This answer doesn't cite your plan. Check the sources.").
- Timings, backend and match scores go in a "Details" disclosure. Sources become a list, not a table.
- Loading state on submit.

### 5.7 Insights (merges Summary, Reports, Charts, Vega-Lite)
- KPI tiles → "Spending by provider" chart → "In vs. out of network" chart → tables → Export buttons.
- Restyle the Vega-Lite specs with the new tokens (font, colors); see `static/vega-lite/*.vl.json`.

### 5.8 Auth (`templates/account/*`)
- Centered card, logo, Google button styled to match, inline field errors.

### 5.9 Global
- Toast-style flash messages; signing in shows "Welcome back, Emma" instead of the username.
- Footer: "Not legal or medical advice · Developer API · Team 10".
- Skip-to-content link, visible focus, `aria-current="page"` on the active nav item.

## 6. Accessibility and responsive checklist
- [x] Contrast ≥ 4.5:1 for text. Every token pair was checked; `--muted` was darkened to `#5b6b80` (5.1:1 on the page background). Gold is used only on navy (8.3:1).
- [x] Every status conveyed with text + dot, not color only
- [x] `:focus-visible` ring on all interactive elements; skip link
- [x] Tables have `scope`d headers; tables that scroll sideways become focusable, labelled regions (`static/js/ui.js`)
- [x] Touch targets ≥ 40px (buttons/inputs) and 44px for mobile nav items
- [x] No horizontal scroll at 375px on any page (Vega charts were fixed in Phase 5)
- [~] Forms: `<label>` for every input; auth errors are shown under each field but not yet linked with `aria-describedby`
- [x] `prefers-reduced-motion` respected

**Phase 5 audit (2026-11-11):** axe-core 4.10.2 (WCAG 2.0/2.1 A + AA + best practices) reports **0 violations** on: home (both states), login, signup, Dashboard, Bills, Bill detail, AI review (after running), Ask AI (with an answer), Insights, Developer, Procedure lookup, Search, Summary, Matplotlib chart and Vega-Lite pages. Fixed along the way: added an `<h1>` on every page (headings shifted h2→h1, h3→h2), keyboard access for scrolling tables and charts, and labels for the Vega export menus.

## 7. Delivery phases

| Phase | Work | Output | Est. |
|---|---|---|---|
| **0. Align** | Team reviews this plan; pick font (Inter vs system), confirm nav labels; quick hi-fi mock of Dashboard + Bill detail (Figma or HTML) | Approved direction | 1–2 days |
| **1. Foundation** | Tokens, base CSS, `money` filter, component partials, new `base.html` shell (header, nav, flash, footer) | Every page instantly looks consistent | 2–3 days |
| **2. Core flow** | Dashboard, Bills (merged search), Bill detail | The patient happy path is done | 3–4 days |
| **3. AI screens** | AI review cards, appeal letter, Ask AI chat layout, loading states, hide dev copy | The demo-critical screens are polished | 3 days |
| **4. Insights & misc** | Merge reports/charts/vega, Developer page, auth pages, procedure lookup | Nav reduced to 4 items | 2 days |
| **5. QA** | A11y audit, mobile pass, update tests, refresh `presentation_screenshots/` | Ready to demo | 1–2 days |

Suggested split (4 people): **A** foundation + shell (blocks everyone, so do it first), then **B** Dashboard/Bills/Detail, **C** AI review/appeal/Ask, **D** Insights/auth/Developer/QA. Use one feature branch per phase off `main`, following `docs/branching_strategy/`.

## 8. Risks and constraints
- **Tests assert on template text.** `claims/tests.py` checks for `'All Bills'`, `'Vega-Lite'`, `'>Manage</a>'`, `'ai-flag-review'`, `'Plan rule:'`, `'Ask about your plan'`, `'Sources'`, `'Provider is out of network.'`, among others. Either keep those strings and class names (e.g. keep the `ai-flag-review` class on the new badge, and keep "Vega-Lite" as a label on the Insights page and in the footer), or update the tests in the same PR. Run `python manage.py test claims` before every merge.
- **Course grading may expect specific pages.** Keep all routes, and keep the Developer page linking to every assignment view.
- **Local LLM latency.** Loading states are needed, not optional; ideally add a small inline script to disable buttons on submit.
- **No frontend build.** Avoid Tailwind/React unless the team agrees to add a build step; plain CSS custom properties are enough.

## 9. Definition of done
- 4–5 item nav; every old route still reachable.
- Dashboard shows *You owe* and *Needs attention* above the fold.
- All currency rendered with `money` filter, right-aligned, tabular.
- No model names, env vars, or timings visible to non-staff users by default.
- Passes the §6 checklist at 375px and 1440px.
- `python manage.py test claims` green; screenshots refreshed.

## 10. Open questions for the team
1. Font: Inter via Google Fonts, or system UI (zero network requests)?
2. Do we want hi-fi mocks in Figma first, or go straight to HTML/CSS and iterate in the browser?
3. Is it OK to change visible nav labels the tests check for (and update the tests), or must those strings stay?
4. Is the dark mode in scope for this cycle?

## 11. Status (2026-11-11)

All five phases are built on branch `feature/ui-phase1-foundation` (not yet committed).

| Phase | Result |
|---|---|
| 1. Foundation | Design tokens and components in `static/css/style.css`, `money` filter, `templates/components/`, new header/footer shell |
| 2. Core flow | Dashboard with totals and "Needs your attention", Bills with search/filters, flags on Bill detail (`claims/bill_insights.py`) |
| 3. AI screens | AI review as one card per charge, appeal letter with Copy/Download, Ask AI with citations; technical details collapsed |
| 4. Insights & misc | Insights page with themed Vega charts, `/developer/` page, auth pages; nav reduced to Dashboard · Bills · Ask AI · Insights |
| 5. QA | Accessibility audit and fixes, 375px pass, 47 tests passing, new screenshots in `../presentation_screenshots_v2/` |

Answers to §10: system font (no Google Fonts); went straight to HTML/CSS; nav labels changed and tests updated; dark mode not done.

**Follow-up pass (2026-11-11, branch `feature/ui-intuitive`):** "Explain with AI" is a POST button on the dashboard
and bill detail, so one click runs the review (no intermediate page); example questions ask in one click; the page
scrolls to the answer; the plan rule is shown in full under each charge; flag badges have tooltips and a "What the
flags mean" legend; the missing-citation warning is an info note; without a Gemini key the appeal checkboxes are
replaced by "What you can do next"; the header shows the patient's name. 49 tests passing.

Known gaps: the appeal letter page was not checked in a browser (no Gemini key on the test machine); auth field errors aren't linked with `aria-describedby`; in "Charges over time", bills on the same date make the line jump vertically (from the original spec).
