from fastapi import APIRouter

router = APIRouter()

from app.main import routes  # noqa: E402, F401
