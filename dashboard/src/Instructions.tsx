import { api } from "./api";
import { useLoad } from "./useLoad";

export function Instructions() {
  const { data: text, error } = useLoad(
    () => api.instructions(),
    "instructions",
  );

  if (error)
    return (
      <p className="error">The instructions could not be loaded. {error}</p>
    );
  if (text === undefined)
    return <p className="quiet">Loading the instructions.</p>;

  return (
    <div className="panel">
      <h2>The agent&apos;s instructions</h2>
      <p className="quiet">Read only. This is the text the agent runs on.</p>
      <pre className="instructions">{text}</pre>
    </div>
  );
}
