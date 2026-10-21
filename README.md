# NoB — Neighbourhoods of Bangalore

Self-guided, GPS-triggered audio walking tours of Bangalore neighbourhoods.

## Repository layout

```
backend/   FastAPI + PostgreSQL service      <- actively developed
docs/      design docs, backend plan, DB notes, API changelog, contributing guide
web/       legacy web client (not maintained by the backend workstream)
mobile/    legacy mobile client (not maintained by the backend workstream)
docker-compose.yml, nginx.conf   local/staging infrastructure
```

## Start here
- Connect a frontend: [`docs/INTEGRATION.md`](docs/INTEGRATION.md), client kit in [`docs/frontend-kit/`](docs/frontend-kit/)
- Deploy to staging: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md); legal notes: [`docs/LEGAL_NOTES.md`](docs/LEGAL_NOTES.md)
- Plan and status: [`docs/BACKEND_PLAN.md`](docs/BACKEND_PLAN.md)
- Backend setup and API: [`backend/README.md`](backend/README.md)
- How we work (branches, commits, PRs): [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md)
- Product/design docs: [`docs/design/`](docs/design/)
