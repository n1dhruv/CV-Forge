# REST endpoints

All `/api` endpoints require a Supabase Auth bearer token except where noted. Owned resources return `404` when the resource does not exist or belongs to another user.

### GET /health
**Auth required:** no  
**Description:** Reports API process health.  
**Request:** None.  
**Response:** `{"status":"ok"}`.  
**Errors:** Startup fails before this route is served if PostgreSQL or Redis is unavailable.

### GET /api/skill_bank/items
**Auth required:** yes  
**Description:** Lists the current user's Skill Bank items.  
**Request:** Optional `type` query parameter.  
**Response:** Item summaries including `source`.  
**Errors:** `401` for invalid authentication; `422` for an invalid type.

### POST /api/skill_bank/items
**Auth required:** yes  
**Description:** Creates a manual Skill Bank item and queues its item-level embedding, even when it has no bullets.  
**Request:** JSON item type, title, optional organization/dates/raw text/tags.  
**Response:** `201` with the created item.  
**Errors:** `401`; `422` for invalid fields.

### GET /api/skill_bank/items/{item_id}
**Auth required:** yes  
**Description:** Returns one owned item and its bullets.  
**Request:** Item UUID in the path.  
**Response:** Item detail.  
**Errors:** `404` if not owned/found.

### PUT /api/skill_bank/items/{item_id}
**Auth required:** yes  
**Description:** Updates an owned item and queues its item-level embedding plus fresh embeddings for existing bullets.  
**Request:** Partial item JSON.  
**Response:** Updated item.  
**Errors:** `404`; `422` for invalid fields.

### DELETE /api/skill_bank/items/{item_id}
**Auth required:** yes  
**Description:** Deletes an item, its PostgreSQL bullets, its own item-ID vectors, and every child vector tagged with the item ID in the user's namespace.  
**Request:** Item UUID.  
**Response:** `204`.  
**Errors:** `404`; external vector-store errors prevent the PostgreSQL delete so stale vectors are not left behind.

### POST /api/skill_bank/items/{item_id}/bullets
**Auth required:** yes  
**Description:** Creates a bullet and queues an `embedding` job.  
**Request:** JSON text, tags, metrics, and display order.  
**Response:** `201` with the bullet.  
**Errors:** `404` for a foreign/missing item; `422` for invalid fields.

### PUT /api/skill_bank/bullets/{bullet_id}
**Auth required:** yes  
**Description:** Updates an owned bullet and queues replacement of its Pinecone vector.  
**Request:** Partial bullet JSON.  
**Response:** Updated bullet.  
**Errors:** `404`; `422`.

### DELETE /api/skill_bank/bullets/{bullet_id}
**Auth required:** yes  
**Description:** Deletes the vector from the user's Pinecone namespace, then deletes the PostgreSQL bullet.  
**Request:** Bullet UUID.  
**Response:** `204`.  
**Errors:** `404`; external vector-store errors prevent the PostgreSQL delete.

### POST /api/skill_bank/items/reembed
**Auth required:** yes  
**Description:** Queues fresh dense and sparse embeddings for every Skill Bank item and bullet owned by the current user. Stable vector IDs make retries overwrite-safe.  
**Request:** None.  
**Response:** `202` with `{items_queued, bullets_queued, failed}`. Counts report actual queue results.  
**Errors:** `401`; queue failures are recorded on the generated background jobs.

### GET /api/settings/llm/supported-models
**Auth required:** no  
**Description:** Lists completion models shown by the settings UI.  
**Request:** None.  
**Response:** Provider-to-model mapping.  
**Errors:** None under normal operation.

### POST /api/settings/llm
**Auth required:** yes  
**Description:** Encrypts and saves the optional user completion configuration.  
**Request:** `provider`, `model`, and `api_key` for initial setup. On later updates, omit the API key to preserve its existing encrypted value.  
**Response:** Saved provider/model names; never returns keys.  
**Errors:** `422` when the initial API key is missing.

### GET /api/settings/llm
**Auth required:** yes  
**Description:** Returns completion provider/model names and the masked key.  
**Request:** None.  
**Response:** Completion provider/model and masked secret.  
**Errors:** `404` when not configured.

### DELETE /api/settings/llm
**Auth required:** yes  
**Description:** Deletes the current user's encrypted LLM settings.  
**Request:** None.  
**Response:** `204`.  
**Errors:** `404` when not configured.

### POST /api/settings/llm/test
**Auth required:** yes  
**Description:** Sends a minimal completion request through the current user's provider without using the server fallback.  
**Request:** None.  
**Response:** `{success, error}` with provider-independent safe errors.  
**Errors:** Provider failures are represented in the response.

### POST /api/jd/parse
**Auth required:** yes  
**Description:** Stages pasted JD text or a PDF and queues `jd_parse`.  
**Request:** JSON `raw_text`, or multipart `file` containing a PDF up to 10 MB.  
**Response:** `202` with `job_description_id` and `background_job_id`.  
**Errors:** `415` wrong request encoding; `422` invalid/missing input; `413` oversized PDF; `502` upload failure; `503` queue failure.

