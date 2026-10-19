import type { Step } from "./api";

export function Activity({
  steps,
  working,
}: Readonly<{ steps: Step[] | undefined; working: boolean }>) {
  return (
    <div className="panel">
      <h3>What the agent did</h3>
      {steps && steps.length > 0 ? (
        <ul className="steps">
          {steps.map((step, index) => (
            <li key={`${step.at}-${String(index)}`}>
              <strong>{step.step}</strong>
              <div className="quiet">{step.detail}</div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="quiet">Nothing yet.</p>
      )}
      {working && <p className="quiet">Working.</p>}
    </div>
  );
}
