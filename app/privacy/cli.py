"""ЛР4: CLI-команди для живої демонстрації (`flask privacy ...`).
Усі дані - СИНТЕТИЧНІ (домен .test зарезервовано RFC 2606, код 00 не існує).
"""
import logging
import secrets
import sys
from dataclasses import dataclass, field

import click
import sqlalchemy as sa

from app import db
from app.models import (User, Post, Message, Notification, UserConsent,
                        ConsentEvent, AnalyticsEvent, MarketingDispatch,
                        AuditEvent, followers)
from app.privacy.secure_logging import make_secure_handler

DEMO_USERS = [
    # username, email, phone, password, officer
    ('olena_demo', 'olena.demo@example.test', '+380 00 123 45 67',
     'Demo-Passw0rd-1', False),
    ('taras_demo', 'taras.demo@example.test', '+380 00 765 43 21',
     'Demo-Passw0rd-2', False),
    ('dpo_demo', 'dpo.demo@example.test', None, 'Demo-Passw0rd-3', True),
]


@dataclass
class ContactDTO:
    email: str
    phone: str


@dataclass
class RegistrationDTO:
    username: str
    password: str
    contact: ContactDTO
    meta: dict = field(default_factory=dict)


def register(bp):
    @bp.cli.group()
    def privacy():
        """ЛР4: Privacy Engineering demo commands."""

    @privacy.command('seed-demo')
    @click.option('--env', 'as_env', is_flag=True,
                  help='Вивести у форматі shell-змінних (для demo-скрипта)')
    def seed_demo(as_env):
        """Створити синтетичних користувачів із записами в усіх таблицях."""
        users = {}
        for username, email, phone, pwd, officer in DEMO_USERS:
            u = db.session.scalar(sa.select(User).where(
                User.username == username))
            if u is None:
                u = User(username=username, email=email)
                db.session.add(u)
            u.phone, u.can_manage_privacy = phone, officer
            u.about_me = f'Synthetic profile {username}'
            u.set_password(pwd)
            users[username] = u
        db.session.commit()
        o, t = users['olena_demo'], users['taras_demo']
        if not db.session.scalar(sa.select(Post).where(Post.user_id == o.id)):
            db.session.add_all([
                Post(body='Hello from Olena (synthetic)', author=o,
                     language='en'),
                Post(body='Write me at olena.demo@example.test', author=o),
                Message(author=o, recipient=t, body='Hi Taras, call me at '
                                                    '+380 00 123 45 67'),
                Message(author=t, recipient=o, body='Hi Olena!'),
            ])
            o.follow(t)
            t.follow(o)
            o.add_notification('unread_message_count', 1)
        db.session.commit()
        if as_env:
            for username, *_ in DEMO_USERS:
                u = users[username]
                key = username.split('_')[0].upper()
                click.echo(f'{key}_ID={u.id}')
                click.echo(f'{key}_TOKEN={u.get_token(expires_in=8 * 3600)}')
            db.session.commit()
            return
        click.echo('Synthetic users (password -> get token via POST '
                   '/api/tokens with Basic auth):')
        for username, *_ in DEMO_USERS:
            u = users[username]
            tok = u.get_token(expires_in=8 * 3600)
            click.echo(f'  id={u.id:<3} {username:<11} token={tok}'
                       f'{"  (privacy officer)" if u.can_manage_privacy else ""}')
        db.session.commit()

    @privacy.command('log-demo')
    @click.option('--json', 'as_json', is_flag=True, help='JSON-формат логу')
    @click.option('--show-raw', is_flag=True,
                  help='Показати, що потрапило б у лог БЕЗ захисту')
    def log_demo(as_json, show_raw):
        """Операція, що обробляє email/телефон/token/password."""
        log = logging.getLogger('app.registration')
        log.setLevel(logging.INFO)
        log.propagate = False
        log.handlers = [make_secure_handler(logging.StreamHandler(sys.stdout),
                                            'json' if as_json else 'text')]
        # синтетичні секрети генеруються під час запуску - у коді їх немає
        token = secrets.token_hex(16)
        dto = RegistrationDTO('olena_demo', 'Demo-Passw0rd-1',
                              ContactDTO('olena.demo@example.test',
                                         '+380 00 123 45 67'),
                              {'api_key': 'sk_demo_' + secrets.token_hex(8)})
        raw = [
            f'User registered email={dto.contact.email} '
            f'phone={dto.contact.phone} password={dto.password}',
            f'Issued token: {token}; Authorization: Bearer {token}',
            f'Payload: {dto!r}',
        ]
        if show_raw:
            click.secho('--- БЕЗ захисту (так виглядав би лог) ---', fg='red')
            for line in raw:
                click.echo(line)
            click.secho('--- З централізованим sanitization ---', fg='green')
        log.info('User registered email=%s phone=%s password=%s',
                 dto.contact.email, dto.contact.phone, dto.password)
        log.info('Issued token: %s; Authorization: Bearer %s', token, token)
        log.info('Payload: %r', dto)  # вкладений DTO
        log.info('registration_completed', extra={
            'operation': 'user.register', 'result': 'SUCCESS',
            'email': dto.contact.email, 'phone': dto.contact.phone,
            'access_token': token, 'request': {'password': dto.password}})
        try:
            raise ValueError(f'SMTP rejected {dto.contact.email}: '
                             f'auth token={token}')
        except ValueError:
            log.exception('Registration e-mail failed')

    @privacy.command('db-state')
    @click.argument('user_id', type=int)
    def db_state(user_id):
        """Стан УСІХ пов'язаних записів користувача в БД (до/після)."""
        u = db.session.get(User, user_id)
        if u is None:
            click.echo('no such user')
            return
        cols = ['id', 'username', 'email', 'phone', 'about_me',
                'password_hash', 'token', 'anonymized_at']
        click.secho('user', bold=True)
        for c in cols:
            v = getattr(u, c)
            if c == 'password_hash' and v:
                v = v[:16] + '...'
            click.echo(f'  {c:<14} {v}')

        def section(title, stmt, fmt):
            rows = db.session.scalars(stmt).all()
            click.secho(f'{title} ({len(rows)})', bold=True)
            for r in rows:
                click.echo('  ' + fmt(r))

        section('post', sa.select(Post).where(Post.user_id == user_id),
                lambda p: f'#{p.id} {p.timestamp} {p.body!r}')
        section('message', sa.select(Message).where(sa.or_(
            Message.sender_id == user_id, Message.recipient_id == user_id)),
            lambda m: f'#{m.id} {m.sender_id}->{m.recipient_id} {m.body!r}')
        n = db.session.scalar(sa.select(sa.func.count()).select_from(
            followers).where(sa.or_(followers.c.follower_id == user_id,
                                    followers.c.followed_id == user_id)))
        click.secho(f'followers links ({n})', bold=True)
        section('notification', sa.select(Notification).where(
            Notification.user_id == user_id), lambda x: f'{x.name}')
        section('user_consent', sa.select(UserConsent).where(
            UserConsent.user_id == user_id), lambda c:
            f'{c.purpose} {c.status} v{c.policy_version} src={c.source}')
        section('consent_event', sa.select(ConsentEvent).where(
            ConsentEvent.user_id == user_id), lambda e:
            f'{e.occurred_at} {e.action} {e.purpose} src={e.source}')
        section('analytics_event', sa.select(AnalyticsEvent).where(
            AnalyticsEvent.user_id == user_id), lambda a: a.name)
        section('marketing_dispatch', sa.select(MarketingDispatch).where(
            MarketingDispatch.user_id == user_id), lambda d: d.campaign)
        from app.privacy.audit import subject_ref
        section('audit_event', sa.select(AuditEvent).where(
            AuditEvent.subject_ref == subject_ref(user_id)), lambda a:
            f'{a.occurred_at} {a.action} {a.result} actor={a.actor_ref} '
            f'cid={a.correlation_id} {a.details_json}')
        # звітний запит, що НЕ повинен падати після анонімізації
        rows = db.session.execute(
            sa.select(User.username, sa.func.count(Post.id))
            .join(Post, Post.user_id == User.id).group_by(User.username)
        ).all()
        click.secho('report: posts per author', bold=True)
        for name, cnt in rows:
            click.echo(f'  {name:<22} {cnt}')

    @privacy.command('run-digest-job')
    @click.argument('user_id', type=int)
    def run_digest_job(user_id):
        """Виконати background job маркетингової розсилки (як rq worker)."""
        from app.privacy.consent import marketing_digest_job
        click.echo(f'job result: {marketing_digest_job(user_id)}')
