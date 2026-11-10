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
- **Content**: PostgreSQL via SQLAlchemy (async, `asyncpg`), migrations with Alembic. Blog posts are Markdown files in `content/blog/` (format in `content/README.md`), synced into `blog_posts` by `python -m app.cli sync-posts`; pages read the table.
- **Typed data**: Pydantic (settings, schema.org / Open Graph models); frozen dataclasses for internal records
- **Package management**: `uv` (dependencies in `pyproject.toml` + `uv.lock`; dev tools in the `dev` group)
- **Hosting**: Railway (Hobby plan), built from the root `Dockerfile`, custom domain (jameshlms.com)
- **Linting/formatting**: `ruff` (Python), `djlint` (templates, `jinja` profile); type checking via `pyright` (standard mode, configured in `pyproject.toml`)
- **Testing**: `pytest` with FastAPI `TestClient`
- **CI**: GitHub Actions (`.github/workflows/ci.yml`) runs ruff, djlint, pyright and pytest on PRs and pushes to `master`

## Architecture

Simple hexagonal (ports and adapters), grouped by feature inside each layer. Dependencies point inward: **adapters → ports → domain**, with use cases in between.

- **`domain/`**: records, business rules and every domain error. Plain frozen dataclasses and functions; imports only the standard library and itself.
- **`ports/driven/`**: the `Protocol`s the use cases need from infrastructure (`PostRepository`, `MarkdownRenderer`, `HumanVerifier`, `MailSender`). Imports only the domain.
- **`services/`**: thin async use cases (`send_contact_message`, `render_posts`, `sync_posts`, `blog_index`, `get_post`) that call domain rules and ports. Routes and the CLI call these; there are no driving-port Protocols, since each use case has one implementation.
- **Adapters**: driving ones are `routes/` (HTTP) and `cli.py`; driven ones are `adapters/` (they implement `ports/driven/`). `deps/` is the per-request wiring that picks which adapter fills each port.

`tests/test_architecture.py` enforces the domain and port import rules. `services/` also holds the SEO helpers (`seo.py`, `schema_org.py`, `open_graph.py`, `charts.py`). These are pure presentation code (page metadata and chart markup), not business rules, so they stay outside the domain and are unit-tested without the app.

