export type ClaimStatus =
  "waiting" | "in_progress" | "awaiting_signoff" | "decided";

export type DecisionName = "approve" | "decline" | "refer";

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface Document {
  name: string;
  type: string;
  content: string;
}

export interface Decision {
  decision: DecisionName;
  payout: number;
  reason: string;
  policy_section: string;
  decided_at: string;
  signed_off_by: string | null;
  signed_off_at: string | null;
  paid_amount: number | null;
  paid_at: string | null;
}

export interface QueueClaim {
  claim_id: string;
  customer_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  submitted_on: string;
  amount_claimed: number;
  status: ClaimStatus;
  decision: DecisionName | null;
  payout: number | null;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  customer_name: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: Item[];
  amount_claimed: number;
  documents: Document[];
  status: ClaimStatus;
  decision: Decision | null;
}

export interface Plan {
  plan: string;
  name: string;
  trip_cancellation_max: number;
  trip_delay_waiting_hours: number;
  trip_delay_max: number;
  baggage_delay_waiting_hours: number;
  baggage_delay_max: number;
  baggage_max: number;
  per_item_limit: number;
  passport_max: number;
  emergency_medical_max: number;
  deductible: number;
}

export interface AddOn {
  add_on: string;
  name: string;
  effect: string;
}

export interface Policy {
  policy_id: string;
  customer_id: string;
  plan: string;
  plan_limits: Plan;
  add_ons: AddOn[];
  purchased_on: string;
  sold_through: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  status: string;
  deductible_applies_to: string[];
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  incident_date: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface Customer {
  customer_id: string;
  name: string;
  email: string;
  phone: string;
  date_of_birth: string;
  address: { street: string; city: string; state: string; zip: string };
  customer_since: string;
  previous_claims: PreviousClaim[];
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
  email: string;
  can_approve_over_limit: boolean;
}

export interface Step {
  step: string;
  detail: string;
  at: string;
}

async function json<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`);
  if (!response.ok)
    throw new Error(`${path} returned ${String(response.status)}`);
  return (await response.json()) as T;
}

async function text(path: string): Promise<string> {
  const response = await fetch(`/api${path}`);
  if (!response.ok)
    throw new Error(`${path} returned ${String(response.status)}`);
  return await response.text();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = (await response.json()) as T & { detail?: string };
  if (!response.ok) throw new Error(payload.detail ?? `${path} failed`);
  return payload;
}

export const api = {
  queue: () => json<QueueClaim[]>("/claims"),
  claim: (id: string) => json<Claim>(`/claims/${id}`),
  policy: (id: string) => json<Policy>(`/claims/${id}/policy`),
  customer: (id: string) => json<Customer>(`/claims/${id}/customer`),
  activity: (id: string) => json<Step[]>(`/claims/${id}/activity`),
  handlers: () => json<Handler[]>("/handlers"),
  instructions: () => text("/instructions"),
  run: (id: string) => post<Claim>(`/claims/${id}/run`, {}),
  signOff: (id: string, handlerId: string) =>
    post<Claim>(`/claims/${id}/signoff`, { handler_id: handlerId }),
  pay: (id: string, amount: number) =>
    post<Claim>(`/claims/${id}/payment`, { amount }),
};

const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function money(amount: number): string {
  return dollars.format(amount);
}

export const stateLabels: Record<ClaimStatus, string> = {
  waiting: "Waiting",
  in_progress: "In progress",
  awaiting_signoff: "Waiting for sign-off",
  decided: "Decided",
};

export function claimTypeLabel(claimType: string): string {
  return claimType.replaceAll("_", " ");
}
