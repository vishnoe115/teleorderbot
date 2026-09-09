from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

import db


def create_web_app() -> FastAPI:
    app = FastAPI(
        title="AutoOrderTele",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/health")
    async def health():
        db_ok = db.healthcheck()
        return JSONResponse(
            {
                "ok": db_ok,
                "database": "ok" if db_ok else "error",
                "payment": "DANA_BUSINESS_QRIS",
            },
            status_code=200 if db_ok else 503,
        )

    return app
