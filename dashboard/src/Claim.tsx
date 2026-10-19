import { api, claimTypeLabel, money } from "./api";
import { Chip } from "./Chip";
import { useLoad } from "./useLoad";

export function Claim({ claimId }: Readonly<{ claimId: string }>) {
  const { data: claim, error } = useLoad(() => api.claim(claimId), claimId);

  if (error)
    return (
      <p className="error">
        Claim {claimId} could not be loaded. {error}
      </p>
    );
  if (!claim) return <p className="quiet">Loading {claimId}.</p>;

  return (
    <div className="panel">
      <div className="row">
        <h2 className="mono">{claim.claim_id}</h2>
        <Chip status={claim.status} />
        <span className="quiet">
          {claim.customer_name} · {claimTypeLabel(claim.claim_type)} ·{" "}
          {money(claim.amount_claimed)} claimed
        </span>
      </div>
      <p>{claim.summary}</p>
      <p className="quiet mono">
        {claim.incident_date} · {claim.incident_location}
      </p>
      <p>{claim.story}</p>
    </div>
  );
}
