import sqlalchemy as sa
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBearer, HTTPBasicCredentials, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

basic_scheme = HTTPBasic(auto_error=False)
token_scheme = HTTPBearer(auto_error=False)


def get_basic_auth_user(
    credentials: HTTPBasicCredentials = Depends(basic_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            headers={'WWW-Authenticate': 'Basic'})
    user = db.scalar(sa.select(User).where(User.username == credentials.username))
    if user is None or not user.check_password(credentials.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            headers={'WWW-Authenticate': 'Basic'})
    return user


def get_token_auth_user(
    credentials: HTTPAuthorizationCredentials = Depends(token_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            headers={'WWW-Authenticate': 'Bearer'})
    user = User.check_token(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            headers={'WWW-Authenticate': 'Bearer'})
    return user
