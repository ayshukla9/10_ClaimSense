# Team production demo — 290 seconds maximum

Assign these presenter roles to the real team members before recording; no names are assumed. Every actual team member must introduce themselves and speak if required by the full rubric. Rehearse within the allocated slots, including browser delays.

| Time | Presenter role | Screen and narration |
|---|---|---|
| 0–20 s | Opening presenter | Show production URL and introduce actual team members. Explain ClaimSense and the existing repo. |
| 20–65 s | Internal auth presenter | Fresh anonymous session: hidden protected navigation, bill-page login redirect, private API 401. Show custom signup and username/password login. Use a preapproved demo operator for records access; explain that new accounts require approval. |
| 65–100 s | Internal auth presenter | Show approved navigation and a protected bill page using permitted demo records; POST logout and show links disappearing. |
| 100–145 s | OAuth presenter | From production custom login/signup page, Continue with Google; complete real authorization, return to ClaimSense and show signed-in state. Log out. Show callback URI configuration without showing client secrets. |
| 145–180 s | API presenter | Anonymous production public plan-types endpoint; explain database grouping and fields. Contrast private bill API 401 and signed-in nonstaff 403. |
| 180–215 s | Visualization presenter | Show production-backed Vega Editor chart and .txt spec's absolute data URL. Explain nominal plan type and quantitative count. |
| 215–260 s | Use-case presenter(s) | Show actual CSV, browser dashboard and monitoring outputs/screenshots; explain three consumers of the same endpoint. |
| 260–290 s | Closing presenter | Show existing GitHub repo's merged commit and deployed version evidence, state actual checks, then end. |

Preflight: deploy and reload; preapprove demo accounts; use permitted demonstration records; register exact production callback; ensure test-user consent access; open required tabs; generate absolute .txt spec; capture real evidence; hide credentials; assign real speaking roles; record at most 300 seconds. Do not claim successful OAuth or production tests when blocked. If access remains unavailable, this script is preparation only and the assignment is incomplete.
