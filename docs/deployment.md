# Deployment

This project is containerized for local development and production-style deployment with Docker Compose.

## Services

- `backend`: FastAPI application served by Uvicorn
- `postgres`: PostgreSQL database for persistent application data
- `redis`: Redis for scheduler/job state and cache-like workflows
- `nginx`: static frontend server and reverse proxy for `/api/*`

## Prerequisites

- Docker
- Docker Compose v2

## Local startup

From the repository root:

```bash
docker compose -f infra/docker-compose.yml up --build
```

The services will be available at:

- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:8080/api/v1`
- Backend docs: `http://localhost:8080/docs`
- Backend redoc: `http://localhost:8080/redoc`

## Environment variables

The compose file is wired through environment variables with safe defaults. Override them in your shell or in an `infra/.env` file.

Important variables:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `BACKEND_PORT`
- `FRONTEND_PORT`
- `SECRET_KEY`
- `ENABLE_SCHEDULER`
- `DEMO_MODE`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `GEMINI_BASE_URL`

## Backend image

The backend image is built from [`backend/Dockerfile`](../backend/Dockerfile) and starts with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Nginx routing

The Nginx container:

- serves the static frontend from `/usr/share/nginx/html`
- proxies `/api/*` requests to the backend service
- proxies `/docs`, `/redoc`, and `/openapi.json` to the backend service
- exposes a simple `/health` endpoint

## Health checks

Health checks are defined for:

- PostgreSQL using `pg_isready`
- Redis using `redis-cli ping`
- Backend using `GET /health`
- Nginx using a local request to `/`

## Production notes

- Set `DEMO_MODE=false` when you switch to live integrations.
- Store real secrets outside source control.
- If you run behind a platform load balancer, keep Nginx as the public entrypoint and expose only the frontend port.
- For persistent demo data, the database and Redis volumes are named volumes managed by Docker Compose.
- PostgreSQL and Redis stay internal to the Compose network by default, which avoids host port collisions such as `5432` being occupied locally.

## Manual backend run without Compose

If you want to run just the backend locally:

```bash
cd backend
uvicorn app.main:app --reload
```

The app reads its settings from environment variables or `backend/.env`.
