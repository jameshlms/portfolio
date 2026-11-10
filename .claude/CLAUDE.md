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

Flat layers, dependencies pointing inward: **routes / cli → services → models/db**. Routes are thin HTTP adapters; services hold the logic.

- **Feature modules**: each feature with rules is one module in `services/` holding, in this order, its records (frozen dataclasses), the `Protocol`s it needs from outside, its rules, and its use-case functions: `services/blog.py`, `services/contact.py`. They're pure (no I/O, no framework imports), so they're unit-tested without the app; `tests/test_architecture.py` checks they import only the standard library and each other.
- **Adapters** in `adapters/` implement those Protocols (Postgres and in-memory posts, Markdown, Turnstile, Resend, the log mailer, the post-file reader). `deps/` chooses which one a request gets; tests override those dependencies with fakes.
- **Where errors live**: every domain error is in `services/errors.py` (see Conventions).
- **Presentation helpers** also live in `services/`: `seo.py`, `schema_org.py`, `open_graph.py` and `charts.py` are pure page-metadata and chart-markup code, tested without the app.

```
app/
  main.py               # Composition root: lifespan, middleware, static mount, router includes
  config.py             # pydantic-settings Settings; every secret is optional (see .env.example);
                        #   errors hide values; PORTFOLIO_ENV_FILE picks the dotenv file
  paths.py              # Every URL path: Page, RootFile, Internal enums + item_path()
  templates.py          # make_templates(): Jinja2Templates over app/templates, StrictUndefined,
                        #   globals base_url and site_name
  middleware.py         # TrustedHost, Vary: HX-Request, GZip
  exception_handlers.py # DomainError (by _DOMAIN_STATUS), HTTPException, validation and unexpected
                        #   errors -> errors/error.html, fragments/_error.html (htmx), JSON (/api/)
  cli.py                # `python -m app.cli sync-posts`: content/blog/*.md -> blog_posts
  log_config.py         # configure_logging(): structlog, console in DEBUG, JSON otherwise
  db.py                 # DeclarativeBase (datetimes are timestamptz), lazily created async
                        #   engine, get_session, transaction, close_engine
  models.py             # SQLAlchemy models (BlogPost, mirrors alembic 0001)
  deps/                 # FastAPI dependencies: IsHtmx (+ wants_fragment); contact.py
                        #   wires the form's adapters from settings; blog.py picks the
                        #   PostRepository (SQL, or empty in-memory without DATABASE_URL);
                        #   rate_limit.py (in-memory sliding window)
  routes/               # Thin HTTP handlers, one router per area
    pages.py            # Home, About; /resume redirects to RESUME_URL (About until set)
    contact.py          # Contact page; POST validates, rate limits, checks Turnstile, sends
    seo.py              # sitemap.xml, robots.txt, llms.txt
    health.py           # /healthz for Railway's deploy healthcheck
    blog.py             # /blog (tag filter via ?tag=, htmx swaps the list) and /blog/{slug}
  services/
    errors.py           # DomainError and every domain error, grouped by feature
    blog.py             # Post records; PostRepository, MarkdownRenderer; parse_post,
                        #   build_index; render_posts, sync_posts, blog_index, get_post,
                        #   list_published_posts
    contact.py          # Purpose, ContactMessage.parse, OutgoingEmail, compose_email;
                        #   HumanVerifier, MailSender; send_contact_message
    charts.py           # Plotly figure -> embeddable HTML
    seo.py              # PAGE_META (routed pages only), PublishedPage, SEOContext +
                        #   for_page / for_error_page / for_blog_index / for_post,
                        #   this site's schema.org nodes, published_posts, sitemap_urls,
                        #   llms_document
    schema_org.py       # schema.org node models; JsonLdDocument round-trips JSON-LD
    open_graph.py       # OpenGraph / OpenGraphArticle -> <meta property> pairs
  adapters/             # turnstile.py (HumanVerifier), resend.py / log_mail.py (MailSender),
                        #   sql_posts.py / memory_posts.py (PostRepository), markdown.py
                        #   (MarkdownRenderer), post_files.py (reads content/blog/*.md)
  templates/
    base.html           # Layout; renders <head> entirely from `seo`
    pages/              # index.html, about.html, blog.html, blog_post.html, contact.html
    errors/             # error.html (every status)
    seo/                # sitemap.xml.j2, robots.txt.j2, llms.txt.j2
    components/         # include-only partials: _header, _footer, _nav, _plotly, _post_meta,
                        #   _error_message
    fragments/          # also returned alone to htmx: _post_list, _contact_form, _error
  static/               # URL-mounted at /static (css/, js/, images/, fonts/ (Inter, OFL), favicon.svg)
content/                # Site content in git: blog/*.md (see content/README.md)
alembic/                # Migrations (env.py imports app.db.Base and app.models)
tests/                  # Mirrors app/: services/ (rules and use cases, with fakes), adapters/,
                        #   routes/, deps/, plus template, architecture, full-app, CLI and boot
                        #   tests. conftest swaps in an in-memory PostRepository for every app test
scripts/hooks/          # pre-commit: djlint-reformats staged HTML
```

