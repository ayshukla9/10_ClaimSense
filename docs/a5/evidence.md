# Evidence register

Updated October 12, 2026. Results below come from team-supplied production screenshots and terminal output. Screenshots were shared in the working conversation; they have not yet been archived under these names in GitHub. Local test results remain separate from production evidence. All capture times below are the screenshot labels, not server UTC timestamps.

Production origin: https://okc2.pythonanywhere.com/
Public API: https://okc2.pythonanywhere.com/api/public/plan-types/
Deployed A5 merge: `5788b1f21f278f31dcc313070fc39a79d8e6a26f` (the team pulled `main` on PythonAnywhere).

| Requirement | Observed evidence | Status / remaining work |
|---|---|---|
| Production deployment | Main pull completed; live home, reports and charts shown October 12 | Deployed. A later connection-refused browser screenshot needs a fresh availability check. |
| Anonymous protection | 6:07:49 PM home capture shows Home / Log in / Sign up and no bills | Anonymous home verified; production private API 401 and detail redirect captures still needed. |
| Internal auth | `user_demo` signed-in home; staff-linked patient then displays five bills (5:48:40 PM) | Password session and linked-record display observed; retain explicit signup/logout evidence for video. |
| Authorization | Unlinked Google account home shows zero bills (6:10:41 PM); linked demo account shows five | Regular users can navigate with scoped results, not a blanket 403. Cross-patient isolation and staff-only access are covered by local tests; complete production negative checks if needed. |
| Google OAuth | Team completed real signup and confirmed returning Google login; shell output shows saved Google SocialAccount | Production login confirmed by team. Local callback evidence not supplied. Cloud publishing remains External / Testing with Branding prerequisite. |
| Public API | Live consumers return EPO 2, HMO 3, OTHER 1, PPO 1 | Seven catalogue plans, including synthetic demo plans. Save an anonymous response/header capture if required. |
| Vega-Lite | External editor chart capture at 6:39:14 PM renders four matching bars | Completed using server-generated `docs/a5/production_plan_types.txt`; download and rename to required `group-x-vega-lite-API-demo.txt`. Screenshot not yet archived here. |
| CSV reporting | Spreadsheet capture shows plan_type / plan_count with 2, 3, 1, 1 | Completed; retain downloaded CSV and screenshot for submission/demo evidence. |
| Browser dashboard | 6:41:28 PM capture shows production source URL and matching live counts | Completed; screenshot not yet archived here. |
| Catalogue monitoring | 6:41:52 PM terminal capture shows production endpoint, seven plans / four types, PASS | Completed at capture time; screenshot not yet archived here. |
| Team video | No completed recording supplied | Outstanding: maximum 300 seconds, required team/title/course slide and exact opening statement. |

## Submission packaging

Submit the public API URL and [GitHub repository](https://github.com/ayshukla9/10_ClaimSense), the renamed production Vega-Lite text file, the working external-editor chart screenshot, and the downloadable team video. Keep the three consumer screenshots as supporting evidence. Use the official group number in the filename. Store demo login credentials only in private course submission notes.

Before recording/submitting, recheck the live API and Google returning login. The successful captures above do not establish current uptime. Do not mark unperformed checks as passing.

## Video opening still to prepare

Start with a slide listing every member's full name and university email, startup name and title, and “INFO 490 MG - Adv AI-Web-Apps Development, Fall 2026”. Include the required statement: “Today is [date]. We are Team XX: … This is the first prototype of our startup product …”, then describe the idea in fewer than five sentences. Update `demo.md` with the actual team details before recording.

When archiving screenshots, record each original capture time, production source URL, and observed result. Redact credentials and any patient information that should not be shared. Do not list a proposed screenshot filename as an already committed artifact.
