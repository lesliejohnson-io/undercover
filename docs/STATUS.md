# Status

The claims pilot is built: the backend, the dashboard and the UnderCover Agent. `docs/PLAN.md` has
the plan it was built to, with every phase ticked off.

## What it does

A handler opens the queue, opens a claim and presses Run. The agent reads the claim, the policy,
the customer and the policy wording, decides the claim, and pays it. The handler watches the steps
arrive, reads the decision and its reason, and signs off a payout over the approval limit.

## The parts

### `backend/` (FastAPI and SQLite)

Seeds `backend/undercover.db` from `data/` the first time it starts. Delete the file to go back to
a queue of 25 waiting claims. Records go in the database (claims, policies, customers, plans,
handlers, company settings, decisions, payments, activity); documents stay as files
(`data/policy_wording.md`, `agent/instructions.md`).

- `db.py` the schema and the seed, `store.py` the reads and writes, `models.py` the API shapes,
  `main.py` the routes
- reads: `GET /api/health`, `/api/claims`, `/api/claims/{claim_id}`, `/api/claims/{claim_id}/policy`,
  `/api/claims/{claim_id}/customer`, `/api/claims/{claim_id}/activity`, `/api/policy-wording`,
  `/api/instructions`, `/api/handlers`
- writes: `POST /api/claims/{claim_id}/decision`, `/signoff`, `/payment`, `/activity`, `/start`, `/run`
- a claim runs `waiting` to `in_progress` to `awaiting_signoff` or `decided`
- **the payment guard**: paying is its own operation and takes the amount. A payout over the
  `payout_approval_limit` in `data/company.json` sends the claim to `awaiting_signoff`, and the
  payment is refused with a 409 until a handler signs off. The limit is read from the database, not
  written into the code, and the guard holds when the agent calls `pay_claim` itself
- `POST /api/claims/{claim_id}/run` sets the claim to `in_progress` and returns before the agent
  finishes, so the dashboard can poll the activity while it works

### `agent/` (LangChain `create_agent` on OpenRouter)

- `run(claim_id, thread_id)` hands the claim to the agent and works it; `work` is the loop the
  backend runs in the background
- its instructions are `agent/instructions.md`, read through `GET /api/instructions`, the same text
  the handlers see on the dashboard
- `tools_for(claim_id)` builds its tools per claim, so none of them takes a claim id and it cannot
  reach another claim: `read_claim`, `read_policy`, `read_customer`, `read_policy_wording`,
  `record_decision`, `pay_claim`
- each read records a step through the API and the backend records what changed, so a claim's
  activity is the trail of the run
- `openai/gpt-6-luna` at low reasoning effort, or `MODEL_NAME` when it is set

### `dashboard/` (React, Vite and TypeScript)

The brand is in `src/brand.css`: Archivo, Instrument Serif and JetBrains Mono from Google Fonts, the
palette as variables, light and dark surfaces, rounded panels with no outline.

- `api.ts` the typed client, `route.ts` hash routing (`#/`, `#/claims/{id}`, `#/instructions`),
  `useLoad.ts` the loading hook
- `Queue.tsx` the queue, a row per claim with counts by state. State chips: Cerulean waiting,
  Light Blue in progress, Coral waiting for sign-off, Teal decided
- `Claim.tsx` the claim page: the story, items, documents, policy and limits, customer history and
  the agent's decision, with Run, the handler sign-off and the payment. It polls the activity every
  second while the agent works, and keeps polling until an approval inside the limit is paid,
  because a claim leaves `in_progress` at the decision while the agent still has the payment to make
- `Instructions.tsx` shows the agent's instructions read only

### `e2e/` (Playwright)

`queue.spec.ts` and `claim.spec.ts`. The run uses its own database (`backend/e2e.db`, dropped at the
start of each run) and its own ports (backend 8001, dashboard 5174), so it is repeatable and runs
beside `npm run dev`.

## Running it

`uv sync` and `npm install`, then `npm run dev` for the backend on port 8000 and the dashboard on
port 5173. `OPENROUTER_API_KEY` goes in `.env`.

`npm run check` runs every check: ruff, pyright and pytest at 80% coverage; ESLint, Prettier, tsc
and vitest at 80% coverage; and the Playwright tests.

## Where it stands

The agent has worked the whole queue: 22 decided, 3 waiting for sign-off, none left waiting, and
every claim carries a decision, a reason and a section of the wording. Every approval over $1,000 is
waiting for a sign-off with no payment recorded.

Accuracy is not measured yet. `data/evals/` holds the handlers' own decisions and this build never
opens it.
