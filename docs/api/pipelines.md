# AI pipelines

Before using embeddings, create two serverless Pinecone indexes. The dense index (`resumeforge-bullets`) uses cosine similarity and a dimension matching the configured BYOK embedding model. The sparse index (`resumeforge-bullets-sparse`) uses vector type `sparse`, dot-product similarity, and no fixed dimension. Set `PINECONE_INDEX_NAME`, `PINECONE_HOST`, `PINECONE_SPARSE_INDEX_NAME`, and the shared `PINECONE_API_KEY`. Reranking uses `OPENROUTER_API_KEY` and `OPENROUTER_RERANK_MODEL=nvidia/llama-nemotron-rerank-vl-1b-v2:free`.

Before using resume import, create a **private** bucket named `resume-imports` at **Supabase Dashboard → Storage → New bucket**, and set `SUPABASE_STORAGE_BUCKET_RESUME_IMPORTS=resume-imports`. Storage schema metadata is not written by Alembic.

## JD parsing

1. The user pastes a JD or uploads a PDF.
2. The API immediately stores a `job_descriptions` row and a `background_jobs` row in PostgreSQL, queues `jd_parse`, and returns both IDs.
3. The worker reads the text, using the private Supabase Storage object when a PDF was uploaded.
4. The worker calls the submitting user's encrypted BYOK completion configuration and validates the response. One correction attempt is allowed. Named technologies are extracted per requirement with `any`/`all` semantics, and every extracted term must occur in the requirement or source JD.
5. In one PostgreSQL transaction it stores parsed JSON, required/nice-to-have requirement rows, their validated technology terms, and action-verb rows, then marks the job done.
6. The UI polls the generic job endpoint and reads the JD detail. Legacy JDs missing newer parsed fields return empty lists instead of failing.

## Embedding and matching

1. Creating or editing a Skill Bank item queues an item-level `embedding` job; creating or editing a bullet queues a bullet-level job. Changing an item also refreshes its existing bullets because their metadata includes the parent type.
2. The CRUD request returns without waiting for the LLM or Pinecone.
3. The worker loads the real PostgreSQL row. Bullet text is embedded directly; item text combines the item's title, tags, and raw text. In parallel it calls the user's configured dense embedding provider and Pinecone's hosted `pinecone-sparse-english-v0` passage encoder, then writes the result to both indexes. A partial failure records which write succeeded and leaves the job failed so the source can be retried.
4. Both indexes store every user's vectors in a namespace named with that user's UUID. Vector IDs equal the source `bullet_points.id` or `skill_bank_items.id`. Metadata uses `level=bullet` or `level=item`; bullet vectors include `bullet_id`, while item vectors omit that key because Pinecone does not support null metadata. Both levels include `item_id` and `item_type`. PostgreSQL remains the source of truth.
5. `POST /api/match/{jd_id}` validates the completed owned JD and runs matching in the API request.
6. The API confirms every owned item and bullet exists in both indexes. Any source missing either vector is ineligible and sets `pending_embeddings=true`.
7. For each requirement, the API creates its BYOK dense embedding and concurrently retrieves up to 25 candidates from each index. Results are merged and deduplicated by `(level, source UUID)`, then the corresponding owned item or bullet text is loaded from PostgreSQL.
8. The unified candidate set is sent to OpenRouter's hosted reranker. If an item-level vector and one of its bullets both qualify for the same requirement, only the higher-scoring level is kept. Candidates below `MIN_RERANK_SCORE=0.0001` are excluded; confidence is `strong >= 0.01` or `moderate >= 0.0001`.
9. The API returns the complete validated `MatchResult`. Provider/vector failures return HTTP 502 and are visible in browser developer tools.
10. Deleting a bullet removes its vectors. Deleting an item removes both its own item-ID vectors and every child bullet vector from both indexes before deleting PostgreSQL content, preventing stale results from resurfacing.

## Resume import

1. The user uploads a PDF or DOCX.
2. The API writes the file to the private Supabase `resume-imports` bucket, creates PostgreSQL staging/job rows, queues `resume_import`, and immediately returns both IDs.
3. The worker checks the user's LLM settings before spending work on extraction, downloads the object, extracts text, and saves that raw text on the staging row.
4. The worker asks the user's completion model for a strict JSON structure. The prompt forbids inference or embellishment, and a server check rejects returned bullets/skills that are not literally present in the extracted text.
5. A valid response is stored only in `resume_imports.parsed_json`. It is review data, not Skill Bank data.
6. The user edits/removes content and submits the final selection to `/commit`.
7. One transaction writes only submitted items and bullets into PostgreSQL with `source=resume_import`, marks the staging row committed, and rejects a second commit. Item and bullet embedding jobs then populate Pinecone asynchronously, including imported skills that have no bullets.

## Bullet rewriting and approval

1. From Match & Review, the user selects evidence and creates a `resume_versions` draft tied to the owned, completed JD. Source `bullet_points` are never updated by this pipeline.
2. Starting a rewrite validates ownership of every selected bullet, moves the version from `draft` to `rewriting`, creates a `background_jobs` row, and returns immediately.
3. The worker batches the immutable originals with the JD's required skills, ATS keywords, extracted action verbs, and the user's tagged skills. The prompt requires full-sentence restructuring and truthful JD-language use while forbidding new facts, tools, employers, scope, or metrics.
4. Before storage, every proposal receives the exact number/metric check plus the independent unsupported-claim/technology verification. Safe proposals below the calibrated 35% word-sequence change threshold are retried once through the same full guardrail path. A still-trivial safe proposal is retained with `low_effort_rewrite=true`; numeric and unsupported factual changes still fall back to the original, while unrecognized technologies remain visible review flags.
5. After every bullet passes through the guardrails, one transaction inserts `resume_bullet_selections` with original/proposed text, structured safety flags, and the informational quality flag, then moves the version to `reviewing`. A provider failure stores no partial selection set and returns the version to `draft` for retry.
6. The review UI always shows original and proposed text side by side. Approval, user editing, and explicit revert are separate persisted decisions. Bulk approval excludes every flagged proposal.
7. Finalization is server-gated: every selection must have `resolved=true`, which only explicit approval or revert sets. The version then moves to `finalized`, ready for Phase 5 LaTeX assembly; `tex_source` remains nullable until that phase.
