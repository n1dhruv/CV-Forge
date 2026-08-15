import os

from cryptography.fernet import Fernet

DEFAULTS = {
    "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/cvforge_test",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SECRET_KEY": "sb_secret_test",
    "SUPABASE_STORAGE_BUCKET_RESUMES": "resumes",
    "SUPABASE_STORAGE_BUCKET_JD_UPLOADS": "jd-uploads",
    "SUPABASE_STORAGE_BUCKET_RESUME_IMPORTS": "resume-imports",
    "REDIS_URL": "redis://localhost:6379/15",
    "ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "PINECONE_API_KEY": "test",
    "PINECONE_INDEX_NAME": "resumeforge-bullets",
    "PINECONE_HOST": "https://test-index.example.test",
    "PINECONE_SPARSE_INDEX_NAME": "resumeforge-bullets-sparse",
    "OPENROUTER_API_KEY": "test",
    "OPENROUTER_RERANK_MODEL": "nvidia/llama-nemotron-rerank-vl-1b-v2:free",
    "GITHUB_CLIENT_ID": "test",
    "GITHUB_CLIENT_SECRET": "test",
    "TECTONIC_BINARY_PATH": "tectonic",
    "ENVIRONMENT": "test",
}
for key, value in DEFAULTS.items():
    os.environ.setdefault(key, value)
