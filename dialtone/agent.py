"""The call loop: caller text in, tool calls resolved, short spoken reply out.

Speech-to-text and text-to-speech wrap around this. Keeping this layer text-only lets you
test the logic without a phone."""
import json
import os

from openai import OpenAI

from .config import BusinessConfig
from .prompts import build_system_prompt
from .store import Store
from .tools import TOOL_SCHEMAS, ToolContext, dispatch


def make_client() -> OpenAI:
    """Points at LM Studio by default. Set DIALTONE_BASE_URL to use any OpenAI-compatible server."""
    return OpenAI(
        base_url=os.getenv("DIALTONE_BASE_URL", "http://localhost:1234/v1"),
        api_key=os.getenv("DIALTONE_API_KEY", "lm-studio"),
    )


class CallSession:
    MAX_TOOL_STEPS = 4
    FALLBACK = "Let me take your number and have someone get back to you."

    def __init__(self, cfg: BusinessConfig, store: Store, client: OpenAI,
                 model: str, caller_phone: str):
        self.cfg = cfg
        self.client = client
        self.model = model
        self.ctx = ToolContext(cfg=cfg, store=store, caller_phone=caller_phone)
        self.messages = [{"role": "system", "content": build_system_prompt(cfg)}]
        self.transcript: list[tuple[str, str]] = []
        self.tool_log: list[dict] = []
        self.call_id = store.start_call(cfg.id, caller_phone)

    def say(self, caller_text: str) -> str:
        """Handle one caller turn and return the AI's spoken reply."""
        self.messages.append({"role": "user", "content": caller_text})
        self.transcript.append(("caller", caller_text))

        for _ in range(self.MAX_TOOL_STEPS):
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=TOOL_SCHEMAS,
                temperature=0.6,
                max_tokens=200,   # phone replies should be short; this also caps latency
            )
            msg = resp.choices[0].message

            if msg.tool_calls:
                self.messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name,
                                     "arguments": tc.function.arguments},
                    } for tc in msg.tool_calls],
                })
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments or "{}")
                    result = dispatch(tc.function.name, args, self.ctx)
                    self.tool_log.append({"tool": tc.function.name, "args": args, "result": result})
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    })
                continue

            reply = (msg.content or "").strip() or self.FALLBACK
            self.messages.append({"role": "assistant", "content": reply})
            self.transcript.append(("ai", reply))
            return reply

        self.transcript.append(("ai", self.FALLBACK))
        return self.FALLBACK

    def outcome(self) -> str:
        names = [t["tool"] for t in self.tool_log if t["result"].get("ok")]
        if "book_appointment" in names:
            return "booked"
        if "transfer_to_human" in names:
            return "transferred"
        if "take_message" in names:
            return "message_taken"
        return "answered"

    def end(self) -> str:
        outcome = self.outcome()
        self.ctx.store.end_call(self.call_id, outcome, self.transcript)
        return outcome
