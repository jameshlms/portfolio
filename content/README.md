# Content

## Blog posts (`blog/`)

One Markdown file per post. The file name is the URL slug:
`blog/my-first-post.md` is served at `/blog/my-first-post`, so use lowercase
letters, digits and hyphens.

```markdown
---
title: My first post                  # required
summary: One or two sentences.        # required, ≤300 chars; the meta description
tags: [python, data-engineering]      # optional; lowercase, hyphenated
published: 2026-11-07                 # optional; leave out for a draft
updated: 2026-11-20                   # optional; a meaningful revision
---

The post starts here. The page already shows the title as the `<h1>`,
so start sections at `##`.
```

- **Drafts** (no `published`) are stored but never shown. A `published` date in the
  future is shown from that date on.
- Dates are UTC; a bare date means midnight. A time can be given as
  `2026-11-07T09:30:00Z`.
- Markdown is CommonMark plus tables and ~~strikethrough~~. Raw HTML is not rendered.

### Charts

Interactive Plotly charts go in a folder named after the post, as figure JSON:

```python
fig.write_json("content/blog/my-first-post/query-times.json")
```

and are placed with a `plotly` fence: the first line names the file, any further
lines are the caption.

````markdown
```plotly
query-times.json
Median query time before and after partitioning.
```
````

A missing or invalid figure fails the sync like any other error. Pages load
plotly.js only when the post has a chart. The site is dark, so the `plotly_dark`
template with a transparent background (`paper_bgcolor="rgba(0,0,0,0)"`) fits best.
- Deleting a file removes the post on the next sync.

Every deploy runs `python -m app.cli sync-posts`, which checks every file and
writes nothing if any is invalid. Run it locally against a dev database to check
a post before pushing:

```bash
uv run python -m app.cli sync-posts
```
