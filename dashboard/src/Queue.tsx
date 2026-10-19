import {
  api,
  claimTypeLabel,
  money,
  stateLabels,
  type ClaimStatus,
  type QueueClaim,
} from "./api";
import { Chip } from "./Chip";
import { useLoad } from "./useLoad";

const states: ClaimStatus[] = [
  "waiting",
  "in_progress",
  "awaiting_signoff",
  "decided",
];

export function Queue({ open }: Readonly<{ open: (claimId: string) => void }>) {
  const { data: claims, error } = useLoad(() => api.queue(), "queue");

  if (error)
    return <p className="error">The queue could not be loaded. {error}</p>;
  if (!claims) return <p className="quiet">Loading the queue.</p>;

  return (
    <>
      <div className="counts">
        {states.map((state) => (
          <div className="count" key={state}>
            <span className="n">
              {claims.filter((claim) => claim.status === state).length}
            </span>
            <span className="quiet">{stateLabels[state]}</span>
          </div>
        ))}
      </div>
      <div className="panel">
        <table>
          <caption className="quiet" style={{ captionSide: "bottom" }}>
            {claims.length} claims
          </caption>
          <thead>
            <tr>
              <th>Claim</th>
              <th>Customer</th>
              <th>Type</th>
              <th>Submitted</th>
              <th className="money">Claimed</th>
              <th>State</th>
              <th>Decision</th>
              <th className="money">Payout</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => (
              <Row claim={claim} open={open} key={claim.claim_id} />
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Row({
  claim,
  open,
}: Readonly<{
  claim: QueueClaim;
  open: (claimId: string) => void;
}>) {
  return (
    <tr
      onClick={() => {
        open(claim.claim_id);
      }}
    >
      <td className="mono">
        <a
          href={`#/claims/${claim.claim_id}`}
          onClick={(event) => {
            event.preventDefault();
          }}
        >
          {claim.claim_id}
        </a>
      </td>
      <td>{claim.customer_name}</td>
      <td>{claimTypeLabel(claim.claim_type)}</td>
      <td className="mono quiet">{claim.submitted_on}</td>
      <td className="money">{money(claim.amount_claimed)}</td>
      <td>
        <Chip status={claim.status} />
      </td>
      <td className={claim.decision ? `decision ${claim.decision}` : "quiet"}>
        {claim.decision ?? "—"}
      </td>
      <td className="money">
        {claim.payout === null ? "" : money(claim.payout)}
      </td>
    </tr>
  );
}
