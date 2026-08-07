# Background jobs

## `jd_parse`

Triggered by `POST /api/jd/parse`. The worker first verifies LLM settings, marks both rows running, downloads/extracts an uploaded PDF when needed, calls the user's completion provider, validates the complete JSON schema with one retry, and writes `job_descriptions.parsed_json`, `jd_requirements`, and deduplicated `jd_action_verbs` in one transaction. Success marks both rows done and records counts. Missing configuration, unreadable PDFs, provider errors, or two invalid responses mark both rows failed with a safe actionable message. Old successful rows without action verbs remain valid and read back with an empty list.

## `embedding`

Triggered after a bullet is created/updated, after an item's existing bullets need metadata refresh, or after a resume import commit. The worker loads the bullet through an owned parent, calls `llm_client.get_embedding`, then upserts the vector under ID `bullet_points.id` into Pinecone namespace `user_id` with `user_id`, `bullet_id`, `item_id`, and `item_type` metadata. It never writes an embedding column in PostgreSQL. Missing or unsupported embedding configuration is an expected failed-job state; provider/Pinecone errors are normalized and do not crash the worker.

## `resume_import`

Triggered by `POST /api/resume_imports`. The worker verifies LLM configuration before extraction, downloads from the private `resume-imports` bucket, extracts PDF text with pdfplumber/pypdf or DOCX text with python-docx, and stores `resume_imports.raw_text`. It prompts for literal-only structured extraction, validates with one retry, and rejects bullets/skills not present in the source. Success writes only `resume_imports.parsed_json` and marks the staging/job rows done. Failures mark both rows failed. No Skill Bank row is created until the user calls `/commit`.