```
app/
  main.py               # Composition root: lifespan, middleware, static mount, router includes
  config.py             # pydantic-settings Settings; every secret is optional (see .env.example)
  paths.py              # Every URL path: Page, RootFile, Internal enums + item_path()
  templates.py          # make_templates(): Jinja2Templates over app/templates, StrictUndefined,
                        #   globals base_url and site_name
  middleware.py         # TrustedHost, Vary: HX-Request, GZip (AdminAuthMiddleware defined, unregistered)
  exception_handlers.py # HTTPException -> errors/404.html or 500.html (JSON under /api/)
  cli.py                # `python -m app.cli sync-posts`: content/blog/*.md -> blog_posts
  log_config.py         # configure_logging(): structlog, console in DEBUG, JSON otherwise
  db.py                 # DeclarativeBase (datetimes are timestamptz), lazily created async
                        #   engine, get_session, transaction, close_engine
  models.py             # SQLAlchemy models (BlogPost, mirrors alembic 0001)
  deps/                 # FastAPI dependencies: IsHtmx, DbSession; contact.py wires the form's
                        #   adapters from settings; blog.py picks the PostRepository (SQL, or
                        #   empty in-memory without DATABASE_URL); rate_limit.py (in-memory
                        #   sliding window)
  routes/               # Thin HTTP handlers, one router per area
    pages.py            # Home, About; /resume redirects to RESUME_URL (About until set)
    contact.py          # Contact page; POST validates, rate limits, checks Turnstile, sends
    seo.py              # sitemap.xml, robots.txt, llms.txt
    health.py           # /healthz for Railway's deploy healthcheck
    blog.py             # /blog (tag filter via ?tag=, htmx swaps the list) and /blog/{slug}
    projects.py         # In progress; not registered in main.py
  domain/               # Pure business code; imports only the stdlib and app.domain
    errors.py           # DomainError and every domain error, grouped by feature
    contact.py          # Purpose, ContactMessage.parse, OutgoingEmail, compose_email
    blog.py             # Post records, parse_post (front matter), normalize_tag, build_index
  ports/
    driven/             # What the use cases need from outside; imports only app.domain
      contact.py        # HumanVerifier, MailSender
      blog.py           # PostRepository, MarkdownRenderer
  adapters/             # Driven adapters implementing ports/driven: turnstile.py (HumanVerifier),
                        #   resend.py (MailSender), log_mail.py (dev MailSender),
                        #   sql_posts.py / memory_posts.py (PostRepository), markdown.py
                        #   (MarkdownRenderer), post_files.py (reads content/blog/*.md)
  services/             # Use cases (thin async orchestration) and the SEO helpers
    contact.py          # send_contact_message
    blog.py             # render_posts, sync_posts, blog_index, get_post
    content.py          # Project DB queries (draft; to move behind a port like blog's)
    charts.py           # Plotly figure -> embeddable HTML
    seo.py              # PAGE_META (routed pages only), PublishedPage, SEOContext +
                        #   for_page / for_error_page / for_blog_index / for_post / for_project,
                        #   this site's schema.org nodes, published_posts, sitemap_urls,
                        #   llms_document
    schema_org.py       # schema.org node models; JsonLdDocument round-trips JSON-LD
    open_graph.py       # OpenGraph / OpenGraphArticle -> <meta property> pairs
  templates/
    base.html           # Layout; renders <head> entirely from `seo`
    components/         # _header.html, _footer.html, _nav.html, _plotly.html, _contact_form.html,
                        #   _post_list.html (htmx fragment), _post_meta.html
    pages/              # index.html, about.html, blog.html, blog_post.html, contact.html
    errors/             # 404.html, 500.html
    seo/                # sitemap.xml.j2, robots.txt.j2, llms.txt.j2
  static/               # URL-mounted at /static (css/, js/, images/, fonts/ (Inter, OFL), favicon.svg)
content/                # Site content in git: blog/*.md (see content/README.md)
alembic/                # Migrations (env.py imports app.db.Base and app.models)
tests/                  # Mirrors app/: domain/ (pure, no fakes), services/ (fake ports), adapters/,
                        #   routes/, deps/, plus architecture, full-app, CLI and boot tests. conftest swaps in an in-memory PostRepository for every app test
scripts/hooks/          # pre-commit: djlint-reformats staged HTML
```

## Conventions

