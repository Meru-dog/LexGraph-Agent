# CLAUDE.md

## Stack
- Framework: Next.js 15 (App Router), TypeScript
- Styling: Tailwind CSS, shadcn/ui
- Database: Supabase (PostgreSQL) + Drizzle ORM
- Auth: Supabase Auth
- Validation: Zod + React Hook Form
- Package manager: pnpm

## Project Structure
```
app/
  (auth)/         # Auth pages
  (dashboard)/    # Authenticated pages
  actions/        # Server Actions
  api/            # API Routes (minimal use)
components/
  ui/             # shadcn/ui (auto-generated)
  features/       # Domain-specific components
lib/
  db/             # Drizzle client + schema
  supabase/       # Supabase client (server/client separated)
types/            # Shared type definitions
```

## Conventions
- Prefer Server Actions for data fetching and mutation; use API Routes only for external integrations
- All DB access must go through `lib/db/` — no direct queries elsewhere
- Zod schemas are the single source of truth for validation and TypeScript types
- Error handling follows `{ data, error }` return shape throughout
- Use `"use client"` only when strictly necessary

## Naming
- Components: PascalCase (`TaskCard.tsx`)
- Functions & variables: camelCase (`createTask`)
- DB columns: snake_case (`created_at`)
- Types/schemas: PascalCase with `Type` or `Schema` suffix

## Commands
```bash
pnpm dev          # Start dev server
pnpm build        # Production build
pnpm lint         # Run ESLint
pnpm db:push      # Apply Drizzle schema to DB
pnpm db:studio    # Open Drizzle Studio (DB GUI)
```

## Environment Variables
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=    # Server-side only — never expose to client
DATABASE_URL=
```

## Key Constraints
- Variables without `NEXT_PUBLIC_` prefix are server-side only
- Server Components may access the DB directly
- Client Components must use Server Actions for all DB access