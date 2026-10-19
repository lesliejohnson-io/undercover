# Plan: the claims pilot

From `docs/SPEC.md`, built on the skeleton described in `docs/STATUS.md`.

## The shape of the build

**The backend owns everything.** It seeds a SQLite database from `data/` at startup and is the only way to reach a claim, a policy, a customer, the policy wording or the agent's instructions. The agent and the dashboard are both clients of the same API. The rule for what goes where: records go in the database (claims, policies, customers, plans, handlers, company settings, decisions, payments, activity), documents stay as files on disk (`data/policy_wording.md`).

**The agent gets claim-scoped tools.** `run(claim_id, thread_id)` builds its tools as closures over the claim id, so a tool takes no claim argument and the agent cannot reach another claim. Each tool records a step through the API as it runs, which is what the dashboard replays for "what the agent is doing, step by step". The agent fetches its own system prompt from `GET /api/instructions`, so the instructions the handlers read are the instructions it runs on.

**The $1,000 rule lives in the backend.** Paying is its own operation that takes an amount, and it refuses while a claim is waiting for sign-off. The agent is given a `pay_claim` tool on purpose, so the guard is a real server-side check rather than a prompt instruction, and there is a test that the agent's own payment is refused.

**Four states, as the team asked for them:** `waiting`, `in_progress`, `awaiting_signoff`, `decided`. Decline and refer go straight to `decided`. Approve at or under $1,000 pays and goes to `decided`. Approve over $1,000 goes to `awaiting_signoff`, and only after a handler signs off can the payment go through.

### The API

Every operation has an `operation_id`, a one-line docstring and no optional inputs.

