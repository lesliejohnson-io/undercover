# Status

The claims pilot, in progress. See `docs/PLAN.md` for the phases.

## Built

- `backend/`: SQLite seeded from `data/` at startup, and the read side of the API.
  - `db.py` the schema and the seed, `store.py` the reads and writes, `models.py` the API shapes
  - reads: `GET /api/health`, `/api/claims`, `/api/claims/{claim_id}`, `/api/claims/{claim_id}/policy`,
    `/api/claims/{claim_id}/customer`, `/api/claims/{claim_id}/activity`, `/api/policy-wording`, `/api/handlers`
  - writes: `POST /api/claims/{claim_id}/decision`, `/signoff`, `/payment`, `/activity`, `/start`, `/run`
  - `GET /api/instructions` serves `agent/instructions.md`
  - `POST /api/claims/{claim_id}/run` sets the claim to `in_progress` and returns before the agent
    finishes, so the dashboard can poll the activity while it works
- A claim runs `waiting` to `in_progress` to `awaiting_signoff` or `decided`. A payout over the
  `payout_approval_limit` in `data/company.json` goes to `awaiting_signoff`, and the payment is
  refused with a 409 until a handler signs off. The limit is read from the database, not the code.
- `agent/`: decides a claim end to end. `run(claim_id, thread_id)` hands the claim to the agent and
  works it; `work` is the loop the backend runs in the background.
  - its instructions are `agent/instructions.md`, which it reads through `GET /api/instructions`,
    the same text the handlers see
  - its tools are built per claim by `tools_for(claim_id)`, so none of them takes a claim id:
    `read_claim`, `read_policy`, `read_customer`, `read_policy_wording`, `record_decision`, `pay_claim`
  - each read records a step through the API, and the backend records what changed, so the
    activity on a claim is the trail of a run
  - `openai/gpt-6-luna` at low reasoning effort, or `MODEL_NAME` when it is set
- `dashboard/`: the queue, on the brand in `src/brand.css` (Archivo, Instrument Serif and
  JetBrains Mono from Google Fonts, the palette as variables, light and dark surfaces).
  - `api.ts` the typed client, `route.ts` hash routing (`#/`, `#/claims/{id}`, `#/instructions`),
    `useLoad.ts` the loading hook, `Queue.tsx` the queue with counts by state
  - state chips: Cerulean waiting, Light Blue in progress, Coral waiting for sign-off, Teal decided
- `e2e/`: `queue.spec.ts` covers the queue and opening a claim

## Running it

`uv sync` and `npm install`, then `npm run dev` for the backend on port 8000 and the dashboard on port 5173.
The database is `backend/undercover.db`; delete it to go back to the seeded queue of 25 waiting claims.

`npm run check` runs every check.
