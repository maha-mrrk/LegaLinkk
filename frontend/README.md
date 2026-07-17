# LegalLink Frontend

React + TypeScript UI for **LegalLink**, matching the product mockup (dashboard, consultation, analysis, agents, supervision, settings, history).

## Stack

- Vite + React 19 + TypeScript
- Tailwind CSS v4
- React Router
- TanStack Query
- Axios (ready for FastAPI)
- React Hook Form
- Lucide React + Recharts

## Quick start

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open http://localhost:5173 — start at `/login`, then enter the app (demo credentials are prefilled).

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Dev server (port 5173, proxies `/api` → `:8000`) |
| `npm run build` | Production build |
| `npm run preview` | Preview production build |

## Structure

```
src/
├── components/     # Sidebar, Navbar, UploadZone, charts, UI kit
├── pages/          # Login, Dashboard, Consultation, Analysis, …
├── layouts/        # App shells with sidebar + navbar
├── services/       # Axios client + document API (mock / real)
├── hooks/          # React Query hooks
├── data/           # Realistic fake data
└── types/          # Shared TypeScript models
```

## Backend wiring

Set `VITE_USE_MOCK=false` and point `VITE_API_BASE_URL` at FastAPI when endpoints are ready. Document upload already calls `POST /api/v1/documents` in non-mock mode.
