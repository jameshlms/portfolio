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
- **Content**: PostgreSQL via SQLAlchemy (async, `asyncpg`), migrations with Alembic. Blog posts have a table (`blog_posts`) but no registered route reads it yet.
- **Typed data**: Pydantic (settings, schema.org / Open Graph models); frozen dataclasses for internal records
- **Package management**: `uv` (dependencies in `pyproject.toml` + `uv.lock`; dev tools in the `dev` group)
- **Hosting**: Railway (Hobby plan), built from the root `Dockerfile`, custom domain (jameshlms.com)
- **Linting/formatting**: `ruff` (Python), `djlint` (templates, `jinja` profile); type checking via `pyright` (standard mode, configured in `pyproject.toml`)
- **Testing**: `pytest` with FastAPI `TestClient`
- **CI**: GitHub Actions (`.github/workflows/ci.yml`) runs ruff, djlint, pyright and pytest on PRs and pushes to `master`

## Architecture

Flat layers, dependencies pointing inward: **routes → services → models/db**. Routes are thin HTTP adapters; services hold the logic. The SEO services (`seo.py`, `schema_org.py`, `open_graph.py`) are pure (no I/O) and are unit-tested without the app.

```
app/
  main.py               # Composition root: lifespan, middleware, static mount, router includes
  config.py             # pydantic-settings Settings; every secret is optional (see .env.example)
  paths.py              # Every URL path: Page, RootFile, Internal enums + item_path()
  templates.py          # make_templates(): Jinja2Templates over app/templates, StrictUndefined,
                        #   globals base_url and site_name
  middleware.py         # TrustedHost, Vary: HX-Request, GZip (AdminAuthMiddleware defined, unregistered)
  exception_handlers.py # HTTPException -> errors/404.html or 500.html (JSON under /api/)
  db.py                 # DeclarativeBase, lazily created async engine, get_session, close_engine
  models.py             # SQLAlchemy models (BlogPost, mirrors alembic 0001)
  deps/                 # FastAPI dependencies: IsHtmx, DbSession
  routes/               # Thin HTTP handlers, one router per area
    pages.py            # Home, About, Contact
    seo.py              # sitemap.xml, robots.txt, llms.txt
    health.py           # /healthz for Railway's deploy healthcheck
    blog.py, projects.py  # In progress; not registered in main.py
  services/
    content.py          # DB queries -> domain records (e.g. published_posts -> PublishedPage)
    charts.py           # Plotly figure -> embeddable HTML
    seo.py              # PAGE_META (routed pages only), PublishedPage, SEOContext +
                        #   for_page / for_error_page / for_project, this site's schema.org
                        #   nodes, sitemap_urls, llms_document
    schema_org.py       # schema.org node models; JsonLdDocument round-trips JSON-LD
    open_graph.py       # OpenGraph / OpenGraphArticle -> <meta property> pairs
  templates/
    base.html           # Layout; renders <head> entirely from `seo`
    components/         # _header.html, _footer.html, _nav.html
    pages/              # index.html, about.html, contact.html
    errors/             # 404.html, 500.html
    seo/                # sitemap.xml.j2, robots.txt.j2, llms.txt.j2
  static/               # URL-mounted at /static (css/, js/, images/, favicon.svg)
alembic/                # Migrations (env.py imports app.db.Base and app.models)
tests/                  # Mirrors app/: routes/, services/, plus full-app and boot tests
scripts/hooks/          # pre-commit: djlint-reformats staged HTML
```

## Conventions