### GET /api/jd
**Auth required:** yes  
**Description:** Lists the current user's JD submissions.  
**Request:** None.  
**Response:** IDs, excerpts, statuses, and creation dates.  
**Errors:** `401`.

### GET /api/jd/{jd_id}
**Auth required:** yes  
**Description:** Returns parse status, structured JSON, requirements, validated named technologies, their `any`/`all` matching mode, and `action_verbs`. Older parses return empty lists for missing fields.
**Request:** JD UUID.  
**Response:** JD detail; `action_verbs` exists both in parsed JSON and as the top-level structured list.  
**Errors:** `404` if not owned/found.

### POST /api/match/{jd_id}
**Auth required:** yes  
**Description:** Matches an owned, completed JD synchronously in the API request.  
**Request:** JD UUID.  
**Response:** `200` with the completed grouped `MatchResult`.
**Errors:** `404` for a foreign, missing, or incomplete JD; `502` for embedding, Pinecone, or OpenRouter failures.

### GET /api/background_jobs/{job_id}
**Auth required:** yes  
**Description:** Polls any owned background job.  
**Request:** Job UUID.  
**Response:** `status`, optional `result`, and safe `error`.  
**Errors:** `404` if not owned/found.

### POST /api/resume_imports
**Auth required:** yes  
**Description:** Uploads a PDF or DOCX into the private `resume-imports` bucket, creates staging/job rows, and queues parsing.  
**Request:** Multipart `file`, PDF or DOCX, up to 10 MB.  
**Response:** `202` with `resume_import_id` and `background_job_id`.  
**Errors:** `400` missing/unsupported file; `413` oversized file; `502` upload failure; `503` queue failure.

### GET /api/resume_imports
**Auth required:** yes  
**Description:** Lists the current user's staged imports.  
**Request:** None.  
**Response:** IDs, excerpts, statuses, and dates.  
**Errors:** `401`.

### GET /api/resume_imports/{resume_import_id}
**Auth required:** yes  
**Description:** Returns staging status and validated `parsed_json` when done.  
**Request:** Import UUID.  
**Response:** Import detail including `committed_at`.  
**Errors:** `404` if not owned/found.

### POST /api/resume_imports/{resume_import_id}/commit
**Auth required:** yes  
**Description:** Writes only the user's final submitted items, bullets, and skills into the Skill Bank with `source=resume_import`, then queues item and bullet embeddings.  
**Request:** JSON `items` and `skills`; omitted entries are not written, and at least one selection is required.  
**Response:** Created item details.  
**Errors:** `404` foreign/missing import; `409` not ready or already committed; `422` invalid fields.

### POST /api/resume_versions
**Auth required:** yes  
**Description:** Creates an owned draft resume version for a completed JD. The version has no LaTeX source yet.  
**Request:** JSON `jd_id`.  
**Response:** `201` with the version ID, JD ID, and `status=draft`.  
**Errors:** `404` if the completed JD is missing or belongs to another user.

### POST /api/resume_versions/{version_id}/rewrite
**Auth required:** yes  
**Description:** Validates the selected owned bullets, moves the draft to `rewriting`, and queues the safety-checked rewrite job.  
**Request:** JSON `bullet_point_ids` with 1–50 unique UUIDs.  
**Response:** `202` with `resume_version_id` and `background_job_id`.  
**Errors:** `404` for a foreign/missing version or bullet; `409` unless the version is a draft; `503` queue failure.

### GET /api/resume_versions/{version_id}/bullets
**Auth required:** yes  
**Description:** Lists the version's original and proposed text, structured guardrail flags, informational `low_effort_rewrite` state, and explicit approval/resolution state.
**Request:** Version UUID.  
**Response:** Ordered `resume_bullet_selections`.  
**Errors:** `404` if the version is not owned/found.

### PUT /api/resume_bullet_selections/{selection_id}
**Auth required:** yes  
**Description:** Approves a proposal, saves a user edit, or explicitly reverts to the immutable original text. Edits reset approval until the user approves them.  
**Request:** One of `approved`, `rewritten_text`, or `revert=true`; revert cannot be combined with another action.  
**Response:** Updated selection.  
**Errors:** `404` if not owned/found; `409` after finalization; `422` if an edit changes, adds, or removes a number or metric.

### POST /api/resume_versions/{version_id}/finalize
**Auth required:** yes  
**Description:** Moves a reviewing version to `finalized` only after every bullet has been explicitly approved or reverted.  
**Request:** Version UUID.  
**Response:** Finalized version.  
**Errors:** `404` if not owned/found; `409` with the unresolved selection IDs when any decision is missing.

### POST /api/storage/signed-upload-url
**Auth required:** yes  
**Description:** Creates a signed upload URL in the configured resume bucket under the user's UUID prefix.  
**Request:** JSON storage `path`.  
**Response:** Scoped path, signed URL, and optional token.  
**Errors:** `502` storage failure.

### POST /api/storage/signed-download-url
**Auth required:** yes  
**Description:** Creates a one-hour signed download URL under the user's UUID prefix.  
**Request:** JSON storage `path`.  
**Response:** Scoped path and signed URL.  
**Errors:** `502` storage failure.
