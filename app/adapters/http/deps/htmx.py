from collections.abc import Mapping
from typing import Annotated

from fastapi import Depends, Header


def wants_fragment(headers: Mapping[str, str]) -> bool:
    """True when an htmx request should get a fragment, not a full page.

    Boosted requests and history restores (Back/Forward) need the whole page.
    """
    return (
        headers.get("hx-request") == "true"
        and headers.get("hx-boosted") != "true"
        and headers.get("hx-history-restore-request") != "true"
    )


def _is_htmx(
    hx_request: Annotated[str | None, Header()] = None,
    hx_boosted: Annotated[str | None, Header()] = None,
    hx_history_restore_request: Annotated[str | None, Header()] = None,
) -> bool:
    headers = {
        "hx-request": hx_request,
        "hx-boosted": hx_boosted,
        "hx-history-restore-request": hx_history_restore_request,
    }
    return wants_fragment({k: v for k, v in headers.items() if v is not None})


IsHtmx = Annotated[bool, Depends(_is_htmx)]
