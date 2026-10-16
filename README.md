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
