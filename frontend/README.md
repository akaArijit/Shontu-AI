# MFD Fund Monitoring Dashboard - Frontend

Next.js 14 + TypeScript + Tailwind CSS frontend for the MFD Fund Monitoring & Scoring Engine.

## Features

- **Dashboard** - Overview with summary cards, scheme table, alerts panel
- **Alerts Center** - Full alert management with bulk actions
- **Category Rankings** - Peer comparison within SEBI categories
- **Pipeline Health** - Data freshness, run history, system resources
- **Settings** - Scoring weights, alert rules, benchmark mappings, notifications, user management

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State Management**: TanStack Query (React Query)
- **HTTP Client**: Axios
- **Charts**: Recharts (ready for integration)
- **Icons**: Lucide React
- **Forms**: Native HTML with custom components

## Getting Started

### Prerequisites
- Node.js 18+
- Backend API running on `http://localhost:8000` (or set `NEXT_PUBLIC_API_URL`)

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

Opens at `http://localhost:3000`

### Production Build

```bash
npm run build
npm start
```

## Environment Variables

Create `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Project Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── dashboard/          # Main dashboard
│   ├── alerts/             # Alerts center
│   ├── rankings/           # Category rankings
│   ├── pipeline/           # Pipeline health
│   ├── settings/           # Configuration
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Redirect to dashboard
│   └── globals.css         # Global styles
├── components/
│   ├── ui/                 # Reusable UI components
│   ├── layout/             # Layout components (Sidebar, Header, DashboardLayout)
│   └── dashboard/          # Dashboard-specific components
├── hooks/
│   └── useQueries.ts       # TanStack Query hooks
├── lib/
│   ├── api.ts              # Axios client + API functions
│   └── utils.ts            # Utility functions
├── hooks/
│   └── useQueries.ts       # React Query hooks
├── types/
│   └── index.ts            # TypeScript types
└── hooks/
    └── useQueries.ts       # TanStack Query hooks
```

## API Integration

The frontend connects to the MFD Fund Monitoring API at `NEXT_PUBLIC_API_URL`. All endpoints are prefixed with `/api/v1/mfd/`.

Key endpoints used:
- `GET /mfd/schemes` - All schemes with scores
- `GET /mfd/scores` - Fund health scores
- `GET /mfd/alerts` - Alerts with filtering
- `GET /mfd/alerts/summary` - Alert counts by severity
- `POST /mfd/alerts/{id}/resolve` - Resolve alert
- `POST /mfd/alerts/{id}/dismiss` - Dismiss alert
- `GET /mfd/rankings/category/{category}` - Category rankings
- `GET /mfd/health` - Pipeline health
- `GET /mfd/meta/*` - Config metadata

## Key Features

### Dashboard
- Summary cards (total schemes, avg score, AUM, alerts)
- Interactive scheme table with sorting, filtering, search
- Real-time alerts panel with bulk actions

### Alerts Center
- Filter by severity, type, scheme
- Bulk resolve/dismiss with reasons
- Individual resolve/dismiss actions

### Category Rankings
- Per-category peer rankings
- Sortable by score, return, alpha, drawdown, volatility
- Percentile display

### Pipeline Health
- Real-time pipeline status
- Data freshness indicators
- Run history table
- System resource monitoring

### Settings
- Scoring weights (drag sliders, total must = 100%)
- Alert rules with category overrides
- Benchmark mappings management
- Notification preferences
- Database/API config
- User management

## Deployment

### Docker
```bash
docker build -t mfd-dashboard .
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=https://api.yourdomain.com mfd-dashboard
```

### Vercel (Recommended)
1. Connect GitHub repo
2. Set `NEXT_PUBLIC_API_URL` in Vercel dashboard
3. Deploy

### Build Output
- Static optimization where possible
- Server-side rendering for dashboard
- Client-side for interactive components

## Customization

### Theming
Edit `tailwind.config.ts` for colors, fonts, shadows.

### Adding New Pages
1. Create `src/app/new-page/page.tsx`
2. Use `DashboardLayout` wrapper
3. Add to `Sidebar.tsx` navigation

### Adding New API Endpoints
1. Add types in `src/types/index.ts`
2. Add API function in `src/lib/api.ts`
3. Add hook in `src/hooks/useQueries.ts`
4. Use in components

## License

Internal MFD Use Only