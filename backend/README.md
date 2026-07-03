# Backend

## Demo seed data

Run the demo seeding script from the `backend/` directory after configuring your `.env` file:

```bash
python -m app.scripts.seed_demo_data
```

If you already created the tables with Alembic or another migration workflow, you can skip table creation:

```bash
python -m app.scripts.seed_demo_data --skip-create-tables
```

The seeder is idempotent, so it can be run multiple times without creating duplicate demo rows.

If you do not have a PostgreSQL driver installed yet, the backend will fall back to a local SQLite database file (`energy_resilience.db`) for demo mode. For production, set `DATABASE_URL` to PostgreSQL.

### Demo login credentials

- Admin: `demo.admin@energy.local`
- Password: `DemoAdmin123!`

- Analyst: `demo.analyst@energy.local`
- Password: `DemoAnalyst123!`

## Production note

For production environments, prefer Alembic migrations instead of `Base.metadata.create_all()`.
