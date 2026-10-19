import json

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend.main import app


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def call(name: str, args: dict, step: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": step}])


APPROVE = {
    "decision": "approve",
    "payout": 420.0,
    "reason": "A six hour delay on a Premium plan, with the costs receipted.",
    "policy_section": "Section 3",
}


def stub(*replies: AIMessage) -> StubModel:
    return StubModel(messages=iter(replies))


def test_a_scripted_approval_is_decided_and_paid(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    reply = main.run(
        "CLM-1001",
        "thread-1",
        stub(
            call("read_claim", {}, "1"),
            call("read_policy", {}, "2"),
            call("read_policy_wording", {}, "3"),
            call("record_decision", APPROVE, "4"),
            call("pay_claim", {"amount": 420.0}, "5"),
            AIMessage(content="Approved and paid $420.00 under section 3."),
        ),
    )
    assert reply == "Approved and paid $420.00 under section 3."

    client = TestClient(app)
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["payout"] == 420.0
    assert claim["decision"]["paid_amount"] == 420.0
    assert claim["decision"]["policy_section"] == "Section 3"

    steps = [
        step["step"] for step in client.get("/api/claims/CLM-1001/activity").json()
    ]
    assert steps == [
        "Started",
        "Read the claim",
        "Read the policy",
        "Read the policy wording",
        "Decision",
        "Paid",
    ]


def test_the_agents_own_payment_over_the_limit_is_refused(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    reply = main.run(
        "CLM-1001",
        "thread-2",
        stub(
            call("read_claim", {}, "1"),
            call("record_decision", APPROVE | {"payout": 2400.0}, "2"),
            call("pay_claim", {"amount": 2400.0}, "3"),
            AIMessage(content="Approved $2,400.00. It waits for a handler's sign-off."),
        ),
    )
    assert "sign-off" in reply

    client = TestClient(app)
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "awaiting_signoff"
    assert claim["decision"]["paid_at"] is None

    activity = client.get("/api/claims/CLM-1001/activity").json()
    blocked = [step for step in activity if step["step"] == "Payment blocked"]
    assert len(blocked) == 1
    assert "needs a handler's sign-off" in blocked[0]["detail"]


def test_a_scripted_referral_is_decided_with_no_payout(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    referral = {
        "decision": "refer",
        "payout": 0.0,
        "reason": "The police report the wording asks for is missing.",
        "policy_section": "Section 5",
    }
    main.run(
        "CLM-1003",
        "thread-3",
        stub(
            call("read_claim", {}, "1"),
            call("read_customer", {}, "2"),
            call("record_decision", referral, "3"),
            AIMessage(content="Referred."),
        ),
    )
    claim = TestClient(app).get("/api/claims/CLM-1003").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["decision"] == "refer"
    assert claim["decision"]["payout"] == 0.0


def test_a_refused_decision_comes_back_to_the_agent(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    tools = {tool.name: tool for tool in main.tools_for("CLM-1001")}
    assert (
        tools["record_decision"]
        .invoke(APPROVE | {"payout": 0.0})
        .startswith("Refused.")
    )
    assert "no decision yet" in tools["pay_claim"].invoke({"amount": 10.0})


def test_the_tools_are_bound_to_one_claim(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    tools = {tool.name: tool for tool in main.tools_for("CLM-1002")}
    assert tools["read_claim"].args == {}
    assert tools["read_policy"].args == {}
    assert tools["read_customer"].args == {}
    assert json.loads(tools["read_claim"].invoke({}))["claim_id"] == "CLM-1002"
    assert json.loads(tools["read_policy"].invoke({}))["policy_id"] == "POL-2002"
    assert json.loads(tools["read_customer"].invoke({}))["customer_id"] == "CUS-3002"
    assert "## 10. How we work out your payment" in tools["read_policy_wording"].invoke(
        {}
    )


def test_the_instructions_reach_the_agent_as_its_system_prompt(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    seen = {}

    class FakeAgent:
        def invoke(self, state, config):
            seen["task"] = state["messages"][0]["content"]
            seen["thread"] = config["configurable"]["thread_id"]
            return {"messages": [AIMessage(content="done")]}

    def fake_create_agent(llm, tools, system_prompt):
        seen["prompt"] = system_prompt
        seen["tools"] = [tool.name for tool in tools]
        return FakeAgent()

    monkeypatch.setattr(main, "create_agent", fake_create_agent)
    assert main.work("CLM-1001", "thread-4") == "done"
    assert seen["prompt"] == TestClient(app).get("/api/instructions").text
    assert "You are the UnderCover Agent" in seen["prompt"]
    assert "Refer rather than guess" in seen["prompt"]
    assert seen["tools"] == [
        "read_claim",
        "read_policy",
        "read_customer",
        "read_policy_wording",
        "record_decision",
        "pay_claim",
    ]
    assert (
        seen["task"]
        == "Work claim CLM-1001, record your decision and pay it if you approve it."
    )
    assert seen["thread"] == "thread-4"


def test_the_backend_starts_a_run_and_returns_before_it_finishes(monkeypatch):
    worked = []
    monkeypatch.setattr(
        "backend.main.work", lambda claim_id, thread_id: worked.append(claim_id)
    )
    with TestClient(app) as client:
        claim = client.post("/api/claims/CLM-1004/run").json()
        assert claim["status"] == "in_progress"
        assert claim["decision"] is None
    assert worked == ["CLM-1004"]


def test_the_model_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
