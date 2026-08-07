# AI pipelines

Before using embeddings, create a classic dense Pinecone index named `resumeforge-bullets` with cosine similarity, set `PINECONE_INDEX_NAME`, copy its host into `PINECONE_HOST`, and set `PINECONE_API_KEY`. Its dimension must match every embedding model allowed by the app; one index cannot accept mixed vector dimensions.

Before using resume import, create a **private** bucket named `resume-imports` at **Supabase Dashboard → Storage → New bucket**, and set `SUPABASE_STORAGE_BUCKET_RESUME_IMPORTS=resume-imports`. Storage schema metadata is not written by Alembic.

## JD parsing

1. The user pastes a JD or uploads a PDF.
2. The API immediately stores a `job_descriptions` row and a `background_jobs` row in PostgreSQL, queues `jd_parse`, and returns both IDs.
3. The worker reads the text, using the private Supabase Storage object when a PDF was uploaded.
4. The worker calls the submitting user's encrypted BYOK completion configuration and validates the response. One correction attempt is allowed.
5. In one PostgreSQL transaction it stores parsed JSON, required/nice-to-have requirement rows, and action-verb rows, then marks the job done.
6. The UI polls the generic job endpoint and reads the JD detail. JDs created before action verbs were added return an empty list instead of failing.

## Embedding and matching

1. Creating or editing a bullet queues an `embedding` job; changing its parent item queues fresh jobs for that item's bullets.
2. The CRUD request returns without waiting for the LLM or Pinecone.
3. The worker loads the real bullet from PostgreSQL, calls the user's embedding provider, and writes only the numeric vector plus lookup metadata to Pinecone. PostgreSQL remains the source of truth for all text and dates.
4. Pinecone stores every user's vectors in a namespace named with that user's UUID. Vector IDs equal PostgreSQL bullet UUIDs.
5. When the user starts matching, the API verifies ownership of the JD, embeds each structured requirement, and searches only that same namespace.
6. The API looks every returned UUID up in the user's PostgreSQL Skill Bank, combines semantic similarity with simple token overlap and a mild recency signal, limits bullets per parent item, and returns grouped results.
7. If PostgreSQL contains bullets not seen in Pinecone, the response sets `pending_embeddings=true` so the UI can show processing rather than treating a partial result as complete.
8. Deleting a bullet/item removes its Pinecone vector(s) before deleting PostgreSQL content, preventing deleted content from resurfacing.

## Resume import

1. The user uploads a PDF or DOCX.
2. The API writes the file to the private Supabase `resume-imports` bucket, creates PostgreSQL staging/job rows, queues `resume_import`, and immediately returns both IDs.
3. The worker checks the user's LLM settings before spending work on extraction, downloads the object, extracts text, and saves that raw text on the staging row.
4. The worker asks the user's completion model for a strict JSON structure. The prompt forbids inference or embellishment, and a server check rejects returned bullets/skills that are not literally present in the extracted text.
5. A valid response is stored only in `resume_imports.parsed_json`. It is review data, not Skill Bank data.
6. The user edits/removes content and submits the final selection to `/commit`.
7. One transaction writes only submitted items and bullets into PostgreSQL with `source=resume_import`, marks the staging row committed, and rejects a second commit. Bullet embedding jobs then populate Pinecone asynchronously.
