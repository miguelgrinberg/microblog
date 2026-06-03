from fastapi import Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api import router
from app.api.auth import get_basic_auth_user, get_token_auth_user
from app.db import get_db
from app.models import User


@router.post('/tokens', name='get_token')
def get_token(
    current_user: User = Depends(get_basic_auth_user),
    db: Session = Depends(get_db),
):
    token = current_user.get_token()
    db.commit()
    return {'token': token}


@router.delete('/tokens', status_code=204, name='revoke_token')
def revoke_token(
    current_user: User = Depends(get_token_auth_user),
    db: Session = Depends(get_db),
):
    current_user.revoke_token()
    db.commit()
    return Response(status_code=204)
