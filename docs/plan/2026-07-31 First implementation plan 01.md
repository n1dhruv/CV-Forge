# ResumeForge — Implementation Plan

**Auth:** Clerk (Pro plan) &nbsp;|&nbsp; **Database/Storage:** Supabase (Postgres + pgvector + Storage) &nbsp;|&nbsp; **Backend:** FastAPI &nbsp;|&nbsp; **Hosting:** TBD (Railway/Render/Fly.io for backend+workers, Vercel for frontend — decided in Phase 9)

This plan is sequenced so each phase produces something runnable and testable before the next begins. Phase 1 is the one to hand to a coding agent first — it establishes auth, database, and the skill bank, which everything else depends on.

---

## Architecture Decisions (locked in for this build)

- **Supabase is used as a managed Postgres + Storage provider only.** We will *not* use Supabase Auth (Clerk replaces it) and will *not* rely on Supabase's auto-generated REST/GraphQL API — FastAPI talks directly to the Postgres instance via SQLAlchemy (async, `asyncpg`), and to Supabase Storage via its S3-compatible API or the `supabase-py` storage client.
- **Clerk is the sole identity provider.** The frontend uses Clerk's React SDK for sign-in/sign-up/session. The backend verifies Clerk-issued JWTs on every request (via Clerk's JWKS endpoint) rather than managing passwords/sessions itself.
- **A local `users` table mirrors Clerk users** (keyed by `clerk_user_id`), created via a Clerk webhook on `user.created`. All other tables foreign-key to this local `users.id`, not directly to Clerk — this keeps the schema provider-agnostic if auth is ever swapped.
- **pgvector runs inside the same Supabase Postgres instance** (Supabase supports enabling it as an extension) — no separate vector DB needed.
- **Supabase Storage buckets** hold generated resume PDFs and uploaded JD PDFs; the database stores only URLs/paths, never file bytes.

---

## Phase 0 — Accounts & Project Scaffolding

**Goal:** Every external service exists and the repo skeleton is in place.

- [ ] Create Supabase project → note project URL, `anon` key, `service_role` key, direct Postgres connection string (and pooled/transaction-mode string for serverless-style connections if needed)
- [ ] Enable `pgvector` extension in Supabase (SQL editor: `create extension if not exists vector;`)
- [ ] Create two Supabase Storage buckets: `resumes` (private) and `jd-uploads` (private)
- [ ] Create Clerk application (Pro plan) → note publishable key, secret key, JWKS/issuer URL
- [ ] Configure Clerk webhook endpoint (to be built in Phase 1) for `user.created`, `user.updated`, `user.deleted`
- [ ] Set up Redis instance (Upstash for hosted, or local Docker for dev)
- [ ] Initialize repo structure: `/frontend`, `/backend`, root `AGENTS.md` + subfolder `AGENTS.md` files, root `README.md`
- [ ] Create `.env.example` files for both `/frontend` and `/backend` (see Environment Variables section below)

**Output of this phase:** empty FastAPI app that boots, connects to Supabase Postgres, and returns `200` on `/health`.

---

## Phase 1 — Auth, Database Schema & Skill Bank CRUD *(first implementation — see backend prompt below)*

**Goal:** A user can sign up via Clerk, get synced into the local DB, and perform full CRUD on their Skill Bank through authenticated API routes.

