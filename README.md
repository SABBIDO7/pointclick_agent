# Point&Click Mini Computer‑Use Agent

Minimal Claude‑style agent that pilots a Chrome Extension via a localhost WebSocket bridge.

## ✨ What it does
- Takes a natural language task (e.g., “Open Gmail and list promo emails I’ve not opened in 3 months”).
- Runs an Agent loop (Claude w/ Tools) that invokes browser actions (navigate, wait, query, click, type…).
- The Chrome extension performs those actions safely in the active tab and returns observations.

## 🧩 Architecture
- **Extension (MV3)** exposes a narrow set of DOM tools via `content.js` and tab/Download tools via `background.js`.
- **Python** runs a WebSocket server and an **Orchestrator** using Anthropic Claude Tools.
- Messages are JSON RPCs: `{type, id, method, params}` with structured results.

## ⚙️ Setup
1. **Clone** this repo.
2. **Python deps**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   cd client
   pip install -r requirements.txt
   cp .env.example .env # and set ANTHROPIC_API_KEY