| Operation | Route |
|---|---|
| `health` | `GET /api/health` |
| `list_claims` | `GET /api/claims` |
| `get_claim` | `GET /api/claims/{claim_id}` |
| `get_claim_policy` | `GET /api/claims/{claim_id}/policy` |
| `get_claim_customer` | `GET /api/claims/{claim_id}/customer` |
| `get_policy_wording` | `GET /api/policy-wording` |
| `get_instructions` | `GET /api/instructions` |
| `list_activity` | `GET /api/claims/{claim_id}/activity` |
| `add_activity` | `POST /api/claims/{claim_id}/activity` |
| `decide_claim` | `POST /api/claims/{claim_id}/decision` |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` |
| `sign_off_claim` | `POST /api/claims/{claim_id}/signoff` |
| `run_agent` | `POST /api/claims/{claim_id}/run` |
| `list_handlers` | `GET /api/handlers` |

`data/evals/` is the answer key and this build never opens it. Checking the agent's accuracy against the handlers' decisions is not part of the pilot.

### Two notes on the brief

- `docs/BRAND.md` names Sea Green and Marigold for three things side by side but gives no hex for either. I am reading the palette it does give as the source of truth and using Cerulean for waiting, Light Blue for in progress, Coral for waiting for sign-off, Teal for decided and Raspberry for declined.
- `data/claims.json` ships every claim with `status: "open"`, which I seed as `waiting`.

---

## Phase 1: the business data in the backend

A SQLite store seeded from `data/`, and the read-only half of the API.

Build `backend/db.py` (connection, schema, seed from `data/*.json`, keyed off a `UNDERCOVER_DB` path so tests get their own), `backend/models.py` (the Pydantic shapes the API returns) and the read routes in `backend/main.py`. Claims keep typed columns for what the queue lists and sorts on, with the nested parts (items, documents, travelers, previous claims, add-ons) as JSON text.

- [x] `uv run pytest -q` passes, with tests covering: the seed loads 25 claims, 50 policies, 49 customers, 3 plans and 3 handlers; every claim seeds as `waiting`; `get_claim` returns the story, the items, the documents and the amount claimed; `get_claim_policy` returns the plan's limits and deductible alongside the trip; `get_claim_customer` returns the previous claims; an unknown claim id gives 404
- [x] `curl http://localhost:8000/api/claims` returns 25 claims, each with `claim_id`, `customer_name`, `claim_type`, `submitted_on`, `amount_claimed` and `status: "waiting"`
- [x] `curl http://localhost:8000/api/claims/CLM-1001` returns the Rome trip delay claim with its four documents and `amount_claimed: 420.0`
- [x] `curl http://localhost:8000/api/claims/CLM-1001/policy` returns POL-2001 on the `premium` plan with `trip_delay_waiting_hours: 6` and `trip_delay_max: 800.0`
- [x] `curl http://localhost:8000/api/claims/CLM-1001/customer` returns Maya Patel with her 2024 baggage delay claim
- [x] `curl http://localhost:8000/api/policy-wording` returns the wording, including the section 10 payment steps
- [x] Deleting the database file and restarting the backend re-seeds it; the queue is back to 25 waiting claims
- [x] `npm run check:python` is clean

## Phase 2: decisions, sign-off and the payment guard

The half of the API that changes a claim, and the $1,000 rule.

`decide_claim` takes the decision, the payout, the reason and the policy section, and sets the next status. `pay_claim` takes the amount and refuses with 409 unless the claim is approved and either at or under the limit or signed off. `sign_off_claim` takes a handler id. `add_activity` and `list_activity` record and replay the agent's steps.

- [x] `uv run pytest -q` passes, with tests covering: approving $420 moves CLM-1001 to `decided` and a $420 payment succeeds; approving $2,400 moves a claim to `awaiting_signoff` and a $2,400 payment is refused with 409; the same payment succeeds after sign-off and the claim is then `decided`; declining and referring both land on `decided`; a payment on a declined claim is refused; paying twice is refused; a payout that does not match the decision is refused; `list_activity` returns steps in the order they were added
- [x] `POST /api/claims/CLM-1001/decision` with approve, $420, a reason and "Section 3" returns the claim as `decided`
- [x] A claim approved over the limit shows `status: "awaiting_signoff"` in `GET /api/claims`, and `POST .../payment` returns 409 with a message naming the sign-off
- [x] `POST .../signoff` with `HND-01` then `POST .../payment` returns the recorded payment
- [x] The payout approval limit comes from `company.json`, not a literal in the code: a test that seeds a different limit changes where the guard falls
- [x] `npm run check:python` is clean

## Phase 3: the UnderCover Agent

The agent decides a claim end to end, and the backend can start it.

`agent/main.py` keeps the `run(claim_id, thread_id)` entry point and gains claim-scoped tools: `read_claim`, `read_policy`, `read_customer`, `read_policy_wording`, `record_decision` and `pay_claim`. Each records its step through `add_activity`. The system prompt comes from `GET /api/instructions`, which serves the instructions from `agent/instructions.md` so the handlers' read-only page and the agent read one file. The prompt tells it how to work a claim: check the dates and the filing window, find the benefit and its section, work the payout out by the wording's section 10 steps, and refer rather than guess when a document is missing. `run_agent` starts a run in the background, sets the claim to `in_progress` and clears its earlier activity.

- [x] `uv run pytest -q` passes with a stub model and no network: a scripted approve records the decision and the payment and leaves the claim `decided`; a scripted approve over the limit leaves it `awaiting_signoff` with the agent's `pay_claim` refused and that refusal recorded as a step; a scripted refer leaves it `decided`; the tools are bound to the one claim id; the instructions reach the agent as its system prompt
- [x] `curl http://localhost:8000/api/instructions` returns the text of `agent/instructions.md`
- [x] One real run on the queue's simplest claim: `uv run python -c "from agent.main import run; print(run('CLM-1001', 'plan-check'))"` approves it, pays a payout at or under $800 against section 3, and `GET /api/claims/CLM-1001/activity` lists the steps it took in order
- [x] One real run on a claim whose payout clears $1,000 ends `awaiting_signoff` with no payment recorded
- [x] `POST /api/claims/CLM-1002/run` returns immediately with the claim `in_progress`, and polling `GET /api/claims/CLM-1002/activity` shows steps arriving
- [x] `npm run check:python` is clean

## Phase 4: the dashboard, the queue

The queue page, on the brand.

`dashboard/src/` gains the brand in one stylesheet (Archivo, Instrument Serif and JetBrains Mono from Google Fonts, the palette as CSS variables, light and dark surfaces, rounded panels with no outline), a small `api.ts`, and the queue page: one row per claim with the customer, the type, the amount claimed, the date and a state chip, plus counts by state. Money renders as `$1,250.00` and ids in JetBrains Mono.

- [x] `vitest run --root dashboard --coverage` passes at 80%+, with tests covering: the queue renders a row per claim from a stubbed API; the state chip shows all four states; amounts render as `$420.00`; a failed fetch shows a plain message rather than a blank page
- [x] `npm run check:ts` is clean, with no `any` in the new code
- [x] In the browser over Playwright MCP: `http://localhost:5173` lists the 25 claims with their states, and the fonts and palette match `docs/BRAND.md`
- [x] The page is readable in both light and dark mode; I check both and keep a screenshot of each
- [x] `e2e/queue.spec.ts` passes: the queue shows CLM-1001 with Maya Patel, and clicking the row opens the claim

## Phase 5: the dashboard, the claim and the instructions

The claim page the handlers work from, and the agent's instructions read only.

The claim page shows the story, the items, the documents, the policy and the plan's limits, the customer's history, and the agent's decision with its reason and policy section. While the claim is `in_progress` it polls the activity every second and shows the steps as they arrive. It carries the Run button, and for a claim waiting for sign-off, a handler picker, a Sign off button and then a Pay button. `/instructions` renders the agent's instructions, read only.

- [x] `vitest run --root dashboard --coverage` passes at 80%+, with tests covering: the claim page renders the story, items, documents and the decision from a stubbed API; the activity list grows while the claim is in progress and stops polling once it is not; the sign-off and pay controls appear only for a claim awaiting sign-off, and the pay button only after sign-off; the instructions page renders the text and offers no way to edit it
- [x] `npm run check:ts` is clean
- [x] In the browser over Playwright MCP: open CLM-1001, press Run, watch the steps appear one by one and the decision and its reason land on the page
- [x] In the browser over Playwright MCP: a claim over $1,000 shows waiting for sign-off, signing off as Dana Whitfield reveals Pay, and paying moves it to decided
- [x] In the browser over Playwright MCP: `/instructions` shows the same text as `GET /api/instructions`
- [x] `e2e/claim.spec.ts` passes, covering the claim page, the sign-off and payment flow and the
      instructions page, without calling the agent. The e2e run gets its own database and ports, so
      it is repeatable and can run beside `npm run dev`

## Phase 6: the whole queue, and the checks

Work the queue end to end and hand it over.

- [ ] A run over all 25 claims leaves every claim in `decided` or `awaiting_signoff`, none in `waiting` or `in_progress`, and every decided claim carries a decision, a reason and a policy section
- [ ] Every claim approved over $1,000 is `awaiting_signoff` with no payment recorded; every payment recorded is at or under $1,000 or signed off. I confirm this straight from the database, not from the API
- [ ] The queue page shows the finished queue with its counts by state, in both light and dark mode
- [ ] `docs/STATUS.md` describes what is built and how to run it
- [ ] `README.md` is a short description of the product and how to start it
- [ ] `npm run check` passes: ruff, pyright, pytest at 80%+, ESLint, Prettier, tsc, vitest at 80%+ and the Playwright tests. I report the output
