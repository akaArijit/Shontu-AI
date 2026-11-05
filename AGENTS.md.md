# MFD Portfolio Dashboard — Agent Rules

Read README.md for full product, workflow, calculation, privacy, and troubleshooting details.

## Purpose

This is a local, privacy-first MFD dashboard.

Core workflow:
Upload InvestWell files → Review benchmark mappings → Import local benchmark levels → View Benchmark Cluster Graph.

This is not a full business-analytics dashboard. InvestWell handles detailed analytics.

## Non-negotiable rules

- Keep the app local-only.
- Do not add cloud deployment, authentication, payments, web search, AI/Ollama, voice, or live benchmark fetching unless explicitly requested.
- Never store or send PAN, Aadhaar, email, mobile, address, bank, KYC, nominee, or other sensitive personal identifiers.
- Never ask the user to paste real client data into OpenCode chat.
- Never guess, repair, interpolate, or allocate missing client/folio/benchmark data.
- Show missing data as “Not available” and explain the exact reason.
- Do not modify the separate fund-engine project.

## Tech stack

- Frontend: Next.js + TypeScript + Tailwind CSS
- Backend: FastAPI + SQLAlchemy
- Database: SQLite
- Project root: C:\Users\ariji\Desktop\Shontu AI\mfd-dashboard

## Commands

Start app:

```powershell
.\start.ps1
```

Backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api --disable-warnings
```

Frontend tests:

```powershell
cd apps\web
npm test
```

Frontend build:

```powershell
cd apps\web
npm run build
```

## UI rules

Main navigation must remain simple:

1. Upload
2. Benchmark Data
3. Graph

Do not show heavy analytics, KPI grids, client/folio tables, Business Review, concentration charts, or extra dashboards on the landing page.

Use the existing warm graphite/charcoal identity, copper primary actions, parchment text, and soft peach graph canvas.

Avoid generic navy-blue AI-dashboard styling.

Colour meanings:
- Emerald: folio ahead of benchmark.
- Rose: folio behind benchmark.
- Amber: mapping/data needs review.
- Grey: comparison not available.
- Copper/blue: neutral primary actions.
- Dark bronze/graphite: benchmark nucleus.

## Graph rules

The Benchmark Cluster Graph is the main feature.

- Use the existing deterministic organic cluster layout.
- Do not change it unless explicitly requested.
- Benchmark nucleus: dark bronze/graphite.
- Folio primary label: client name.
- Folio secondary label: scheme name at closer zoom.
- Folio ID: tooltip/detail popup only.
- Keep search, filters, tooltips, folio popup, zoom, pan, fit, reset, fullscreen, and the moving X/Y coordinate grid.
- The graph must handle 200+ folios smoothly.

## Benchmark rules

- Include the full major NSE India benchmark list, approximately 119 benchmarks.
- All benchmarks must be selectable, even without folios or local level data.
- Benchmark level data is imported locally only for benchmarks the user tracks.
- Missing levels remain “Not available”; never interpolate or estimate.
- Bulk mapping is scheme-level and must remain reviewable.
- Keyword rules and mapping imports require preview/validation before applying.
- Never silently assign benchmarks.

## Working style

- Work in small milestones.
- Before major changes, give a brief plan.
- After each milestone, stop and wait for user approval.
- Do not add features not explicitly requested.
- Do not change database schema, importer logic, XIRR logic, benchmark comparison logic, or APIs unless specifically required.
- Keep changes focused; avoid unnecessary file reads and broad refactors.
## Response format rule

After completing any task, always end your response with a section called:

## Completion Summary

Give exactly 2–3 short lines:

1. What was completed.
2. Test/build result.
3. What is pending or needs user approval.

Do not include long logs, full file lists, or detailed technical explanations in the Completion Summary.
Keep the rest of the response concise.