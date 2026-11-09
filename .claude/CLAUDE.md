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
- **Content**: PostgreSQL via SQLAlchemy (async, `asyncpg`), migrations with Alembic. Blog posts are Markdown files in `content/blog/` (format in `content/README.md`), synced into `blog_posts` by `python -m app sync-posts`; pages read the table.
- **Typed data**: Pydantic (settings, schema.org / Open Graph models); frozen dataclasses for internal records
- **Package management**: `uv` (dependencies in `pyproject.toml` + `uv.lock`; dev tools in the `dev` group)
- **Hosting**: Railway (Hobby plan), built from the root `Dockerfile`, custom domain (jameshlms.com)
- **Linting/formatting**: `ruff` (Python), `djlint` (templates, `jinja` profile); type checking via `pyright` (standard mode, configured in `pyproject.toml`)
- **Testing**: `pytest` with FastAPI `TestClient`
- **CI**: GitHub Actions (`.github/workflows/ci.yml`) runs ruff, djlint, pyright and pytest on PRs and pushes to `master`

## Architecture

Simple hexagonal (ports and adapters), grouped by feature inside each layer. Dependencies point inward: **adapters → ports → domain**, with use cases in between. `tests/test_architecture.py` enforces the import rules.

- **`domain/`**: records, business rules and every domain error. Plain frozen dataclasses and functions; imports only the standard library and itself.
- **`ports/driven/`**: the `Protocol`s the use cases need from infrastructure (`PostRepository` and its `PostRepositoryScope`, `MarkdownRenderer`, `HumanVerifier`, `MailSender`). Imports only the domain.
- **`services/`**: thin async use cases (`send_contact_message`, `render_posts`, `sync_posts`, `blog_index`, `get_post`) that call domain rules and ports. There are no driving-port Protocols: each use case has one implementation.
- **`adapters/`**: driving adapters (`http/` the website, `cli/` the command line) and driven ones (`postgres/`, `turnstile`, `resend`, `log_mail`, `markdown`, `memory_posts`). Adapters never import each other (the `charts` helper is shared); they meet only through ports.
- **Composition**: `container.py` defines `Container`, which port is filled by which object, holding only port types. `bootstrap.py` is the only module that builds concrete adapters: settings in, `Container` out. The entry points call it: `main.py` (`app = create_app(bootstrap())`, for uvicorn) and `__main__.py` (`python -m app <command>`). Tests skip bootstrap and build a `Container` of fakes.

```
app/
  main.py               # Web entry: configure_logging(); app = create_app(bootstrap())
  __main__.py           # CLI entry: python -m app <command> (see adapters/cli)
  bootstrap.py          # Settings -> Container: picks Postgres or in-memory posts, Turnstile,
                        #   Resend / log mailer; owns the HTTP client and DB pool (Container.close)
  container.py          # Container: the ports each driving adapter is given
  config.py             # pydantic-settings Settings; every secret is optional (see .env.example)
  log_config.py         # configure_logging(): structlog, console in DEBUG, JSON otherwise
  domain/               # Pure business code; imports only the stdlib and app.domain
    errors.py           # DomainError and every domain error, grouped by feature
    contact.py          # Purpose, ContactMessage.parse, OutgoingEmail, compose_email
    blog.py             # Post records, parse_post (front matter), normalize_tag, build_index
  ports/
    driven/             # What the use cases need from outside; imports only app.domain
      contact.py        # HumanVerifier, MailSender
      blog.py           # PostRepository, PostRepositoryScope, MarkdownRenderer
  services/             # Use cases: thin async orchestration
    contact.py          # send_contact_message
    blog.py             # render_posts, sync_posts, blog_index, get_post
  adapters/
    http/               # Driving: the website
      app.py            # create_app(container): middleware, handlers, static, routers; closes
                        #   the container at shutdown; per-app contact rate limiter
      paths.py          # Every URL path: Page, RootFile, Internal enums + item_path()
      templates.py      # make_templates(): Jinja2 over http/templates, StrictUndefined, globals
      middleware.py     # TrustedHost, Vary: HX-Request, GZip (AdminAuthMiddleware defined, unregistered)
      exception_handlers.py  # HTTPException -> errors/404.html or 500.html (JSON under /api/)
      deps/             # FastAPI dependencies: AppContainer (the Container), IsHtmx; contact.py
                        #   and blog.py take their ports from the container; rate_limit.py
      routes/           # Thin handlers, one router per area: pages, blog, contact, seo, health
                        #   (projects.py in progress, not registered)
      presentation/     # seo.py (PAGE_META, SEOContext, for_page / for_post / ..., sitemap,
                        #   llms.txt), schema_org.py, open_graph.py
      templates/        # base.html, components/, pages/, errors/, seo/*.j2
      static/           # URL-mounted at /static (css/, js/, images/, fonts/, favicon.svg)
    cli/                # Driving: commands.py (sync-posts), post_files.py (reads content/blog)
    postgres/           # Driven: engine.py (make_engine, make_sessions), models.py (Base,
                        #   BlogPost, mirrors alembic 0001), posts.py (SqlPostRepository +
                        #   sql_post_repositories scope), projects.py (draft queries)
    turnstile.py        # HumanVerifier
    resend.py, log_mail.py  # MailSender (production / development)
    markdown.py         # MarkdownRenderer (markdown-it + `plotly` chart fences)
    memory_posts.py     # In-memory PostRepository: no-database mode and tests
    charts.py           # Plotly figure -> embeddable HTML (shared helper, not an adapter)
content/                # Site content in git: blog/*.md (see content/README.md)
alembic/                # Migrations (env.py imports app.adapters.postgres.models.Base)
tests/                  # Mirrors app/: domain/ (pure), services/ (fake ports), adapters/ (http/
                        #   through create_app, cli, postgres contract tests), architecture and
                        #   boot tests. conftest builds a Container of fakes and a fresh app per test
scripts/hooks/          # pre-commit: djlint-reformats staged HTML
```

