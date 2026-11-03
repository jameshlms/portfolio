# Project Specifications for My Web Portfolio

## Quick Rules

- Not quick and dirty, instead efficient for the small scale and professional.
- Follow good patterns according to stack and language.
- It's okay to push back and explain the pushback.
- When writing code that uses a framework or library, look up its documentation for up-to-date APIs and patterns — this avoids deprecated usage, improves type-checking accuracy, and prevents linting warnings.

## Tech Stack

Be sure to use any linked documentation for up-to-date information.

- **Backend**: FastAPI (Python 3.13), async-first
- **Templating**: Jinja2, server-rendered HTML (full pages + HTMX fragments)
- **Frontend interactivity**: HTMX [HTMX 4.0.0 Documentation](https://four.htmx.org/docs)
- **Content**: Blog posts live as markdown files with YAML frontmatter under `app/features/blog/posts/*.md`. Parsed at request time via `python-frontmatter` + `markdown-it-py`. No database.
- **Package management**: `uv` (dependencies in `pyproject.toml` + `uv.lock`)
- **Hosting**: Railway (Hobby plan), custom domain (jameshlms.com)
- **Linting/formatting**: `ruff`; type checking via `pyright`
- **Testing**: `pytest` with FastAPI `TestClient`

## Architecture

Feature-based folder structure (Django-style "apps") with a shared infrastructure layer for cross-cutting concerns.

```
app/
  main.py               # Composition root: middleware, mounts, router includes, exception handler registration
  config.py             # pydantic-settings BaseSettings
  core/                 # Cross-cutting concerns (no domain)
    templates.py        # Jinja2Templates; loader searches app/templates/ + every features/*/templates/
    htmx.py             # is_htmx() helper + vary_htmx middleware
    middleware.py       # register_middlewares(app)
    exceptions.py       # HTML error handlers, JSON when path starts with /api/
    db.py               # SQLAlchemy async engine, Base, get_session dep
    cache.py            # Redis connection pool, get_cache dep
  features/             # Domain features, each self-contained
    home/               # router.py, templates/
    about/              # router.py, templates/
    contact/            # router.py, templates/ (display-only, mailto + LinkedIn)
    blog/               # router.py, service.py, schema.py, templates/, posts/*.md
    github/             # router.py, service.py, schema.py, templates/
    seo/                # router.py, files/{robots,llms}.txt
  api/                  # Reserved for a future JSON API surface — currently empty
  templates/            # Shared layout only — feature templates live in their feature folder
    base.html
    components/         # _header.html, _footer.html, _nav.html
    errors/             # 404.html, 500.html
  static/               # URL-mounted at /static (css/, js/, favicon.svg)
```

Within a feature:
- `router.py` — HTTP handlers only. Thin. Delegates work to `service.py`.
- `service.py` — business logic (fetching, parsing, filtering). Where the work happens.
- `schema.py` — Pydantic models for typed data (external-API shapes, in-memory records). Not DB.
- `templates/` — Jinja2 templates owned by the feature.

## Conventions

- **HTMX branching**: routes that render either a full page or an HTMX fragment for the same URL use `is_htmx(request)` from `app.core` and pick the template accordingly. Global middleware sets `Vary: HX-Request` so caches don't cross-serve variants.
- **Errors**: `HTTPException` propagates to `app.core.exceptions.http_exception_handler`, which renders `templates/errors/404.html` or `500.html`. Requests to `/api/*` will return JSON instead when that layer is built.
- **Static assets** (CSS, JS, favicon) live in `app/static/` and are referenced via `url_for('static', path='...')` in templates.
- **Root-level served files** (robots.txt, llms.txt) live in the `seo` feature and are served via explicit `FileResponse` routes.
- **Templates loader**: `core/templates.py` globs every `app/features/*/templates/` so features can name their templates freely — filenames must stay unique across features.
- **No database.** If a future feature genuinely needs persistence, wire the DB layer back in (`app/db/` with async engine + `get_session` dep, `alembic/` for migrations) rather than reaching for the filesystem.

## Blog authoring

Add a new post by dropping a file into `app/features/blog/posts/` named `{slug}.md`. Frontmatter fields:

```yaml
---
title: Post title
summary: One-sentence summary shown in listings.
published_at: 2026-08-06T09:00:00   # omit or leave null to keep as draft
tags:
  - meta
  - python
---

Markdown body here.
```

Posts without `published_at` are treated as drafts and excluded from listings.

## Notes / Not Yet Built

- **JSON API** (`app/api/v1/`): reserved but empty. Build only when a real consumer (RSS reader, CLI, mobile app) exists.
- **Tests**: `tests/` directory at repo root, mirroring `app/features/`. Scaffold with a `conftest.py` exposing a `TestClient` fixture when tests are added.
- **Contact form**: the contact page currently displays mailto + LinkedIn links only. Adding a form that persists submissions would reintroduce the DB layer.
