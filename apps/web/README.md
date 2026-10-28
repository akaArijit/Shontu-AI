# Fund Engine Dashboard (apps/web)

Next.js 14 + TypeScript + Tailwind dashboard for the MFD Fund Monitoring &
Scoring Engine. Deployed on **Vercel**; the API lives in `apps/api` on Railway.

## Pages

- **Dashboard** — summary cards, scheme table, alerts, category rankings
- **Alerts** — full alert center with bulk resolve/dismiss
- **Rankings** — peer comparison within SEBI categories
- **CSV Upload** — scheme master, benchmark mappings, benchmark history, exports
- **Pipeline** — data freshness, run history, system health
- **Settings** — scoring weights, alert rules, benchmark mappings, display

## Local development

```bash
cd apps/web
npm ci
cp .env.example .env.local     # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                    # http://localhost:3000
```

Start the API from `apps/api` (`uvicorn api.main:app --reload --port 8000`) or
set `NEXT_PUBLIC_USE_MOCK_API=true` to use generated demo data.

## Build

```bash
npm run build
npm run start
```

## Deploy (Vercel)

1. Vercel → **Add New → Project** → import the repo.
2. **Root Directory:** `apps/web`.
3. Environment variables (Production + Preview):
   - `NEXT_PUBLIC_API_URL` — bare Railway origin, e.g. `https://fund-engine-api.up.railway.app`
   - `NEXT_PUBLIC_USE_MOCK_API` — `false`
   - `NEXT_PUBLIC_SITE_URL` — optional canonical URL for metadata
4. Deploy. `NEXT_PUBLIC_*` values are inlined at build time, so redeploy after
   changing them.

The browser calls the API directly, so add the Vercel domain to the API's
`ALLOWED_ORIGINS` (and optionally `ALLOWED_ORIGIN_REGEX` for previews). Full
runbook: [../../docs/DEPLOYMENT.md](../../docs/DEPLOYMENT.md).

## Scripts

| Script | Purpose |
|--------|---------|
| `npm run dev` | Development server |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | Next.js lint |

## Notes

- `next.config.js` sets security headers (HSTS, `X-Frame-Options`, `nosniff`,
  referrer/permissions policies) and disables `X-Powered-By`.
- `src/app/error.tsx`, `not-found.tsx`, and `loading.tsx` provide production
  error/empty states.
- Metadata sets `robots: noindex` — this is an internal tool.
