# Backend API (MVP)

FastAPI + SQLite API for owner-controlled products, prospects, orders, payment verification, agent-run records, and audit logs.

## Run locally

```bash
cd sales-agent/backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export OWNER_TOKEN='use-a-long-random-secret'
uvicorn main:app --reload
```

Open `/docs` for the API schema. All `/api/*` routes require `Authorization: Bearer $OWNER_TOKEN`. `/health` is public.

## Deploy
Deploy this folder as a Docker web service on a host that supports persistent disk. Set `OWNER_TOKEN`, `DB_PATH` to a path on that persistent disk, and `ALLOWED_ORIGINS` to the exact dashboard origin. Free hosts may sleep and may not offer persistent storage; confirm provider limits before use.

## Important
- This API does not yet call an LLM, search the web, send outbound messages, or run scheduled agents.
- Payment verification is an owner-only manual action. Verify the actual payment account first; never trust screenshots alone.
- Prospect records require a permission/source note. Only contact people through channels and methods permitted by the platform and applicable law.
- Do not commit real tokens, API keys, passwords, OTPs, or payment credentials.
- SQLite is a starter database, not a high-availability production database. Add backups, authentication hardening, rate limits, monitoring, and PostgreSQL before broad commercial use.
