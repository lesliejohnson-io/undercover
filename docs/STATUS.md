# Status

The claims pilot, in progress. See `docs/PLAN.md` for the phases.

## Built

- `backend/`: SQLite seeded from `data/` at startup, and the read side of the API.
  - `db.py` the schema and the seed, `store.py` the reads and writes, `models.py` the API shapes
  - `GET /api/health`, `/api/claims`, `/api/claims/{claim_id}`, `/api/claims/{claim_id}/policy`,
    `/api/claims/{claim_id}/customer`, `/api/claims/{claim_id}/activity`, `/api/policy-wording`, `/api/handlers`
- `agent/`: still the skeleton, `run(claim_id, thread_id)` with a health-check tool
- `dashboard/`: still the skeleton, one page showing whether the backend is up
- `e2e/`: one test of that page

## Running it

`uv sync` and `npm install`, then `npm run dev` for the backend on port 8000 and the dashboard on port 5173.
The database is `backend/undercover.db`; delete it to go back to the seeded queue of 25 waiting claims.

`npm run check` runs every check.
