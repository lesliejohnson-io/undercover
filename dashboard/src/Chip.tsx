import { stateLabels, type ClaimStatus } from "./api";

export function Chip({ status }: Readonly<{ status: ClaimStatus }>) {
  return <span className={`chip ${status}`}>{stateLabels[status]}</span>;
}
