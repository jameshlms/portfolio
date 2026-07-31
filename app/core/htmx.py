from fastapi import Request


def is_htmx(r: Request) -> bool:
    return r.headers.get("HX-Request") == "true"
