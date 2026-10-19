import {
  claimTypeLabel,
  money,
  type Claim,
  type Customer,
  type Policy,
} from "./api";

export function Story({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <div className="panel">
      <h3>The claim</h3>
      <p>{claim.story}</p>
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Category</th>
            <th className="money">Amount</th>
          </tr>
        </thead>
        <tbody>
          {claim.items.map((item) => (
            <tr key={item.description}>
              <td>{item.description}</td>
              <td className="quiet">{claimTypeLabel(item.category)}</td>
              <td className="money">{money(item.amount)}</td>
            </tr>
          ))}
          <tr>
            <td colSpan={2}>
              <strong>Claimed</strong>
            </td>
            <td className="money">
              <strong>{money(claim.amount_claimed)}</strong>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function Documents({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <div className="panel">
      <h3>Documents</h3>
      {claim.documents.map((document) => (
        <div className="document" key={document.name}>
          <strong>{document.name}</strong>
          <span className="quiet"> · {claimTypeLabel(document.type)}</span>
          <pre>{document.content}</pre>
        </div>
      ))}
    </div>
  );
}

export function PolicyPanel({
  policy,
}: Readonly<{ policy: Policy | undefined }>) {
  if (!policy) return null;
  const limits = policy.plan_limits;
  return (
    <div className="panel">
      <h3>Policy</h3>
      <p className="mono">{policy.policy_id}</p>
      <p>
        {limits.name} · {policy.trip.destination}
      </p>
      <p className="quiet mono">
        {policy.trip.departs_on} to {policy.trip.returns_on} ·{" "}
        {money(policy.trip.trip_cost)} trip cost
      </p>
      <p className="quiet">
        Travelers: {policy.travelers.join(", ")}
        {policy.add_ons.length > 0 &&
          ` · Add-ons: ${policy.add_ons.map((addOn) => addOn.name).join(", ")}`}
      </p>
      <table>
        <thead>
          <tr>
            <th>Benefit</th>
            <th className="money">Limit</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Trip cancellation</td>
            <td className="money">{money(limits.trip_cancellation_max)}</td>
          </tr>
          <tr>
            <td>Trip delay, after {limits.trip_delay_waiting_hours} hours</td>
            <td className="money">{money(limits.trip_delay_max)}</td>
          </tr>
          <tr>
            <td>
              Baggage delay, after {limits.baggage_delay_waiting_hours} hours
            </td>
            <td className="money">{money(limits.baggage_delay_max)}</td>
          </tr>
          <tr>
            <td>Baggage, {money(limits.per_item_limit)} per item</td>
            <td className="money">{money(limits.baggage_max)}</td>
          </tr>
          <tr>
            <td>Passport</td>
            <td className="money">{money(limits.passport_max)}</td>
          </tr>
          <tr>
            <td>Emergency medical</td>
            <td className="money">{money(limits.emergency_medical_max)}</td>
          </tr>
          <tr>
            <td>Deductible</td>
            <td className="money">{money(limits.deductible)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function CustomerPanel({
  customer,
}: Readonly<{ customer: Customer | undefined }>) {
  if (!customer) return null;
  return (
    <div className="panel">
      <h3>Customer</h3>
      <p>{customer.name}</p>
      <p className="quiet">
        {customer.email} · customer since {customer.customer_since}
      </p>
      <h3>Earlier claims</h3>
      {customer.previous_claims.length === 0 ? (
        <p className="quiet">None.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Filed</th>
              <th>Claim</th>
              <th className="money">Paid</th>
            </tr>
          </thead>
          <tbody>
            {customer.previous_claims.map((earlier) => (
              <tr key={earlier.claim_id}>
                <td className="mono quiet">{earlier.filed_on}</td>
                <td>{earlier.summary}</td>
                <td className="money">{money(earlier.amount_paid)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
