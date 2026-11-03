from fastapi import APIRouter

from app.paths import Reserved

router = APIRouter(include_in_schema=False)


@router.get(Reserved.HEALTH)
async def health() -> dict[str, str]:
    """Liveness for Railway's deploy healthcheck: answers once the app can serve requests."""
    return {"status": "ok"}
