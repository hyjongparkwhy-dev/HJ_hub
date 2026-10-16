# my-hub

Personal data hub. Copy `.env.example` to `.env` and fill it in (never commit `.env`).

## server — read-only MCP server

Lets Claude query personal RichRich (stocks) and apt-leader (apartments) databases.

- Tests: `cd server && ./.venv/Scripts/python.exe -m pytest -q`

## collector — daily news collector

Reads seven news feeds once a day (GitHub Actions, 06:00 KST), keeps new items, embeds them with a local
multilingual model and stores them in the `hub` schema. Logs show counts only.

- Database setup (once): run `collector/sql/001_hub.sql`
- Run locally: `cd collector && ./.venv/Scripts/python.exe -m hub_collect`
- Tests: `cd collector && ./.venv/Scripts/python.exe -m pytest -q` (live tests need `HUB_DATABASE_URL`)
- Actions secret: `HUB_DATABASE_URL`

## briefing — morning news briefing

Ranks the last 48 hours of items against seed interests (`hub_collect/topics.py`), picks a diverse top 10,
summarizes them with one Gemini call (feed text if that fails) and sends one Telegram message with 👍/👎
buttons. Presses are read back with `getUpdates` at 09:00 and 21:00 KST and stored in `hub.feedback`.

- Database setup (once): run `collector/sql/002_brief.sql`
- Preview locally without sending or writing: `cd collector && ./.venv/Scripts/python.exe -m hub_collect.brief --dry-run` (add `--summarize` to spend one Gemini call)
- Buttons show a loading spinner and no confirmation: presses are read later, not answered live
- Actions secrets: `HUB_DATABASE_URL`, `HUB_TELEGRAM_TOKEN`, `HUB_TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`
