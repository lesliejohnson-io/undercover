import { useCallback, useEffect, useState } from "react";
import {
  api,
  claimTypeLabel,
  money,
  type Claim as ClaimRecord,
  type Handler,
} from "./api";
import { Activity } from "./Activity";
import { Chip } from "./Chip";
import { CustomerPanel, Documents, PolicyPanel, Story } from "./ClaimPanels";
import { useLoad } from "./useLoad";

const POLL_MS = 1000;

export function Claim({ claimId }: Readonly<{ claimId: string }>) {
  const [tick, setTick] = useState(0);
  const [problem, setProblem] = useState<{
    claimId: string;
    message: string;
  }>();
  const refresh = useCallback(() => {
    setTick((count) => count + 1);
  }, []);

  const key = `${claimId}:${String(tick)}`;
  const { data: claim, error } = useLoad(() => api.claim(claimId), key);
  const { data: steps } = useLoad(() => api.activity(claimId), key);
  const { data: policy } = useLoad(() => api.policy(claimId), claimId);
  const { data: customer } = useLoad(() => api.customer(claimId), claimId);
  const { data: handlers } = useLoad(() => api.handlers(), "handlers");

  const working = claim?.status === "in_progress";
  // A claim leaves in_progress when the decision lands, but the agent still has
  // the payment to make, so keep polling until an approval inside the limit is paid.
  const settling =
    claim?.status === "decided" &&
    claim.decision?.decision === "approve" &&
    !claim.decision.paid_at;
  useEffect(() => {
    if (!working && !settling) return;
    const timer = setInterval(refresh, POLL_MS);
    return () => {
      clearInterval(timer);
    };
  }, [working, settling, refresh]);

  const act = (action: Promise<unknown>) => {
    setProblem(undefined);
    action.then(refresh).catch((cause: unknown) => {
      const message =
        cause instanceof Error ? cause.message : "That did not work.";
      setProblem({ claimId, message });
    });
  };

  if (error)
    return (
      <p className="error">
        Claim {claimId} could not be loaded. {error}
      </p>
    );
  if (!claim) return <p className="quiet">Loading {claimId}.</p>;

  const decision = claim.decision;
  const needsSignOff =
    claim.status === "awaiting_signoff" && !decision?.signed_off_at;

  return (
    <>
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
          {claim.incident_date} · {claim.incident_location} · filed{" "}
          {claim.submitted_on}
        </p>
        <Actions
          claim={claim}
          handlers={handlers}
          working={working}
          needsSignOff={needsSignOff}
          act={act}
        />
      </div>

      {problem?.claimId === claimId && (
        <p className="notice">{problem.message}</p>
      )}
      {needsSignOff && decision && (
        <p className="notice">
          {money(decision.payout)} is over the approval limit. The payment waits
          for a handler&apos;s sign-off.
        </p>
      )}

      <Decision claim={claim} handlers={handlers} />
      <div className="columns">
        <div>
          <Story claim={claim} />
          <Documents claim={claim} />
        </div>
        <div>
          <Activity steps={steps} working={working} />
          <PolicyPanel policy={policy} />
          <CustomerPanel customer={customer} />
        </div>
      </div>
    </>
  );
}

function Decision({
  claim,
  handlers,
}: Readonly<{ claim: ClaimRecord; handlers: Handler[] | undefined }>) {
  const decision = claim.decision;
  if (!decision)
    return (
      <div className="panel">
        <h3>Decision</h3>
        <p className="quiet">The agent has not decided this claim yet.</p>
      </div>
    );

  return (
    <div className="panel">
      <h3>Decision</h3>
      <div className="row">
        <span className={`decision ${decision.decision}`}>
          {decision.decision}
        </span>
        <span className="mono">{money(decision.payout)}</span>
        <span className="quiet">{decision.policy_section}</span>
      </div>
      <p>{decision.reason}</p>
      <p className="quiet">
        {decision.signed_off_by
          ? `Signed off by ${nameOf(handlers, decision.signed_off_by)}. `
          : ""}
        {decision.paid_at
          ? `Paid ${money(decision.paid_amount ?? 0)}.`
          : "Not paid."}
      </p>
    </div>
  );
}

function SignOff({
  handlers,
  onSignOff,
}: Readonly<{
  handlers: Handler[] | undefined;
  onSignOff: (handlerId: string) => void;
}>) {
  const [handlerId, setHandlerId] = useState("");

  return (
    <>
      <select
        aria-label="Handler"
        value={handlerId}
        onChange={(event) => {
          setHandlerId(event.target.value);
        }}
      >
        <option value="">Choose a handler</option>
        {handlers?.map((handler) => (
          <option value={handler.handler_id} key={handler.handler_id}>
            {handler.name}
          </option>
        ))}
      </select>
      <button
        type="button"
        className="quiet"
        disabled={!handlerId}
        onClick={() => {
          onSignOff(handlerId);
        }}
      >
        Sign off
      </button>
    </>
  );
}

function Actions({
  claim,
  handlers,
  working,
  needsSignOff,
  act,
}: Readonly<{
  claim: ClaimRecord;
  handlers: Handler[] | undefined;
  working: boolean;
  needsSignOff: boolean;
  act: (action: Promise<unknown>) => void;
}>) {
  const decision = claim.decision;
  const payable =
    decision?.decision === "approve" && !decision.paid_at && !needsSignOff
      ? decision
      : null;

  return (
    <div className="row">
      <button
        type="button"
        onClick={() => {
          act(api.run(claim.claim_id));
        }}
        disabled={working}
      >
        {working ? "Working" : "Run the agent"}
      </button>
      {needsSignOff && (
        <SignOff
          handlers={handlers}
          onSignOff={(handlerId) => {
            act(api.signOff(claim.claim_id, handlerId));
          }}
        />
      )}
      {payable && (
        <button
          type="button"
          className="quiet"
          onClick={() => {
            act(api.pay(claim.claim_id, payable.payout));
          }}
        >
          Pay {money(payable.payout)}
        </button>
      )}
    </div>
  );
}

function nameOf(handlers: Handler[] | undefined, handlerId: string): string {
  return (
    handlers?.find((handler) => handler.handler_id === handlerId)?.name ??
    handlerId
  );
}
