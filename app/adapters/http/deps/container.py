from typing import Annotated

from fastapi import Depends, Request

from app.container import Container


def get_container(request: Request) -> Container:
    """The Container create_app was given."""
    return request.app.state.container


AppContainer = Annotated[Container, Depends(get_container)]