## Conventions

- **Paths**: never hard-code a URL path in Python. Routes and links use the enums in `app/paths.py` (`Page` for HTML pages, `RootFile` for crawler files, `Internal` for static/health); child pages use `item_path(collection, slug)`. Templates link with `url_for(...)` (djlint rule J018).
- **SEO on every page**: each HTML response passes `seo` — `for_page(Page.X)` or, in error handlers, `for_error_page(...)`. `StrictUndefined` makes a page without it fail to render rather than ship generic metadata. Don't hand-write `<title>`, description, canonical, Open Graph or JSON-LD in page templates.
- **PAGE_META is the single list of live pages**: it drives the sitemap, llms.txt and page metadata. Only add a page once its route is registered.
- **Standard names**: schema.org and Open Graph models use snake_case fields that serialize to the standard's names (`type` → `@type`, `same_as` → `sameAs`, `image_alt` → `og:image:alt`). Models are frozen with `extra="forbid"` so misspelled properties fail at construction. JSON-LD keyword mappings are scoped per model (nodes: `type`/`id`; the document: `context`/`graph`), and a test checks every model for fields that would serialize as an `@` keyword it doesn't own or share a key with another field.
- **Share images**: every page gets `og:image` from `SEOContext.image`, which defaults to `DEFAULT_SOCIAL_IMAGE` (the profile photo, 868×868). Pass a `SocialImage` with real `width`/`height` to override; only wide images (≈1.91:1, e.g. 1200×630) get a large Twitter card.
- **Charts**: plotly.js is not loaded globally. A page that renders `charts.render_chart(...)` includes `components/_plotly.html` in its `{% block head %}`. Blog posts embed charts with a `plotly` fence naming a figure JSON file in `content/blog/<slug>/`; the Markdown adapter renders it at sync (fixed div ids, so unchanged posts aren't rewritten) and sets `has_charts`, which makes `blog_post.html` include `_plotly.html`. Keep `_plotly.html`'s plotly.js version equal to the one the `plotly` package bundles (`plotly.offline.get_plotlyjs_version()`).
- **JavaScript is a last resort, not forbidden**: do as much as possible with HTML and CSS first (modern, widely supported features). When JS is needed, either keep it to a small, focused script or use an established library loaded where it's used (as with htmx and plotly.js), not hand-rolled frameworks.
- **HTMX branching**: routes that render either a full page or a fragment for the same URL take `htmx: IsHtmx` (from `app.deps`) and pick the template (`"fragments/_x.html" if htmx else "pages/x.html"`). `IsHtmx` (and `wants_fragment`, for code outside a route) is False for boosted requests and history restores, which need the full page. Global middleware sets `Vary: HX-Request` so caches don't cross-serve variants.
- **Template folders**: `pages/` (whole pages), `errors/`, `seo/` (crawler files) and `fragments/` are what Python renders. `components/` holds partials that are only ever `{% include %}`d; no Python code names them. A partial that a route (or the exception handler) also returns on its own for htmx goes in `fragments/`. Every outermost element of a fragment, in every branch, carries the `id` its `hx-target` names (the swap is `outerHTML`, so the target must survive). A fragment that emits a `<title>` does so only when `htmx` is true, so the route passes `htmx` in both cases. `tests/test_templates.py` enforces all of this: known folders only, no component rendered from Python, every fragment returned on its own, the swap target kept, and every include/extends/import resolving.
- **Domain errors** all live in `services/errors.py`, under `DomainError`, with a base per feature (`ContactError`, `BlogError`). A test checks that every class there derives from `DomainError`. Feature modules raise them for broken rules (`InvalidPost`, `UnknownTag`, `PostNotFound`). Adapters translate infrastructure failures into them: Turnstile raises `HumanCheckUnavailable`, Resend `DeliveryFailed`, and `sql_posts` `PostsUnavailable` for any SQLAlchemy or connection (`OSError`) error, via its `storage_errors()` context manager. Never raise `HTTPException` from `services/`.
- **Handling errors over HTTP**: routes let domain errors propagate. `exception_handlers.py` maps them by type through `_DOMAIN_STATUS` (not found → 404, invalid → 422, unavailable → 503; the most specific class wins). An unmapped domain error is a bug: it gets a 500 and an `unmapped_domain_error` log line. A test checks that every domain error is either mapped or listed as CLI-only. A route catches a domain error itself only when its response depends on it (the contact form re-renders with field errors). `HTTPException`, `RequestValidationError` (422) and any other exception (500; the server logs the traceback) get the same error page. Pages get `errors/error.html` with a `noindex` SEO context. htmx requests get `fragments/_error.html` with `HX-Retarget: #main-content` and `HX-Reswap: outerHTML`, because htmx 4 swaps error responses into the requesting element by default. Paths under `/api/` get JSON. Error copy per status lives in `_PAGES`.
- **Handling errors in the CLI**: invalid or unreadable post files become `InvalidPost` and are all reported before anything is written. `PostsUnavailable` during a sync is logged and exits 1, and the uncommitted transaction leaves the stored posts unchanged.
- **Root-level crawler files** (sitemap.xml, robots.txt, llms.txt) are rendered from `templates/seo/*.j2` by `routes/seo.py`. `sitemap.xml.j2` turns on autoescape explicitly, because `.j2` files aren't autoescaped by default.
- **Database is optional at runtime**: the engine is created on first use, so the app boots without `DATABASE_URL`. Without it the blog reads an empty in-memory repository, so every page and the sitemap still render. Queries live in adapters behind a feature module's Protocol and return its dataclasses, not ORM rows. Use cases judge "published" at `as_of`, which defaults to now; tests pass a fixed one.
- **Unfinished features** can be merged: keep the router out of `main.py`, the page out of `PAGE_META`, and the link out of the nav until it works.
- **Type-checking exceptions are file-level and explained**: `schema_org.py` turns off `reportIncompatibleVariableOverride` (each subclass narrows `type` for the discriminator). It's the only one; don't add new exceptions without a comment saying why.
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

Copy `.env.example` to `.env` for local settings; the app runs with it empty. An unknown key in `.env` stops the app at startup (it's likely a typo), and the error names the key but never its value (`hide_input_in_errors`). Tests never read `.env`: `tests/conftest.py` sets `PORTFOLIO_ENV_FILE=""` before importing the app, so they run the same on every machine; set it to a path to load a different dotenv file.

## Deployment

- `master` is production: Railway builds the `Dockerfile` on every push. Work on short-lived branches and merge by PR once CI passes.
- The container runs uvicorn from the venv (`uv sync --frozen --no-dev` at build time) with `--proxy-headers`, so `url_for` produces `https://` URLs behind Railway's proxy.
- Railway settings live in the dashboard (healthcheck path `/healthz`, "Wait for CI"). `railway.toml` is deprecated (stops being read 2026-12-01); generate `.railway/railway.py` with `railway config pull` if config-as-code is wanted.
- Postgres: set `DATABASE_URL` on Railway and set the pre-deploy command to `alembic upgrade head && python -m app.cli sync-posts`. A failed sync (an invalid post) fails the deploy and leaves the previous posts in place.

## Notes / Not Yet Built

- **Blog follow-ups**: full-text search (the `search_vector` column and GIN index are in place), an RSS/Atom feed, syntax highlighting for code blocks, and heading anchors.
- **Projects pages**: not started. A projects feature would follow the blog's shape: a `services/projects.py` feature module, a table, an adapter, routes, and a `for_project` SEO context (an earlier draft is in git history).
- **Admin**: not started. Posts are managed as files in `content/blog/`, so no admin is needed yet (an earlier GitHub-OAuth draft is in git history).
- **llms-full.txt**: not built; add a `RootFile` member and a route in `routes/seo.py` when it is.
- **Contact form**: shown only when `TURNSTILE_SITE_KEY` + `TURNSTILE_SECRET_KEY` are set and mail can go out (`RESEND_API_KEY`, or logged when `DEBUG`). Resend needs the sending domain (`CONTACT_FROM_EMAIL`) verified. The rate limit is per process; move it to Redis if the app runs more than one replica. Brand logos in `static/images/brands/` are the official files, unmodified.
- **Home page role cards**: not built (the placeholder loop was removed because it included a template that didn't exist). Add them as `components/_role_card.html`, with the home route passing `roles`.
- **JSON API**: none. Build only when a real consumer (RSS reader, CLI, mobile app) exists; the error handler already returns JSON under `/api/`.
