# Database setup

DBInspector talks to **any** PostgreSQL read-only. For a demo you have two options.

## Option A — Hosted: Neon.tech (recommended for deploy)

1. Create a free project at https://neon.tech (no credit card).
2. Open the SQL editor and paste a sample schema. Recommended:
   - **Chinook** (music store, perfect for BI questions): https://github.com/lerocha/chinook-database
     Download `Chinook_PostgreSql.sql` and run it.
   - Alternatives: **Sakila** (videoclub), **Northwind** (e-commerce), **DVD Rental** (Postgres tutorial).
3. Open `init/01_readonly_role.sql` from this folder, change `CHANGE_ME`, and run it as the
   Neon owner.
4. Copy the connection string with the `dbinspector_ro` user into your `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://dbinspector_ro:<password>@<neon-host>/<db>
   ```

## Option B — Local: Docker Postgres

(See `docker-compose.yml` at the repo root — to be added.)

## Sanity check from the CLI

```bash
psql "$DATABASE_URL_RO" -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"
```

If that returns a number > 0 you're ready. Then run the pipeline:

```bash
cd backend
python -m app.main "¿Cuáles son los 5 álbumes con más canciones?"
```
