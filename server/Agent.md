# AGENTS.md — /backend
 
Read `/AGENTS.md` (root) first for project-wide rules. This file covers backend-specific conventions.
 
## Stack
 
- FastAPI (Python 3.11+)
- SQLAlchemy 2.x (async) + Alembic for migrations
- PostgreSQL 15+ with the `pgvector` extension
- Celery or `arq` for background task workers, Redis as broker/backend
- Tectonic for sandboxed LaTeX compilation
- Pydantic v2 for request/response schemas
## Folder Structure
 
```
/backend
  /app
    /api
      /skill_bank
      /jd
      /match
      /rewrite
      /integrations
        /github
        /leetcode
      /resume
      /editor
    /services
      jd_parser.py
      matcher.py
      rewriter.py
      github_sync.py
      leetcode_sync.py
      latex_compiler.py
    /workers            # Celery/arq task definitions
    /models              # SQLAlchemy models
    /schemas              # Pydantic request/response schemas
    /db
      session.py
      migrations/          # Alembic migrations
    /core
      config.py
      security.py
    main.py
  requirements.txt
  alembic.ini
```
 
## Conventions
 
1. **Routers are thin.** API route handlers in `/app/api` validate input/output via Pydantic schemas and call into `/app/services` — they should not contain business logic themselves.
2. **Services are pure and testable.** Each file in `/app/services` should be independently unit-testable with mocked external dependencies (LLM client, GitHub API, Tectonic subprocess).
3. **Anything calling an LLM, GitHub, LeetCode, or Tectonic must be dispatched as a background task**, not run synchronously inside a request handler. Return a job ID immediately; expose a status endpoint for polling.
4. **Rewriting pipeline constraints are non-negotiable.** `rewriter.py` must enforce, both in the prompt and via a post-generation check, that no technology/metric/claim appears in the output that isn't present in the source bullet or the user's tagged skills. Any modification to this file needs a corresponding test asserting the constraint still holds.
5. **Approval gating is enforced server-side, not just in the UI.** `resume_versions` rows are only created/updated through an endpoint that requires an explicit `approved_bullet_ids` (or equivalent) payload — never by directly persisting raw pipeline output.
6. **Source tagging is mandatory.** Any skill or bullet written to the DB from `github_sync.py` or `leetcode_sync.py` must set `source` accordingly. Do not write inferred data into fields shared with self-reported entries without the tag.
7. **LaTeX compilation safety.** `latex_compiler.py` must always run Tectonic in a subprocess with a hard timeout and restricted filesystem/network access. Do not change this to shell out unsandboxed, even for debugging convenience — revert debug changes before committing.
8. **Migrations required for all schema changes.** Any model change in `/app/models` needs a matching Alembic migration in the same PR — do not rely on `create_all` outside of test fixtures.
9. **Config via environment variables only**, loaded through `/app/core/config.py` (e.g., a Pydantic `Settings` class). No hardcoded credentials or URLs.
## Testing
 
- Unit tests: matching/ranking logic, JD parsing schema validation, ATS scoring, rewriting guardrail checks — all with mocked LLM responses.
- Integration tests: full pipeline against a test database, with a mocked LLM client and a mocked Tectonic compile step (do not shell out to a real compiler in CI unless explicitly testing the compiler integration itself).
- Run: `pytest --cov=app --cov-report=term-missing`
## Before Submitting Changes
 
- `pytest`
- `ruff check .`
- `black --check .`
- `alembic upgrade head` runs cleanly against a fresh test database if migrations were added/changed
 