- **Paths**: never hard-code a URL path in Python. Routes and links use the enums in `app/paths.py` (`Page` for HTML pages, `RootFile` for crawler files, `Internal` for admin/static/health); child pages use `item_path(collection, slug)`. Templates link with `url_for(...)` (djlint rule J018).
- **SEO on every page**: each HTML response passes `seo` — `for_page(Page.X)` or, in error handlers, `for_error_page(...)`. `StrictUndefined` makes a page without it fail to render rather than ship generic metadata. Don't hand-write `<title>`, description, canonical, Open Graph or JSON-LD in page templates.
- **PAGE_META is the single list of live pages**: it drives the sitemap, llms.txt and page metadata. Only add a page once its route is registered.
- **Standard names**: schema.org and Open Graph models use snake_case fields that serialize to the standard's names (`type` → `@type`, `same_as` → `sameAs`, `image_alt` → `og:image:alt`). Models are frozen with `extra="forbid"` so misspelled properties fail at construction. JSON-LD keyword mappings are scoped per model (nodes: `type`/`id`; the document: `context`/`graph`), and a test checks every model for fields that would serialize as an `@` keyword it doesn't own or share a key with another field.
- **Share images**: every page gets `og:image` from `SEOContext.image`, which defaults to `DEFAULT_SOCIAL_IMAGE` (the profile photo, 868×868). Pass a `SocialImage` with real `width`/`height` to override; only wide images (≈1.91:1, e.g. 1200×630) get a large Twitter card.
- **Charts**: plotly.js is not loaded globally. A page that renders `charts.render_chart(...)` includes `components/_plotly.html` in its `{% block head %}`. Blog posts embed charts with a `plotly` fence naming a figure JSON file in `content/blog/<slug>/`; the Markdown adapter renders it at sync (fixed div ids, so unchanged posts aren't rewritten) and sets `has_charts`, which makes `blog_post.html` include `_plotly.html`. Keep `_plotly.html`'s plotly.js version equal to the one the `plotly` package bundles (`plotly.offline.get_plotlyjs_version()`).
- **JavaScript is a last resort, not forbidden**: do as much as possible with HTML and CSS first (modern, widely supported features). When JS is needed, either keep it to a small, focused script or use an established library loaded where it's used (as with htmx and plotly.js), not hand-rolled frameworks.
- **HTMX branching**: routes that render either a full page or a fragment for the same URL take `htmx: IsHtmx` (from `app.deps`) and pick the template. Global middleware sets `Vary: HX-Request` so caches don't cross-serve variants.
- **Domain errors** all live in `domain/errors.py`, under `DomainError`, with a base per feature (`ContactError`, `BlogError`). A test checks that every class there derives from `DomainError`. The domain, use cases and driven adapters raise them (e.g. Resend raises `DeliveryFailed`). Routes and the CLI catch them and translate (e.g. `PostNotFound` -> 404). Never raise `HTTPException` or an infrastructure error past a port.
- **Errors**: `HTTPException` propagates to `app.exception_handlers.http_exception_handler`, which renders `errors/404.html` or `errors/500.html` with a `noindex` SEO context. Paths under `/api/` get JSON instead.
- **Root-level crawler files** (sitemap.xml, robots.txt, llms.txt) are rendered from `templates/seo/*.j2` by `routes/seo.py`. `sitemap.xml.j2` turns on autoescape explicitly, because `.j2` files aren't autoescaped by default.
- **Database is optional at runtime**: the engine is created on first use, so the app boots without `DATABASE_URL`. Without it the blog reads an empty in-memory repository, so every page and the sitemap still render. Queries live in driven adapters behind a port and return domain dataclasses, not ORM rows.
- **Unfinished features** can be merged: keep the router out of `main.py`, the page out of `PAGE_META`, and the link out of the nav until it works.
- **Type-checking exceptions are file-level and explained**: `schema_org.py` turns off `reportIncompatibleVariableOverride` (each subclass narrows `type` for the discriminator); `content.py` turns off undefined-variable checks until the `Project*` model exists. Don't add new exceptions without a comment saying why.
- **Immutability**: prefer frozen dataclasses / frozen Pydantic models and tuples for data passed between layers.

## Development

```bash
uv sync                                  # install, including dev tools
uv run fastapi dev app/main.py           # run locally with reload
uv run pytest                            # tests (Postgres ones skip unless TEST_DATABASE_URL is set
                                         #   to a migrated database; CI provides one)
uv run python -m app.cli sync-posts      # load content/blog into DATABASE_URL
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
- Postgres: set `DATABASE_URL` on Railway and set the pre-deploy command to `alembic upgrade head && python -m app.cli sync-posts`. A failed sync (an invalid post) fails the deploy and leaves the previous posts in place.

## Notes / Not Yet Built

- **Blog follow-ups**: full-text search (the `search_vector` column and GIN index are in place), an RSS/Atom feed, syntax highlighting for code blocks, and heading anchors.
- **Projects pages**: `routes/projects.py` isn't registered. Projects need a model and table first (`content.py` references undefined `Project*` names and carries ruff/pyright exceptions until then).
- **Admin**: GitHub OAuth settings, `AdminAuthMiddleware` and `admin.css` exist, but no admin routes or session middleware are registered.
- **llms-full.txt**: `RootFile.LLMS_FULL` is reserved; no route yet.
- **Contact form**: shown only when `TURNSTILE_SITE_KEY` + `TURNSTILE_SECRET_KEY` are set and mail can go out (`RESEND_API_KEY`, or logged when `DEBUG`). Resend needs the sending domain (`CONTACT_FROM_EMAIL`) verified. The rate limit is per process; move it to Redis if the app runs more than one replica. Brand logos in `static/images/brands/` are the official files, unmodified.
- **JSON API**: none. Build only when a real consumer (RSS reader, CLI, mobile app) exists; the error handler already returns JSON under `/api/`.