- [ ] Alembic migration creating the full schema (see [Database Schema](#database-schema) below)
- [ ] Clerk JWT verification middleware/dependency in FastAPI
- [ ] Clerk webhook handler (`/webhooks/clerk`) that creates/updates/deletes rows in `users` on Clerk events, with signature verification (Svix, which Clerk uses under the hood)
- [ ] `users` CRUD is implicit — no direct create endpoint; rows are created only via webhook
- [ ] Skill Bank endpoints: full CRUD for `skill_bank_items` and their nested `bullet_points`, scoped to the authenticated user (never expose another user's data)
- [ ] Basic Supabase Storage integration: signed upload/download URL generation, tested with a dummy file
- [ ] Unit tests for auth dependency (valid token / expired token / missing token / tampered token) and Skill Bank CRUD (ownership isolation between two test users)

**Output of this phase:** a deployable backend where an authenticated user can create/edit/delete experiences, projects, skills, and bullet points, with data correctly isolated per user.

---

## Phase 2 — JD Parsing Pipeline

- [ ] Async task: accept pasted text or uploaded PDF → extract text (PDF via `pypdf`/`pdfplumber`) → LLM call constrained to strict JSON schema → persist to `job_descriptions` + `jd_requirements`
- [ ] Job-status endpoint for polling (`queued` / `running` / `done` / `failed`)
- [ ] Endpoint to fetch a parsed JD's structured requirements

## Phase 3 — Embedding & Matching Pipeline

- [ ] On create/update of any `bullet_points` or `skill_bank_items` row, enqueue an embedding task → store vector in `embedding` column
- [ ] Matching service: given a `jd_id`, compute hybrid relevance scores (embedding cosine similarity + keyword/fuzzy overlap + recency weighting) across the user's bullet points
- [ ] Endpoint returning ranked/selected bullets per section within a configurable length budget

## Phase 4 — Rewriting Pipeline (with guardrails)

- [ ] LLM rewriting service constrained to rephrasing only (see root `AGENTS.md` rule — no new facts/metrics/tech)
- [ ] Post-generation guardrail check: diff new terms in output against source bullet + user's tagged skills, flag anything unmatched
- [ ] Approval endpoint: user submits `approved_bullet_ids`/edited text; only approved content can be written into a resume version

## Phase 5 — Resume Assembly, LaTeX Compilation & Editor Backend

- [ ] Base LaTeX template(s) checked into the repo
- [ ] Resume assembly service: approved bullets + template → `.tex` source
- [ ] Tectonic compilation service, sandboxed subprocess with timeout, structured error parsing
- [ ] `resume_versions` versioning + rollback endpoints
- [ ] Editor endpoints: fetch/update raw `.tex` source, trigger recompile, return PDF URL (Supabase Storage) or structured errors

## Phase 6 — GitHub & LeetCode Integrations

- [ ] GitHub OAuth connect flow (can piggyback on Clerk's built-in GitHub OAuth if using Clerk social connections, or a separate OAuth flow if repo-level scopes are needed beyond identity)
- [ ] GitHub sync task: pull repos, README, languages → LLM summarization → inferred skills tagged `source: github`
- [ ] LeetCode sync task via the unofficial GraphQL endpoint → topic/difficulty stats, graceful failure handling
- [ ] Integrations status endpoints (last synced, sync-in-progress, sync failed)

## Phase 7 — ATS Compatibility Check

- [ ] Deterministic keyword-coverage service comparing a resume version's rendered text against `jd_requirements.ats_keywords`
- [ ] Endpoint returning matched/missing keywords per resume version

## Phase 8 — Frontend Build

- [ ] Use the separate frontend build prompt (already provided) with the Clerk React SDK wired in for auth
- [ ] All screens: Dashboard, Skill Bank editor, JD input, Match & Review, LaTeX Editor, Integrations, ATS Score panel
- [ ] Frontend attaches Clerk session JWT to every API request

## Phase 9 — Hosting & Deployment

- [ ] Backend + Celery/arq workers deployed to a container host (Railway, Render, or Fly.io) — API and workers as separate services/processes
- [ ] Redis: managed instance (Upstash or provider-native)
- [ ] Frontend deployed to Vercel, with Clerk + API base URL environment variables set
- [ ] Supabase project promoted to a paid tier if needed for connection limits/storage size
- [ ] Set up CI (GitHub Actions): lint + test on PR, deploy on merge to `main`
- [ ] Configure custom domain, HTTPS, CORS allowlist (frontend origin only)

## Phase 10 — Post-Launch Hardening

- [ ] Rate limiting on LLM-calling endpoints (per-user quota)
- [ ] Cost monitoring/alerting on LLM + embedding usage
- [ ] Structured logging + error tracking (Sentry)
- [ ] Backups: confirm Supabase automated backup policy is adequate, or add manual export job for `resume_versions`

---

## Database Schema

Run as an Alembic migration against the Supabase Postgres instance. Written as raw SQL here for clarity; translate to SQLAlchemy models for the actual migration.

```sql
create extension if not exists vector;
create extension if not exists "uuid-ossp";

-- Mirrors Clerk users; created/updated via Clerk webhook only.
create table users (
    id uuid primary key default uuid_generate_v4(),
    clerk_user_id text unique not null,
    email text not null,
    first_name text,
    last_name text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table skill_bank_items (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references users(id) on delete cascade,
    type text not null check (type in ('experience', 'project', 'skill', 'education', 'certification')),
    title text not null,
    org text,
    start_date date,
    end_date date,           -- null = ongoing/present
    raw_text text,
    tags text[] default '{}',
    embedding vector(1536),   -- dimension depends on chosen embedding model
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table bullet_points (
    id uuid primary key default uuid_generate_v4(),
    item_id uuid not null references skill_bank_items(id) on delete cascade,
    text text not null,
    tags text[] default '{}',
    metrics text,
    embedding vector(1536),
    display_order int not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table job_descriptions (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references users(id) on delete cascade,
    raw_text text not null,
    source_file_url text,          -- Supabase Storage path, if uploaded as PDF
    parsed_json jsonb,
    status text not null default 'queued' check (status in ('queued','running','done','failed')),
    created_at timestamptz not null default now()
);

create table jd_requirements (
    id uuid primary key default uuid_generate_v4(),
    jd_id uuid not null references job_descriptions(id) on delete cascade,
    skill text not null,
    importance text not null check (importance in ('required','nice_to_have')),
    category text
);

create table resume_versions (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references users(id) on delete cascade,
    jd_id uuid references job_descriptions(id) on delete set null,
    tex_source text not null,
    pdf_storage_path text,          -- Supabase Storage path
    ats_score numeric,
    parent_version_id uuid references resume_versions(id),  -- for rollback lineage
    created_at timestamptz not null default now()
);

create table resume_bullet_selections (
    id uuid primary key default uuid_generate_v4(),
    resume_version_id uuid not null references resume_versions(id) on delete cascade,
    bullet_point_id uuid not null references bullet_points(id) on delete cascade,
    original_text text not null,
    rewritten_text text,
    approved boolean not null default false,
    section_order int not null default 0
);

create table github_repos (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references users(id) on delete cascade,
    repo_name text not null,
    repo_url text not null,
    languages jsonb,
    readme_summary text,
    inferred_skills text[] default '{}',
    last_synced_at timestamptz,
    created_at timestamptz not null default now()
);

create table leetcode_stats (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references users(id) on delete cascade,
    topic text not null,
    solved_count int not null default 0,
    difficulty_distribution jsonb,
    last_synced_at timestamptz
);

-- Generic async job tracking for polling endpoints (JD parsing, matching,
-- rewriting, sync, compilation)
create table background_jobs (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references users(id) on delete cascade,
    job_type text not null,   -- 'jd_parse' | 'match' | 'rewrite' | 'github_sync' | 'leetcode_sync' | 'compile'
    status text not null default 'queued' check (status in ('queued','running','done','failed')),
    result jsonb,
    error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Indexes
create index on skill_bank_items using ivfflat (embedding vector_cosine_ops);
create index on bullet_points using ivfflat (embedding vector_cosine_ops);
create index on skill_bank_items (user_id);
create index on bullet_points (item_id);
create index on job_descriptions (user_id);
create index on resume_versions (user_id);
create index on background_jobs (user_id, status);
```

**Note on Row Level Security (RLS):** Since the FastAPI backend connects using the Supabase `service_role` key (bypassing RLS by design, with authorization enforced in application code via the Clerk-authenticated `user_id`), RLS policies are not strictly required for this architecture. If you later want defense-in-depth or plan to let the frontend talk to Supabase directly for anything, enable RLS and add `user_id = auth.uid()`-style policies at that time — flag this as a deliberate deferred decision, not an oversight.

---

## Environment Variables

**Backend (`/backend/.env`)**
```
DATABASE_URL=postgresql+asyncpg://...supabase-connection-string...
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_STORAGE_BUCKET_RESUMES=resumes
SUPABASE_STORAGE_BUCKET_JD_UPLOADS=jd-uploads
REDIS_URL=
CLERK_SECRET_KEY=
CLERK_JWKS_URL=
CLERK_WEBHOOK_SIGNING_SECRET=
LLM_API_KEY=
LLM_MODEL=
EMBEDDING_MODEL=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
TECTONIC_BINARY_PATH=
ENVIRONMENT=development
```

**Frontend (`/frontend/.env`)**
```
VITE_CLERK_PUBLISHABLE_KEY=
VITE_API_BASE_URL=http://localhost:8000
```

---

## Sequencing Summary

```
Phase 0  Accounts & scaffolding
Phase 1  Auth (Clerk) + DB schema (Supabase) + Skill Bank CRUD   ◀── build this first
Phase 2  JD parsing pipeline
Phase 3  Embedding + matching pipeline
Phase 4  Rewriting pipeline + guardrails
Phase 5  Resume assembly + LaTeX compilation + editor backend
Phase 6  GitHub + LeetCode integrations
Phase 7  ATS compatibility check
Phase 8  Frontend build
Phase 9  Hosting & deployment
Phase 10 Post-launch hardening
```

Each phase should end with a working, tested increment before the next begins. Phase 1 is the one to hand to a coding agent immediately — see the accompanying backend implementation prompt.