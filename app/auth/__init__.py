from fastapi import APIRouter

router = APIRouter()

from app.auth import routes  # noqa: E402, F401
