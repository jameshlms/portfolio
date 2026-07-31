from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.features.blog.router import router as blog_router
from app.features.pages.router import router as pages_router

app = FastAPI()
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

app.include_router(pages_router)
app.include_router(blog_router)

