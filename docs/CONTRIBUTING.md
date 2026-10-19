# Contributing

## Branches
- `main` is always deployable. Never commit to it directly.
- One branch per chunk of work, branched from `main`:
  `feat/<name>`, `fix/<name>`, `chore/<name>`, `docs/<name>`, `test/<name>`.
- Merge by pull request (squash or merge commit), even when working solo.

## Commits — Conventional Commits
```
<type>(<scope>): <what changed, imperative, lower-case>
```
Types: `feat`, `fix`, `test`, `docs`, `chore`, `refactor`, `perf`, `ci`.
Scopes: `auth`, `tours`, `purchases`, `sessions`, `social`, `admin`, `db`, `infra`, `docs`.

Examples
- `feat(auth): deliver otp by email`
- `fix(auth): stop returning otp in api response`
- `test(purchases): webhook replay does not double-credit`

Rules: one logical change per commit; keep commits small; never commit `.env` or real credentials.

## Pull requests
- Title follows the commit convention.
- Description: what, why, how it was tested, and any doc/API changes.
- Checklist: tests added/updated · docs updated · no secrets · CI green.

## Releases
Each checkpoint is tagged: `v0.2-cp1`, `v0.2-cp2`, then `v0.2.0`.

## Layout
```
backend/   FastAPI service (app/, alembic/, tests/, scripts/)
docs/      design docs, plan, API changelog, DB notes
web/       not maintained by the backend workstream
mobile/    not maintained by the backend workstream
```
