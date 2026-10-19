"""The UnderCover Agent."""

import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
TASK = "Work claim {claim_id}, record your decision and pay it if you approve it."
REFUSED = 409


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=60)


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def instructions() -> str:
    """Read the agent's instructions from the backend."""
    with backend() as client:
        response = client.get("/api/instructions")
    response.raise_for_status()
    return response.text


def read(path: str) -> str:
    """Read one of the backend's documents or records as text."""
    with backend() as client:
        response = client.get(path)
    response.raise_for_status()
    return response.text


def write(claim_id: str, path: str, body: dict[str, Any]) -> tuple[bool, str]:
    """Post to a claim, saying whether the backend allowed it and what it said."""
    with backend() as client:
        response = client.post(f"/api/claims/{claim_id}{path}", json=body)
    if response.status_code == REFUSED:
        return False, response.json()["detail"]
    response.raise_for_status()
    return True, response.text


def tools_for(claim_id: str) -> list[BaseTool]:
    """Build the agent's tools, each bound to the one claim it is working."""

    def step(name: str, detail: str) -> None:
        write(claim_id, "/activity", {"step": name, "detail": detail})

    @tool
    def read_claim() -> str:
        """Read the claim: the story, the items claimed and the documents."""
        claim = read(f"/api/claims/{claim_id}")
        step("Read the claim", json.loads(claim)["summary"])
        return claim

    @tool
    def read_policy() -> str:
        """Read the policy behind the claim, with its plan's limits and add-ons."""
        policy = read(f"/api/claims/{claim_id}/policy")
        trip = json.loads(policy)["trip"]
        step(
            "Read the policy",
            f"{json.loads(policy)['plan']} plan, "
            f"{trip['departs_on']} to {trip['returns_on']}",
        )
        return policy

    @tool
    def read_customer() -> str:
        """Read the customer who made the claim, with their claim history."""
        customer = read(f"/api/claims/{claim_id}/customer")
        earlier = len(json.loads(customer)["previous_claims"])
        step("Read the customer", f"{earlier} earlier claims")
        return customer

    @tool
    def read_policy_wording() -> str:
        """Read the policy wording, the contract that settles the decision."""
        wording = read("/api/policy-wording")
        step("Read the policy wording", "The contract with the customer")
        return wording

    @tool
    def record_decision(
        decision: str, payout: float, reason: str, policy_section: str
    ) -> str:
        """Record the decision: approve, decline or refer, and its payout."""
        allowed, detail = write(
            claim_id,
            "/decision",
            {
                "decision": decision,
                "payout": payout,
                "reason": reason,
                "policy_section": policy_section,
            },
        )
        if not allowed:
            return f"Refused. {detail}"
        return f"Recorded {decision} with a payout of ${payout:,.2f}."

    @tool
    def pay_claim(amount: float) -> str:
        """Pay the claim the payout you recorded."""
        allowed, detail = write(claim_id, "/payment", {"amount": amount})
        if not allowed:
            return f"Refused. {detail}"
        return f"Paid ${amount:,.2f}."

    return [
        read_claim,
        read_policy,
        read_customer,
        read_policy_wording,
        record_decision,
        pay_claim,
    ]


def work(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Work a claim the backend has already handed to the agent."""
    agent = create_agent(
        llm or model(), tools=tools_for(claim_id), system_prompt=instructions()
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": TASK.format(claim_id=claim_id)}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].text


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Hand one claim to the agent, work it and return its final reply."""
    with backend() as client:
        client.post(f"/api/claims/{claim_id}/start").raise_for_status()
    return work(claim_id, thread_id, llm)
