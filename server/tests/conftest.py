import os

from cryptography.fernet import Fernet

DEFAULTS = {
    "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/cvforge_test",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role",
    "SUPABASE_STORAGE_BUCKET_RESUMES": "resumes",
    "SUPABASE_STORAGE_BUCKET_JD_UPLOADS": "jd-uploads",
    "REDIS_URL": "redis://localhost:6379/15",
    "CLERK_SECRET_KEY": "sk_test_example",
    "CLERK_JWKS_URL": "https://clerk.example/.well-known/jwks.json",
    "CLERK_ISSUER": "https://clerk.example",
    "CLERK_WEBHOOK_SIGNING_SECRET": "whsec_dGVzdHNlY3JldHRlc3RzZWNyZXQ=",
    "ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "EMBEDDING_MODEL": "test",
    "GITHUB_CLIENT_ID": "test",
    "GITHUB_CLIENT_SECRET": "test",
    "TECTONIC_BINARY_PATH": "tectonic",
    "ENVIRONMENT": "test",
}
for key, value in DEFAULTS.items():
    os.environ.setdefault(key, value)
