from fastapi import Request


def is_htmx(r: Request) -> bool:
    """
    Check if the request is an HTMX request.

    Args:
        r (Request): The incoming HTTP request.

    Returns:
        bool: True if the request is an HTMX request, False otherwise.
    """
    return r.headers.get("HX-Request") == "true"
