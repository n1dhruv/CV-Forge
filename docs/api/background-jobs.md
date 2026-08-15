# Background jobs

## `jd_parse`

Triggered by `POST /api/jd/parse`. The worker marks both rows running, downloads/extracts an uploaded PDF when needed, calls the user's completion provider or the NVIDIA fallback, validates the complete JSON schema with one retry, and writes `job_descriptions.parsed_json`, `jd_requirements`, and deduplicated `jd_action_verbs` in one transaction. Success marks both rows done and records counts. Unreadable PDFs, provider errors, or two invalid responses mark both rows failed with a safe actionable message. Old successful rows without action verbs remain valid and read back with an empty list.

## `embedding`

Triggered after an item or bullet is created/updated, after a resume import commit, and by the Skill Bank's account-wide re-embed action. Bullet jobs embed `bullet_points.text` under `bullet_points.id`; item jobs combine `skill_bank_items.title`, tags, and raw text under `skill_bank_items.id`, so a bare skill such as Kafka is matchable without a child bullet. Item vectors remain when bullets are later added. Each worker independently writes a 2048-dimension NVIDIA Nemotron 3 Embed 1B dense vector and a Pinecone `pinecone-sparse-english-v0` passage vector in namespace `user_id`. Metadata distinguishes `level=bullet` from `level=item`; item metadata omits `bullet_id` because Pinecone rejects null metadata values. Both levels carry `user_id`, `item_id`, and `item_type`. The job result records `dense_stored` and `sparse_stored`; a partial failure remains retryable. No embedding column is written in PostgreSQL.

## `match`

Triggered by `POST /api/match/{jd_id}`. The API only verifies ownership/completion, inserts the queued job, and enqueues `match_jd_task`. The worker performs readiness checks, one dense embedding plus dense/sparse retrieval and reranking per JD requirement, then stores the complete validated match response in `background_jobs.result` and marks the job done. The client receives updates through the shared Supabase Realtime job channel and uses the generic job endpoint as fallback. Missing configuration and embedding/Pinecone failures mark the job failed with a safe actionable error; they do not hold open or fail the original HTTP request.

## `resume_import`

Triggered by `POST /api/resume_imports`. The worker downloads from the private `resume-imports` bucket, extracts PDF text with pdfplumber/pypdf or DOCX text with python-docx, and stores `resume_imports.raw_text`. It prompts the user's completion model or the NVIDIA fallback for literal-only structured extraction, validates with one retry, and rejects bullets/skills not present in the source. Success writes only `resume_imports.parsed_json` and marks the staging/job rows done. Failures mark both rows failed. No Skill Bank row is created until the user calls `/commit`.

## `rewrite`

Triggered by `POST /api/resume_versions/{version_id}/rewrite`. The worker loads only owned bullets plus required JD skills, ATS keywords, extracted action verbs, and the user's tags, then calls the user's BYOK completion model outside a database transaction. Rewrites and independent verification are batched. Each proposal receives exact number/metric and unsupported-claim/technology checks; a safe proposal below the 35% change threshold is retried once and, if still trivial, stored with `low_effort_rewrite=true`. Numeric or unsupported factual changes fall back to the original; unrecognized named technologies remain visible review flags. Success writes the complete selection set atomically, moves the version to `reviewing`, and marks the job done. A provider or validation failure writes no partial selections, marks the job failed, and returns the version to `draft`.
