"""Reads blog posts from Markdown files with YAML front matter (content/blog/*.md).

The file name is the slug: content/blog/my-first-post.md -> /blog/my-first-post.
Chart figures for a post live in a folder of the same name:
content/blog/my-first-post/*.json.
"""

from dataclasses import dataclass
from pathlib import Path

import frontmatter
import yaml  # python-frontmatter's YAML parser; its errors are what a bad header raises

from app.domain.blog import PostSource, parse_post
from app.domain.errors import InvalidPost


@dataclass(frozen=True)
class PostFiles:
    posts: tuple[PostSource, ...]
    invalid: tuple[InvalidPost, ...]


def read_post_files(directory: Path) -> PostFiles:
    """Every *.md file in `directory`, checked. Raises NotADirectoryError if it's missing."""
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    results = tuple(_read(path) for path in sorted(directory.glob("*.md")))
    return PostFiles(
        posts=tuple(r for r in results if isinstance(r, PostSource)),
        invalid=tuple(r for r in results if isinstance(r, InvalidPost)),
    )


def _read(path: Path) -> PostSource | InvalidPost:
    try:
        document = frontmatter.loads(path.read_text(encoding="utf-8"))
        return parse_post(
            path.stem, document.metadata, document.content, _figures(path)
        )
    except yaml.YAMLError as e:
        return InvalidPost(path.stem, {"front matter": str(e)})
    except UnicodeDecodeError as e:
        return InvalidPost(path.stem, {"file": f"Not UTF-8 text: {e.reason}."})
    except OSError as e:
        return InvalidPost(path.stem, {"file": f"Can't be read: {e.strerror or e}."})
    except InvalidPost as e:
        return e


def _figures(post_path: Path) -> dict[str, str]:
    folder = post_path.with_suffix("")
    return {
        f.name: f.read_text(encoding="utf-8") for f in sorted(folder.glob("*.json"))
    }
