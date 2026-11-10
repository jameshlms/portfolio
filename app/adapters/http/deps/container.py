from typing import Annotated

from fastapi import Depends, Request

from app.container import Container
from app.ports.driven.clock import Clock


def get_container(request: Request) -> Container:
    """The Container create_app was given."""
    return request.app.state.container


def get_clock(container: Annotated[Container, Depends(get_container)]) -> Clock:
    return container.clock


AppContainer = Annotated[Container, Depends(get_container)]
AppClock = Annotated[Clock, Depends(get_clock)]
