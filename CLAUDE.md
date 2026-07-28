# Project Specifications for My Web Portfolio

## Quick Rules

- Not quick and dirty, instead efficient for the small scale and professional.
- Follow good patterns according to stack and language.
- It's okay to push back and explain the pushback.

## Tech Stack

Be sure to use any linked documentation for up-to-date information.

- **Backend**: FastAPI (Python 3.13), async-first
- **Templating**: Jinja2, server-rendered HTML (full pages + HTMX fragments)
- **Frontend interactivity**: HTMX [HTMX 4.0.0 Documentation](https://four.htmx.org/docs)
- **Package management**: `uv` (dependencies in `pyproject.toml` + `uv.lock`)
- **Dev environment**: Dev Container (`.devcontainer/`) + Docker for production (`Dockerfile` at root)
- **Database**: SQLite via SQLAlchemy (async, `aiosqlite`), stored on a mounted Railway Volume for persistence
- **Architecture**: feature-based folder structure (`app/features/<feature>/`), each with its own `router.py`, data/logic module, and `templates/`
- **API layer**: separate JSON-only API surface at `app/api/v1.py`, reuses feature logic, distinct from HTMX fragment routes
- **Hosting**: Railway (Hobby plan), custom domain (jameshlms.com)
- **Analytics**: self-hosted, logged server-side into SQLite (no third-party tracker)
- **Linting/formatting**: `ruff`; type checking via `mypy`/`pyright`
- **Testing**: `pytest` with FastAPI `TestClient`