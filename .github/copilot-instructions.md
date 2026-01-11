# Copilot Instructions for Buyer Request Workflow + Audit Log API

## Project Overview
- **Purpose:** REST API for buyer-factory evidence requests with strict role-based access and immutable audit logging.
- **Stack:** Python 3.8+, FastAPI, SQLite, JWT-like tokens, Uvicorn.

## Architecture & Data Flow
- **Buyers** create requests for evidence from factories. Cannot create or fulfill evidence.
- **Factories** create evidence, add versions, and fulfill requests for their own factory only.
- **Audit Log:** Every action (login, request, evidence, fulfill) is logged immutably.
- **Database:** SQLite file (`workflow.db`) auto-initialized on startup. Tables: `audit_log`, `evidence`, `evidence_versions`, `requests`, `request_items`, `auth_tokens`.

## Key Files
- `main.py`: All API endpoints, models, DB logic, and role enforcement.
- `test_main.py`: Pytest-based test suite. Run with `pytest test_main.py -v`.
- `requirements.txt`: FastAPI, Uvicorn, Pydantic, Python-multipart.
- `README.md`: Full API usage, curl examples, and workflow documentation.

## Developer Workflows
- **Install:** `pip install -r requirements.txt`
- **Run server:** `python main.py` (serves at `http://localhost:8000`)
- **API docs:** Swagger UI at `/docs`
- **Test:** `pytest test_main.py -v` (uses and resets `workflow.db`)
- **DB reset:** Delete `workflow.db` to start fresh.

## Project Conventions
- **ID Generation:** All IDs are prefixed (E, V, R, I) and random.
- **Role Enforcement:** Use `require_role` dependency for endpoint protection.
- **Audit Logging:** Use `log_audit()` for every mutating action.
- **Token Auth:** All endpoints (except login) require `Authorization: Bearer <token>` header.
- **Factory Isolation:** Factories can only access/modify their own data.
- **No migrations:** Schema is created/updated on startup.

## Integration & Extensibility
- **No external services** (self-contained, no email, no cloud, no external auth).
- **Extend endpoints** by following existing Pydantic models and role checks.
- **Add DB fields** by updating `init_db()` and relevant models.

## Examples
- See `README.md` for curl usage and response formats.
- See `test_main.py` for end-to-end test flows.

---
**For AI agents:**
- Always enforce role and factory boundaries.
- Log all state-changing actions.
- Reference `main.py` for all business logic and patterns.
- Use `README.md` for API and workflow details.
