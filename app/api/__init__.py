from fastapi import APIRouter

router = APIRouter()

from app.api import users, errors, tokens  # noqa: E402, F401
