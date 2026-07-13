# Supabase Setup

Supabase is required when Render does not have a durable PostgreSQL database.

## Database Decision

Local default: SQLite at `sqlite+aiosqlite:///./nexora.db`  
Durable on Render: no  
Suitable for Render paper positions: no  
Supabase required on Render when no other durable PostgreSQL `DATABASE_URL` is configured: yes

Reason:

- Render application filesystem is not the correct place for paper-trading state.
- Paper positions, candles, signals, job locks, and provider health must survive restarts and redeployments.

## Required Supabase Value

Use the Supabase PostgreSQL connection string as:

```text
DATABASE_URL
```

The application uses SQLAlchemy/Alembic directly. Supabase Auth, Storage, Realtime and Edge Functions are not required.

## Conditional Values

- `DIRECT_URL`: only if a separate direct migration connection is needed.
- `SUPABASE_URL`: not required unless Supabase REST/Realtime/Storage is later used.
- `SUPABASE_SERVICE_ROLE_KEY`: not required for current server runtime.
- `SUPABASE_ANON_KEY`: not required without a public frontend.

Never expose service role keys in browser or public code.

## Migration

Render start command runs:

```text
alembic upgrade head
```

The latest migration adds persistent scheduler locks, job execution records, and system incidents.
