# AGENTS.md — CVForge (Root)
 
This file gives coding agents project-wide context. Folder-specific instructions live in `/frontend/AGENTS.md` and `/backend/AGENTS.md` — read this file first, then the relevant subfolder file for the area you're working in.
 
## Project Summary
 
CVForge is a platform where a user builds a structured "Skill Bank" (experiences, projects, skills, education), pastes/uploads a job description, and receives an AI-selected, tailored resume rendered via LaTeX, editable live in-browser. See `/README.md` at the repo root for full architecture, data model, and pipeline documentation before making structural changes.
 
## Repository Layout
 
```
/frontend      # React + TypeScript client (see /frontend/AGENTS.md)
/backend       # FastAPI service + workers (see /backend/AGENTS.md)
/docs          # Architecture notes, ADRs
/README.md     # Full project documentation
```
 
## Global Rules for Agents
 
1. **Never fabricate resume content logic.** Any code touching the rewriting pipeline must preserve the constraint that rewritten bullets cannot introduce technologies, metrics, or claims absent from the source bullet. Do not "helpfully" relax this to make output look better.
2. **Nothing auto-applies to a resume version.** Any AI-generated content (rewritten bullets, selected bullets, inferred skills) must pass through an explicit user-approval step before being persisted into a `resume_versions` row. Do not add code paths that bypass this.
3. **Keep inferred vs. self-reported data distinct.** Skills inferred from GitHub or LeetCode must always carry their `source` field and must never be silently merged into user-authored skill entries.
4. **Long-running work is async.** JD parsing, matching, rewriting, GitHub/LeetCode sync, and LaTeX compilation must run via background workers (Celery/arq), never inline in a request/response cycle.
5. **LaTeX compilation is sandboxed.** Any change to the compilation service must preserve subprocess sandboxing and timeouts — this executes user-editable and AI-generated LaTeX source.
6. **Match the existing stack.** Backend: FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL + pgvector, Celery/arq + Redis, Tectonic. Frontend: React, TypeScript, Vite, Tailwind. Don't introduce a new framework/library for something the existing stack already covers without flagging it first.
7. **Env vars, not hardcoded secrets.** All API keys, DB URLs, and credentials come from environment variables per `.env.example` — never hardcode or commit secrets.
## Before Submitting Changes
 
- Run backend tests: `pytest` (from `/backend`)
- Run backend lint/format: `ruff check .` and `black --check .`
- Run frontend typecheck: `tsc --noEmit` (from `/frontend`)
- Run frontend lint: `npm run lint`
- Update `/README.md` if you change the data model, API routes, or pipeline behavior — it is the source of truth for project architecture.
## Commit Conventions
 
Use Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`). Keep backend and frontend changes in separate commits where practical.