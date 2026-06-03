from urllib.parse import urlsplit
import sqlalchemy as sa
from fastapi import Depends, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.auth import router
from app.auth.forms import LoginForm, RegistrationForm, ResetPasswordRequestForm, ResetPasswordForm
from app.auth.email import send_password_reset_email
from app.db import get_db
from app.i18n import _
from app.models import User
from app.security import flash, get_current_user, login_user, logout_user
from app.templates import render


@router.api_route('/login', methods=['GET', 'POST'], response_class=HTMLResponse, name='login')
async def login(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    if current_user is not None:
        return RedirectResponse(url='/', status_code=303)

    form_data = await request.form() if request.method == 'POST' else None
    form = LoginForm(formdata=form_data, meta={'session': request.session})

    if request.method == 'POST' and form.validate():
        user = db.scalar(sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash(request, _('Invalid username or password'))
            return RedirectResponse(url='/auth/login', status_code=303)
        login_user(request, user.id)
        next_page = request.query_params.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = '/'
        return RedirectResponse(url=next_page, status_code=303)

    return render(request, db, 'auth/login.html', title=_('Sign In'), form=form)


@router.get('/logout', name='logout')
async def logout(request: Request):
    logout_user(request)
    return RedirectResponse(url='/', status_code=303)


@router.api_route('/register', methods=['GET', 'POST'], response_class=HTMLResponse, name='register')
async def register(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    if current_user is not None:
        return RedirectResponse(url='/', status_code=303)

    form_data = await request.form() if request.method == 'POST' else None
    form = RegistrationForm(formdata=form_data, meta={'session': request.session})

    if request.method == 'POST' and form.validate():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.add(user)
        db.commit()
        flash(request, _('Congratulations, you are now a registered user!'))
        return RedirectResponse(url='/auth/login', status_code=303)

    return render(request, db, 'auth/register.html', title=_('Register'), form=form)


@router.api_route('/reset_password_request', methods=['GET', 'POST'],
                  response_class=HTMLResponse, name='reset_password_request')
async def reset_password_request(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    if current_user is not None:
        return RedirectResponse(url='/', status_code=303)

    form_data = await request.form() if request.method == 'POST' else None
    form = ResetPasswordRequestForm(formdata=form_data, meta={'session': request.session})

    if request.method == 'POST' and form.validate():
        user = db.scalar(sa.select(User).where(User.email == form.email.data))
        if user:
            send_password_reset_email(user)
        flash(request, _('Check your email for the instructions to reset your password'))
        return RedirectResponse(url='/auth/login', status_code=303)

    return render(request, db, 'auth/reset_password_request.html',
                  title=_('Reset Password'), form=form)


@router.api_route('/reset_password/{token}', methods=['GET', 'POST'],
                  response_class=HTMLResponse, name='reset_password')
async def reset_password(token: str, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    if current_user is not None:
        return RedirectResponse(url='/', status_code=303)

    user = User.verify_reset_password_token(token)
    if not user:
        return RedirectResponse(url='/', status_code=303)

    form_data = await request.form() if request.method == 'POST' else None
    form = ResetPasswordForm(formdata=form_data, meta={'session': request.session})

    if request.method == 'POST' and form.validate():
        user.set_password(form.password.data)
        db.commit()
        flash(request, _('Your password has been reset.'))
        return RedirectResponse(url='/auth/login', status_code=303)

    return render(request, db, 'auth/reset_password.html', form=form)
