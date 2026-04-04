# Frontend MVP

React + TypeScript frontend for the Multi-Agent Personal Knowledge Copilot backend.

## Pages

- `Chat`: private-document QA flow with route badges, citations, and retrieved chunk previews
- `Documents`: upload, list, inspect, reindex, and delete indexed documents

## Run locally

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

The frontend expects the FastAPI backend at `http://127.0.0.1:8000/api` by default.

## Run with the full stack

```powershell
cd infra
docker compose up --build
```

This starts PostgreSQL, Qdrant, the FastAPI backend, and the Vite frontend together.

Override with:

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:8000/api"
```
