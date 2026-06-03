from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.api.errors import error_response


def _wants_json(request: Request) -> bool:
    accept = request.headers.get('Accept', '')
    return 'application/json' in accept and 'text/html' not in accept


def register_exception_handlers(app: FastAPI) -> None:
    from app.db import get_db_session
    from app.templates import render_error

    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        if _wants_json(request):
            return error_response(404)
        return HTMLResponse(render_error(request, 'errors/404.html'), status_code=404)

    @app.exception_handler(500)
    async def internal_error(request: Request, exc):
        try:
            db = get_db_session()
            db.rollback()
        except Exception:
            pass
        if _wants_json(request):
            return error_response(500)
        return HTMLResponse(render_error(request, 'errors/500.html'), status_code=500)
