from typing import Annotated

from fastapi import Depends, Header


def _is_htmx(
    hx_request: Annotated[str | None, Header()] = None,
    hx_boosted: Annotated[str | None, Header()] = None,
    hx_history_restore_request: Annotated[str | None, Header()] = None,
) -> bool:
    """True when the response should be a fragment, not a full page."""
    return (
        hx_request == "true"
        and hx_boosted != "true"
        and hx_history_restore_request != "true"
    )

IsHtmx = Annotated[bool, Depends(_is_htmx)]