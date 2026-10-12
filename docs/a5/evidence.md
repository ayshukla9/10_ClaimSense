# Evidence register

Status at preparation: production URL and access unavailable; no production screenshots captured, no real Google login tested, no video recorded.

| Requirement | Evidence to capture | Actual result |
|---|---|---|
| Production deployment | URL, deployed SHA, date/time, reload outcome | Pending access |
| Anonymous protection | Hidden navigation; bill redirect; private JSON 401 | Pending production |
| Internal auth | Signup, password login, approved navigation, POST logout | Pending production |
| Authorization | New account 403; approved staff access | Pending production |
| Google OAuth | Successful localhost and production callback; no secrets in capture | Pending credentials |
| Public API | Anonymous JSON, Content-Type, actual database counts | Pending production |
| Vega-Lite | Absolute production .txt spec and rendered editor chart | Pending production URL |
| CSV reporting | CSV output and source URL screenshot | Pending production |
| Browser dashboard | Live counts and source URL screenshot | Pending production |
| Catalogue monitoring | Source URL and actual PASS/FAIL screenshot | Pending production |
| Team video | Real presenters, production demonstration, duration <=300 seconds | Pending recording |

Use filenames such as `production-private-api-401.png`, `production-google-success.png`, `production-vega-chart.png`, `usecase-csv.png`, `usecase-dashboard.png`, `usecase-monitor.png`. Add only files actually captured. Record timestamp, source URL and observed result next to each filename. Redact patient information and credential values. Local automated test evidence is separate and does not satisfy production evidence.
