import sqlalchemy as sa
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api import router
from app.api.auth import get_token_auth_user
from app.api.errors import bad_request
from app.db import get_db, get_or_404
from app.models import User


def _url_builder(request: Request, name: str, **path_kwargs):
    """Return a callable that generates paginated URLs for a named route."""
    def builder(page: int, per_page: int) -> str:
        return str(request.url_for(name, **path_kwargs).include_query_params(
            page=page, per_page=per_page))
    return builder


@router.get('/users/{id}', name='get_user')
def get_user(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_token_auth_user),
):
    return get_or_404(db, User, id).to_dict()


@router.get('/users', name='get_users')
def get_users(
    request: Request,
    page: int = 1,
    per_page: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_token_auth_user),
):
    per_page = min(per_page, 100)
    return User.to_collection_dict(
        sa.select(User), db, page, per_page,
        _url_builder(request, 'get_users'))


@router.get('/users/{id}/followers', name='get_followers')
def get_followers(
    id: int,
    request: Request,
    page: int = 1,
    per_page: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_token_auth_user),
):
    per_page = min(per_page, 100)
    user = get_or_404(db, User, id)
    return User.to_collection_dict(
        user.followers.select(), db, page, per_page,
        _url_builder(request, 'get_followers', id=id))


@router.get('/users/{id}/following', name='get_following')
def get_following(
    id: int,
    request: Request,
    page: int = 1,
    per_page: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_token_auth_user),
):
    per_page = min(per_page, 100)
    user = get_or_404(db, User, id)
    return User.to_collection_dict(
        user.following.select(), db, page, per_page,
        _url_builder(request, 'get_following', id=id))


@router.post('/users', status_code=201, name='create_user')
def create_user(request: Request, data: dict, db: Session = Depends(get_db)):
    if 'username' not in data or 'email' not in data or 'password' not in data:
        return bad_request('must include username, email and password fields')
    if db.scalar(sa.select(User).where(User.username == data['username'])):
        return bad_request('please use a different username')
    if db.scalar(sa.select(User).where(User.email == data['email'])):
        return bad_request('please use a different email address')
    user = User()
    user.from_dict(data, new_user=True)
    db.add(user)
    db.commit()
    return JSONResponse(
        content=user.to_dict(),
        status_code=201,
        headers={'Location': str(request.url_for('get_user', id=user.id))})


@router.put('/users/{id}', name='update_user')
def update_user(
    id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_token_auth_user),
):
    if current_user.id != id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    user = get_or_404(db, User, id)
    if 'username' in data and data['username'] != user.username and \
            db.scalar(sa.select(User).where(User.username == data['username'])):
        return bad_request('please use a different username')
    if 'email' in data and data['email'] != user.email and \
            db.scalar(sa.select(User).where(User.email == data['email'])):
        return bad_request('please use a different email address')
    user.from_dict(data, new_user=False)
    db.commit()
    return user.to_dict()
