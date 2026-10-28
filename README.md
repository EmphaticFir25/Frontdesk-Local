# Dialtone

AI phone receptionist for local businesses. The LLM runs locally behind an OpenAI-compatible
server (LM Studio by default). Each client is one YAML file.

## Layout

```
businesses/           one YAML config per client (hours, services, facts, escalation rules)
dialtone/
  config.py           loads business YAML
  prompts.py          system prompt, including the voice rules
  tools.py            tool schemas and handlers (availability, booking, messages, transfer)
  scheduling.py       open-slot logic; replace the store lookup with a calendar API later
  store.py            SQLite: call log with transcripts, appointments, messages
  agent.py            the call loop: caller text -> tool calls -> short spoken reply
tests/
  scenarios.yaml      scripted caller conversations with expected behavior
  run_scenarios.py    runs them and reports pass/fail and reply latency
data/                 SQLite databases (gitignored)
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

1. Start LM Studio, load a 27B-class model with tool calling, and start the local server (port 1234).
2. Set the model id LM Studio shows:

```bash
export DIALTONE_MODEL="your-model-id"
python tests/run_scenarios.py
```

## Status

- [x] Config, storage, availability, tools, prompt, call loop
- [x] Scripted scenario harness (text only, no phone yet)
- [ ] Speech-to-text and text-to-speech adapters
- [ ] Telephony (Twilio or Telnyx media stream, with barge-in)
- [ ] Google Calendar or client booking-software integration
- [ ] Call summaries sent to the business by email or text
- [ ] Simple dashboard for call logs

## Design notes

- Replies are capped at 200 tokens and told to be one to three sentences. Length drives both latency and how natural the call sounds.
- The AI only states facts from the business config and takes a message when unsure. It never guesses prices or medical answers.
- Booking re-checks the slot right before saving, because two calls can race for the same time.
- The voice layer is separate from `agent.py`, so you can swap STT and TTS engines without touching the logic.
