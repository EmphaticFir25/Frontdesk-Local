"""Run scripted caller scenarios against the local LLM and report pass/fail plus latency.

Usage:
    python tests/run_scenarios.py                      # all scenarios
    python tests/run_scenarios.py "booking happy path" # one scenario by name

Environment:
    DIALTONE_MODEL       model id as LM Studio shows it (required)
    DIALTONE_BASE_URL    default http://localhost:1234/v1
"""
import os
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dialtone.agent import CallSession, make_client   # noqa: E402
from dialtone.config import load_business             # noqa: E402
from dialtone.store import Store                      # noqa: E402

DB_PATH = ROOT / "data" / "test.db"


def run_one(scenario: dict, store: Store, client, model: str) -> tuple[bool, list[str], list[float]]:
    cfg = load_business(ROOT / scenario["business"])
    session = CallSession(cfg, store, client, model, scenario["caller_phone"])
    latencies, replies = [], []

    for turn in scenario["turns"]:
        start = time.perf_counter()
        reply = session.say(turn)
        latencies.append(time.perf_counter() - start)
        replies.append(reply)
        print(f"    caller: {turn}")
        print(f"    AI:     {reply}")

    outcome = session.end()
    called = {t["tool"] for t in session.tool_log if t["result"].get("ok")}
    attempted = {t["tool"] for t in session.tool_log}
    failures = []

    for tool in scenario.get("expect_tools", []):
        if tool not in called:
            failures.append(f"expected successful {tool}")
    for tool in scenario.get("forbid_tools", []):
        if tool in attempted:
            failures.append(f"should not call {tool}")
    if "expect_outcome" in scenario and outcome != scenario["expect_outcome"]:
        failures.append(f"outcome was {outcome}, expected {scenario['expect_outcome']}")
    if "reply_contains_any" in scenario:
        joined = " ".join(replies).lower()
        if not any(w.lower() in joined for w in scenario["reply_contains_any"]):
            failures.append("no reply contained the expected wording")

    return not failures, failures, latencies


def main() -> None:
    model = os.getenv("DIALTONE_MODEL")
    if not model:
        sys.exit("Set DIALTONE_MODEL to the model id shown in LM Studio.")

    scenarios = yaml.safe_load((ROOT / "tests" / "scenarios.yaml").read_text())
    if len(sys.argv) > 1:
        scenarios = [s for s in scenarios if s["name"] == sys.argv[1]]

    if DB_PATH.exists():
        DB_PATH.unlink()   # fresh database each run so bookings don't collide
    store = Store(DB_PATH)
    client = make_client()

    passed = 0
    all_latencies = []
    for scenario in scenarios:
        print(f"\n== {scenario['name']}")
        ok, failures, latencies = run_one(scenario, store, client, model)
        all_latencies.extend(latencies)
        passed += ok
        status = "PASS" if ok else "FAIL"
        print(f"  {status}" + ("" if ok else " - " + "; ".join(failures)))
        print(f"  reply latency (s): " + ", ".join(f"{x:.2f}" for x in latencies))

    print(f"\n{passed}/{len(scenarios)} scenarios passed")
    if all_latencies:
        all_latencies.sort()
        p50 = all_latencies[len(all_latencies) // 2]
        print(f"median reply latency: {p50:.2f}s  (phone target: under ~1.5s including STT/TTS)")


if __name__ == "__main__":
    main()
