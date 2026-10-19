# NoB documentation

| Path | What it is |
|---|---|
| [`design/`](design/) | The 12 product/design docs (vision → definition of done). Source of truth for *intent*. |
| [`BACKEND_PLAN.md`](BACKEND_PLAN.md) | 3-day backend plan: chunks, checkpoints, status. |
| [`DATABASE.md`](DATABASE.md) | How the design schema maps to the real tables. |
| [`API_CHANGELOG.md`](API_CHANGELOG.md) | Endpoints added/changed since the original API spec. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Branching, commit and PR conventions. |
| [`reference/`](reference/) | Legacy artefacts kept for history (old raw SQL schema, UI overview image). |

Rule (Definition of Done §Documentation): a PR that changes behaviour updates the matching doc in the same PR.

Frontend reference: the UI screenshots supplied by the product owner are the **only** frontend reference.
The `web/` and `mobile/` folders are not maintained by the backend workstream.
