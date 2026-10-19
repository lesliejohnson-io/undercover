import "./brand.css";
import { Claim } from "./Claim";
import { Instructions } from "./Instructions";
import { Queue } from "./Queue";
import { go, useRoute } from "./route";

export function App() {
  const route = useRoute();

  return (
    <div className="page">
      <header className="masthead">
        <h1>UnderCover Claims</h1>
        <nav>
          <a href="#/">Queue</a>
          <a href="#/instructions">Agent instructions</a>
        </nav>
      </header>
      <p className="tagline">
        The claims queue, worked by the UnderCover Agent.
      </p>
      {route.page === "claim" && <Claim claimId={route.claimId} />}
      {route.page === "instructions" && <Instructions />}
      {route.page === "queue" && (
        <Queue
          open={(claimId) => {
            go(`#/claims/${claimId}`);
          }}
        />
      )}
    </div>
  );
}