## Conventions

- **Paths**: never hard-code a URL path in Python. Routes and links use the enums in `app/adapters/http/paths.py` (`Page` for HTML pages, `RootFile` for crawler files, `Internal` for admin/static/health); child pages use `item_path(collection, slug)`. Templates link with `url_for(...)` (djlint rule J018).
- **SEO on every page**: each HTML response passes `seo` — `for_page(Page.X)` or, in error handlers, `for_error_page(...)`. `StrictUndefined` makes a page without it fail to render rather than ship generic metadata. Don't hand-write `<title>`, description, canonical, Open Graph or JSON-LD in page templates.
- **PAGE_META is the single list of live pages**: it drives the sitemap, llms.txt and page metadata. Only add a page once its route is registered.
- **Standard names**: schema.org and Open Graph models use snake_case fields that serialize to the standard's names (`type` → `@type`, `same_as` → `sameAs`, `image_alt` → `og:image:alt`). Models are frozen with `extra="forbid"` so misspelled properties fail at construction. JSON-LD keyword mappings are scoped per model (nodes: `type`/`id`; the document: `context`/`graph`), and a test checks every model for fields that would serialize as an `@` keyword it doesn't own or share a key with another field.
- **Share images**: every page gets `og:image` from `SEOContext.image`, which defaults to `DEFAULT_SOCIAL_IMAGE` (the profile photo, 868×868). Pass a `SocialImage` with real `width`/`height` to override; only wide images (≈1.91:1, e.g. 1200×630) get a large Twitter card.
- **Charts**: plotly.js is not loaded globally. A page that renders `charts.render_chart(...)` includes `components/_plotly.html` in its `{% block head %}`. Blog posts embed charts with a `plotly` fence naming a figure JSON file in `content/blog/<slug>/`; the Markdown adapter renders it at sync (fixed div ids, so unchanged posts aren't rewritten) and sets `has_charts`, which makes `blog_post.html` include `_plotly.html`. Keep `_plotly.html`'s plotly.js version equal to the one the `plotly` package bundles (`plotly.offline.get_plotlyjs_version()`).
- **JavaScript is a last resort, not forbidden**: do as much as possible with HTML and CSS first (modern, widely supported features). When JS is needed, either keep it to a small, focused script or use an established library loaded where it's used (as with htmx and plotly.js), not hand-rolled frameworks.
- **HTMX branching**: routes that render either a full page or a fragment for the same URL take `htmx: IsHtmx` (from `app.adapters.http.deps`) and pick the template. Global middleware sets `Vary: HX-Request` so caches don't cross-serve variants.
- **Domain errors** all live in `domain/errors.py`, under `DomainError`, with a base per feature (`ContactError`, `BlogError`). A test checks that every class there derives from `DomainError`. The domain, use cases and driven adapters raise them (e.g. Resend raises `DeliveryFailed`). Routes and the CLI catch them and translate (e.g. `PostNotFound` -> 404). Never raise `HTTPException` or an infrastructure error past a port.
- **Errors**: `HTTPException` propagates to `app.adapters.http.exception_handlers.http_exception_handler`, which renders `errors/404.html` or `errors/500.html` with a `noindex` SEO context. Paths under `/api/` get JSON instead.
- **Root-level crawler files** (sitemap.xml, robots.txt, llms.txt) are rendered from `templates/seo/*.j2` by `routes/seo.py`. `sitemap.xml.j2` turns on autoescape explicitly, because `.j2` files aren't autoescaped by default.
- **Database is optional at runtime**: without `DATABASE_URL`, bootstrap gives the blog an empty in-memory repository, so every page and the sitemap still render (the engine doesn't connect until the first query anyway). `sync-posts` refuses to run without it. Queries live in driven adapters behind a port and return domain dataclasses, not ORM rows.
- **Unfinished features** can be merged: keep the router out of `adapters/http/app.py`, the page out of `PAGE_META`, and the link out of the nav until it works.
- **Type-checking exceptions are file-level and explained**: `schema_org.py` turns off `reportIncompatibleVariableOverride` (each subclass narrows `type` for the discriminator); `adapters/postgres/projects.py` turns off undefined-variable checks until the `Project*` model exists. Don't add new exceptions without a comment saying why.
- **Immutability**: prefer frozen dataclasses / frozen Pydantic models and tuples for data passed between layers.

## Development

```bash
uv sync                                  # install, including dev tools
uv run fastapi dev app/main.py           # run locally with reload
uv run pytest                            # tests (Postgres ones skip unless TEST_DATABASE_URL is set
                                         #   to a migrated database; CI provides one)
uv run python -m app sync-posts          # load content/blog into DATABASE_URL
uv run ruff check . && uv run ruff format --check .
uv run djlint app/adapters/http/templates --lint && uv run djlint app/adapters/http/templates --check
uv run pyright                           # type check
git config core.hooksPath scripts/hooks  # enable the djlint pre-commit hook
```

Copy `.env.example` to `.env` for local settings; the app runs with it empty.

## Deployment

- `master` is production: Railway builds the `Dockerfile` on every push. Work on short-lived branches and merge by PR once CI passes.
- The container runs uvicorn from the venv (`uv sync --frozen --no-dev` at build time) with `--proxy-headers`, so `url_for` produces `https://` URLs behind Railway's proxy.
- Railway settings live in the dashboard (healthcheck path `/healthz`, "Wait for CI"). `railway.toml` is deprecated (stops being read 2026-12-01); generate `.railway/railway.py` with `railway config pull` if config-as-code is wanted.
- Postgres: set `DATABASE_URL` on Railway and set the pre-deploy command to `alembic upgrade head && python -m app sync-posts`. A failed sync (an invalid post) fails the deploy and leaves the previous posts in place.

## Notes / Not Yet Built

- **Blog follow-ups**: full-text search (the `search_vector` column and GIN index are in place), an RSS/Atom feed, syntax highlighting for code blocks, and heading anchors.
- **Projects pages**: `routes/projects.py` isn't registered. Projects need a model and table first (`adapters/postgres/projects.py` references undefined `Project*` names and carries ruff/pyright exceptions until then).
- **Admin**: GitHub OAuth settings, `AdminAuthMiddleware` and `admin.css` exist, but no admin routes or session middleware are registered.
- **llms-full.txt**: `RootFile.LLMS_FULL` is reserved; no route yet.
- **Contact form**: shown only when bootstrap provides both ports (`TURNSTILE_SECRET_KEY` for the verifier; `RESEND_API_KEY`, or the log mailer when `DEBUG`, for the sender) and `TURNSTILE_SITE_KEY` is set for the widget. Resend needs the sending domain (`CONTACT_FROM_EMAIL`) verified. The rate limit is per process; move it to Redis if the app runs more than one replica. Brand logos in `adapters/http/static/images/brands/` are the official files, unmodified.
- **JSON API**: none. Build only when a real consumer (RSS reader, CLI, mobile app) exists; the error handler already returns JSON under `/api/`.