- **Paths**: never hard-code a URL path in Python. Routes and links use the enums in `app/paths.py` (`Page` for HTML pages, `RootFile` for crawler files, `Internal` for admin/static/health); child pages use `item_path(collection, slug)`. Templates link with `url_for(...)` (djlint rule J018).
- **SEO on every page**: each HTML response passes `seo` — `for_page(Page.X)` or, in error handlers, `for_error_page(...)`. `StrictUndefined` makes a page without it fail to render rather than ship generic metadata. Don't hand-write `<title>`, description, canonical, Open Graph or JSON-LD in page templates.
- **PAGE_META is the single list of live pages**: it drives the sitemap, llms.txt and page metadata. Only add a page once its route is registered.
- **Standard names**: schema.org and Open Graph models use snake_case fields that serialize to the standard's names (`type` → `@type`, `same_as` → `sameAs`, `image_alt` → `og:image:alt`). Models are frozen with `extra="forbid"` so misspelled properties fail at construction.
- **HTMX branching**: routes that render either a full page or a fragment for the same URL take `htmx: IsHtmx` (from `app.deps`) and pick the template. Global middleware sets `Vary: HX-Request` so caches don't cross-serve variants.
- **Errors**: `HTTPException` propagates to `app.exception_handlers.http_exception_handler`, which renders `errors/404.html` or `errors/500.html` with a `noindex` SEO context. Paths under `/api/` get JSON instead.
- **Root-level crawler files** (sitemap.xml, robots.txt, llms.txt) are rendered from `templates/seo/*.j2` by `routes/seo.py`. `sitemap.xml.j2` turns on autoescape explicitly, because `.j2` files aren't autoescaped by default.
- **Database is optional at runtime**: the engine is created on first use, so the app boots without `DATABASE_URL`. Routes get a session through the `DbSession` dependency; queries live in `services/content.py` and return domain dataclasses, not ORM rows.
- **Unfinished features** can be merged: keep the router out of `main.py`, the page out of `PAGE_META`, and the link out of the nav until it works.
- **Type-checking exceptions are file-level and explained**: `schema_org.py` turns off `reportIncompatibleVariableOverride` (each subclass narrows `type` for the discriminator); `content.py` turns off undefined-variable checks until the `Project*` model exists. Don't add new exceptions without a comment saying why.
- **Immutability**: prefer frozen dataclasses / frozen Pydantic models and tuples for data passed between layers.

## Development

```bash
uv sync                                  # install, including dev tools
uv run fastapi dev app/main.py           # run locally with reload
uv run pytest                            # tests
uv run ruff check . && uv run ruff format --check .
uv run djlint app/templates --lint && uv run djlint app/templates --check
uv run pyright                           # type check
git config core.hooksPath scripts/hooks  # enable the djlint pre-commit hook
```

Copy `.env.example` to `.env` for local settings; the app runs with it empty.

## Deployment

- `master` is production: Railway builds the `Dockerfile` on every push. Work on short-lived branches and merge by PR once CI passes.
- The container runs uvicorn from the venv (`uv sync --frozen --no-dev` at build time) with `--proxy-headers`, so `url_for` produces `https://` URLs behind Railway's proxy.
- Railway settings live in the dashboard (healthcheck path `/healthz`, "Wait for CI"). `railway.toml` is deprecated (stops being read 2026-12-01); generate `.railway/railway.py` with `railway config pull` if config-as-code is wanted.
- When the DB is wired in: set `DATABASE_URL` on Railway and run `alembic upgrade head` as the pre-deploy command.

## Notes / Not Yet Built

- **Blog and projects pages**: `routes/blog.py` and `routes/projects.py` aren't registered. `content.published_posts` is ready to feed the sitemap and llms.txt once `/blog/{slug}` has a route. Projects need a model and table first (`content.py` references undefined `Project*` names and carries ruff/pyright exceptions until then).
- **Admin**: GitHub OAuth settings, `AdminAuthMiddleware` and `admin.css` exist, but no admin routes or session middleware are registered.
- **llms-full.txt**: `RootFile.LLMS_FULL` is reserved; no route yet.
- **Contact form**: the contact page shows mailto + LinkedIn links only.
- **JSON API**: none. Build only when a real consumer (RSS reader, CLI, mobile app) exists; the error handler already returns JSON under `/api/`.
