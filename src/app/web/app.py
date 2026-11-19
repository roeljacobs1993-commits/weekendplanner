"""FastAPI application."""

from fastapi import FastAPI

import app as package


def create_app() -> FastAPI:
    web = FastAPI(title="Weekendplanner")

    @web.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": package.__version__}

    return web
