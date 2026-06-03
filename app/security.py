from fastapi import Request
from sqlalchemy.orm import Session


def flash(request: Request, message: str, category: str = 'message') -> None:
    flashes = list(request.session.get('_flashes', []))
    flashes.append((category, str(message)))
    request.session['_flashes'] = flashes


def get_flashed_messages(request: Request, with_categories: bool = False):
    flashes = list(request.session.get('_flashes', []))
    request.session['_flashes'] = []
    if with_categories:
        return flashes
    return [msg for _cat, msg in flashes]


def login_user(request: Request, user_id: int) -> None:
    request.session['_user_id'] = user_id


def logout_user(request: Request) -> None:
    request.session.pop('_user_id', None)


def get_current_user(request: Request, db: Session):
    user_id = request.session.get('_user_id')
    if user_id is None:
        return None
    from app.models import User
    return db.get(User, user_id)
