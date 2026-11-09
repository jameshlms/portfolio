"""The blog's PostRepository for one request, opened from the Container's scope."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from app.adapters.http.deps.container import AppContainer
from app.ports.driven.blog import PostRepository


async def get_post_repository(container: AppContainer) -> AsyncIterator[PostRepository]:
    async with container.posts() as repository:
        yield repository


Posts = Annotated[PostRepository, Depends(get_post_repository)]
