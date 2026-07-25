# Frontend Architecture

## Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Fonts**: Geist Sans / Geist Mono (via `next/font`)
- **Theme**: `next-themes` (dark/light/system)

## Directory Structure

```
frontend/
├── src/
│   ├── app/                         # App Router pages
│   │   ├── layout.tsx               # Root layout: ThemeProvider, AuthProvider, DashboardLayout
│   │   ├── page.tsx                 # Home / landing page
│   │   ├── login/                   # Login page
│   │   ├── dashboard/               # Main analytics dashboard
│   │   ├── content/                 # Content library page
│   │   ├── analytics/               # Deep analytics page
│   │   ├── agent/                   # AI Agent chat interface
│   │   ├── pipeline/                # Pipeline control panel
│   │   └── settings/                # User settings
│   ├── components/
│   │   ├── layout/                  # DashboardLayout, Navbar, Sidebar, ThemeProvider
│   │   ├── ui/                      # Badge, Button, Card, Input, Select, Skeleton
│   │   └── onboarding/              # OnboardingFlow component
│   └── lib/
│       ├── api.ts                   # HTTP client for backend API
│       ├── auth-context.tsx         # Auth state management
│       └── utils.ts                 # Utility functions
```

## Key Pages

| Route | File | Purpose |
|-------|------|---------|
| `/` | `page.tsx` | Landing page with platform overview |
| `/login` | `login/page.tsx` | Authentication form |
| `/dashboard` | `dashboard/page.tsx` | Analytics overview with KPIs |
| `/content` | `content/page.tsx` | Browse and search reel content |
| `/analytics` | `analytics/page.tsx` | Deep performance analytics |
| `/agent` | `agent/page.tsx` | AI agent chat interface |
| `/pipeline` | `pipeline/page.tsx` | Pipeline run and status view |
| `/settings` | `settings/page.tsx` | User configuration |

## Auth Flow

1. User logs in via `/login` → POST to `/auth/token`
2. Token stored in `AuthContext` (React context)
3. All API calls include `Authorization: Bearer <token>` header
4. Protected routes redirect to `/login` if no token

## API Client (`src/lib/api.ts`)

Centralized HTTP client wrapping `fetch`:
- Auto-injects `Authorization` header from auth context
- Parses JSON responses
- Handles errors (401 → redirect to login)
- Base URL from `NEXT_PUBLIC_API_URL` env var

## Theme Provider

Uses `next-themes` with `attribute="class"`, enabling Tailwind CSS dark mode via `class` strategy:

```tsx
<ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
```

## SEO

- `metadata` export in `layout.tsx` with Open Graph + Twitter card tags
- `robots.ts`: auto-generated `robots.txt` based on environment
- `sitemap.ts`: auto-generated sitemap from page routes
- `metadataBase` set from `NEXT_PUBLIC_APP_URL`

## Accessibility

- Semantic HTML (`nav`, `main`, `aside`, `section`)
- Proper heading hierarchy (h1 → h6)
- ARIA labels on interactive elements
- Keyboard navigation support
- Focus management on modals/dialogs
- Color contrast ratios meeting WCAG AA

## Performance Optimization

- `next/font` for font loading optimization
- Image component with lazy loading
- Route segment caching via Next.js 15
- Skeleton loading states (`Skeleton` component)
- Minimal client-side JS via React Server Components

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API base URL | `http://localhost:8000` |
| `NEXT_PUBLIC_APP_URL` | Frontend URL | `http://localhost:3000` |

## Docker Build

Multi-stage production build:
1. **deps**: `npm ci` + cache
2. **builder**: `npm run build`
3. **runner**: minimal image with `next start`, non-root `nextjs` user, port 3000, HEALTHCHECK

See `infra/docker/Dockerfile.frontend`.
