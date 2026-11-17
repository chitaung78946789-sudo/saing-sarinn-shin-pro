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
- The owner-triggered `/api/agents/execute` endpoint calls the configured LLM to create drafts only. It does not search the web, send outbound messages, or run scheduled agents.
- Payment verification is an owner-only manual action. Verify the actual payment account first; never trust screenshots alone.
- Prospect records require a permission/source note. Only contact people through channels and methods permitted by the platform and applicable law.
- Do not commit real tokens, API keys, passwords, OTPs, or payment credentials.
- SQLite is a starter database, not a high-availability production database. Add backups, authentication hardening, rate limits, monitoring, and PostgreSQL before broad commercial use.


## Owner-triggered AI agent drafts

The backend now includes a draft-only AI adapter in `agent_engine.py`. Configure these as **private environment variables on the backend host**, never in GitHub source files or browser JavaScript:

- `GROQ_API_KEY`: provider API key
- `AI_MODEL`: defaults to `openai/gpt-oss-20b`
- `AI_BASE_URL`: defaults to `https://api.groq.com/openai/v1`

Authenticated owner endpoint: `POST /api/agents/execute`

Example JSON body:

```json
{"agent":"Marketing","task":"Draft a short Burmese product description for an offline shop ledger app. Features: products, stock, sales, credit tracking and JSON backup. Clearly state that it works offline on one device."}
```

The endpoint generates and records a draft only. It does not search for prospects, send messages, publish content, deploy code, verify payments, or deliver products. External actions require a separate approved integration and owner approval. Provider usage may be rate-limited or billed; check the provider's current terms before use.
