from app.auth.twilio_verify import check_verification_token, request_verification_token
from flask import render_template, redirect, url_for, flash, request, session
from werkzeug.urls import url_parse
from flask_login import login_user, login_required, logout_user, current_user
from flask_babel import _
from app import db
from app.auth import bp
from app.auth.forms import Confirm2faForm, Disable2faForm, Enable2faForm, LoginForm, RegistrationForm, \
    ResetPasswordRequestForm, ResetPasswordForm
from app.models import User
from app.auth.email import send_password_reset_email


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash(_('Invalid username or password'))
            return redirect(url_for('auth.login'))
        next_page = request.args.get('next')
        if user.two_factor_enabled():
            request_verification_token(user.verification_phone)
            session['username'] = user.username
            session['phone'] = user.verification_phone
            return redirect(url_for(
                'auth.verify_2fa', next=next_page,
                remember='1' if form.remember_me.data else '0'))
        login_user(user, remember=form.remember_me.data)
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)
    return render_template('auth/login.html', title=_('Sign In'), form=form)


@bp.route('/verify2fa', methods=['GET', 'POST'])
def verify_2fa():
    form = Confirm2faForm()
    if form.validate_on_submit():
        phone = session['phone']
        if check_verification_token(phone, form.token.data):
            del session['phone']
            if current_user.is_authenticated:
                current_user.verification_phone = phone
                db.session.commit()
                flash('Two-factor authentication is now enabled')
                return redirect(url_for('main.index'))
            else:
                username = session['username']
                del session['username']
                user = User.query.filter_by(username=username).first()
                next_page = request.args.get('next')
                remember = request.args.get('remember', '0') == '1'
                login_user(user, remember=remember)
                return redirect(next_page)
        form.token.errors.append('Invalid token')
    return render_template('auth/verify_2fa.html', form=form)


@bp.route('/enable_2fa', methods=['GET', 'POST'])
@login_required
def enable_2fa():
    form = Enable2faForm()
    if form.validate_on_submit():
        session['phone'] = form.verification_phone.data
        request_verification_token(session['phone'])
        return redirect(url_for('auth.verify_2fa'))
    return render_template('auth/enable_2fa.html', form=form)


@bp.route('/disable_2fa', methods=['GET', 'POST'])
@login_required
def disable_2fa():
    form = Disable2faForm()
    if form.validate_on_submit():
        current_user.verification_phone = None
        db.session.commit()
        flash('Two-factor authentication is now disabled.')
        return redirect(url_for('main.index'))
    return render_template('auth/disable_2fa.html', form=form)


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(_('Congratulations, you are now a registered user!'))
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', title=_('Register'),
                           form=form)


@bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash(
            _('Check your email for the instructions to reset your password'))
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password_request.html',
                           title=_('Reset Password'), form=form)


@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('main.index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash(_('Your password has been reset.'))
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form)
