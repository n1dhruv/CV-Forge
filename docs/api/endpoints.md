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
**Description:** Creates a manual Skill Bank item. An empty item has no vector until it has bullets.  
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
**Description:** Updates an owned item and queues fresh embeddings for its existing bullets.  
**Request:** Partial item JSON.  
**Response:** Updated item.  
**Errors:** `404`; `422` for invalid fields.

### DELETE /api/skill_bank/items/{item_id}
**Auth required:** yes  
**Description:** Deletes an item, its PostgreSQL bullets, and every Pinecone vector tagged with the item ID in the user's namespace.  
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

### GET /api/settings/llm/supported-models
**Auth required:** no  
**Description:** Lists completion models shown by the settings UI.  
**Request:** None.  
**Response:** Provider-to-model mapping.  
**Errors:** None under normal operation.

### GET /api/settings/llm/supported-embedding-models
**Auth required:** no  
**Description:** Lists the curated embedding providers and models shown in Settings.  
**Request:** None.  
**Response:** Provider-to-model mapping.  
**Errors:** None under normal operation.

### POST /api/settings/llm
**Auth required:** yes  
**Description:** Encrypts and saves completion settings plus an optional explicit embedding provider/model/key triplet.  
**Request:** `provider`, `model`, `api_key`; embedding fields must be supplied together when used.  
**Response:** Saved provider/model names; never returns keys.  
**Errors:** `422` for incomplete embedding configuration.

### GET /api/settings/llm
**Auth required:** yes  
**Description:** Returns provider/model names and masked keys.  
**Request:** None.  
**Response:** Completion and optional embedding settings with masked secrets.  
**Errors:** `404` when not configured.

### DELETE /api/settings/llm
**Auth required:** yes  
**Description:** Deletes the current user's encrypted LLM settings.  
**Request:** None.  
**Response:** `204`.  
**Errors:** `404` when not configured.

### POST /api/settings/llm/test
**Auth required:** yes  
**Description:** Sends a minimal completion request through the current user's provider.  
**Request:** None.  
**Response:** `{success, error}` with provider-independent safe errors.  
**Errors:** Provider failures are represented in the response.

### POST /api/settings/llm/test-embedding
**Auth required:** yes  
**Description:** Tests the saved embedding configuration, including the chat-provider fallback when a separate embedding provider is unset.  
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
**Description:** Returns parse status, structured JSON, requirements, and `action_verbs`. Older parses without that field return an empty list.  
**Request:** JD UUID.  
**Response:** JD detail; `action_verbs` exists both in parsed JSON and as the top-level structured list.  
**Errors:** `404` if not owned/found.

### POST /api/match/{jd_id}
**Auth required:** yes  
**Description:** Embeds each owned JD requirement, searches only the user's Pinecone namespace, then ranks owned PostgreSQL bullets by semantic score, token overlap, and mild recency.  
**Request:** JD UUID.  
**Response:** Grouped items/bullets, fixed confidence labels, `pending_embeddings`, and one result per requirement. A requirement with no qualifying evidence has `no_match=true` and `matched_bullets=[]`.
**Errors:** `404` foreign/missing JD; `400` missing/unsupported embedding configuration; `502` provider failure.

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
**Description:** Writes only the user's final submitted items, bullets, and skills into the Skill Bank with `source=resume_import`, then queues bullet embeddings.  
**Request:** JSON `items` and `skills`; omitted entries are not written, and at least one selection is required.  
**Response:** Created item details.  
**Errors:** `404` foreign/missing import; `409` not ready or already committed; `422` invalid fields.

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
