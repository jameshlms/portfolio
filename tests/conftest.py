import os

# Settings() is built at import time and these have no defaults; set placeholders
# so tests don't depend on a local .env. Real values in the environment win.
_REQUIRED_SETTINGS = {
    "GITHUB_TOKEN": "test",
    "GITHUB_CLIENT_ID": "test",
    "GITHUB_CLIENT_SECRET": "test",
    "GITHUB_ADMIN_USERNAME": "test",
    "SESSION_SECRET_KEY": "test",
    "DATABASE_URL": "postgresql://test:test@localhost/test",
    "REDIS_URL": "redis://localhost",
}
for key, value in _REQUIRED_SETTINGS.items():
    os.environ.setdefault(key, value)
