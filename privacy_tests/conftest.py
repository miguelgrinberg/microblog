"""Спільні fixtures ЛР4. Усі значення СИНТЕТИЧНІ (домен .test, код 00)."""
import base64
import io
import logging

import pytest

from app import create_app, db
from app.models import (User, Post, Message, UserConsent, ConsentEvent,
                        AnalyticsEvent, MarketingDispatch)
from app.privacy.secure_logging import make_secure_handler
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    ELASTICSEARCH_URL = None
    MAIL_SERVER = None
    SECRET_KEY = 'test-only-secret-key'


# Контрольні тестові дані (за ними перевіряються маскування, повнота
# експорту та результат анонімізації)
OLENA = dict(username='olena_test', email='olena.control@example.test',
             phone='+380 00 111 22 33', password='Ctrl-Passw0rd-Olena',
             about_me='CONTROL-ABOUT-olena')
TARAS = dict(username='taras_test', email='taras.control@example.test',
             phone='+380 00 444 55 66', password='Ctrl-Passw0rd-Taras',
             about_me='CONTROL-ABOUT-taras')
DPO = dict(username='dpo_test', email='dpo.control@example.test',
           phone=None, password='Ctrl-Passw0rd-Dpo', about_me=None)
POST_BODY = 'CONTROL-POST olena writes from olena.control@example.test'
MSG_TO_TARAS = 'CONTROL-MSG-1 call me +380 00 111 22 33'
MSG_FROM_TARAS = 'CONTROL-MSG-2 hi olena'


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def make_user(spec, officer=False):
    u = User(username=spec['username'], email=spec['email'],
             phone=spec['phone'], about_me=spec['about_me'],
             can_manage_privacy=officer)
    u.set_password(spec['password'])
    db.session.add(u)
    db.session.commit()
    token = u.get_token()
    db.session.commit()
    return u, token


def bearer(token):
    return {'Authorization': f'Bearer {token}'}


def basic(username, password):
    raw = base64.b64encode(f'{username}:{password}'.encode()).decode()
    return {'Authorization': f'Basic {raw}'}


@pytest.fixture
def users(app):
    olena, t_olena = make_user(OLENA)
    taras, t_taras = make_user(TARAS)
    dpo, t_dpo = make_user(DPO, officer=True)
    return {'olena': (olena, t_olena), 'taras': (taras, t_taras),
            'dpo': (dpo, t_dpo)}


@pytest.fixture
def seeded(users):
    """Olena має записи в КОЖНОМУ джерелі з PII inventory."""
    olena, taras = users['olena'][0], users['taras'][0]
    db.session.add(Post(body=POST_BODY, author=olena, language='en'))
    db.session.add(Message(author=olena, recipient=taras, body=MSG_TO_TARAS))
    db.session.add(Message(author=taras, recipient=olena,
                           body=MSG_FROM_TARAS))
    olena.follow(taras)
    taras.follow(olena)
    olena.add_notification('unread_message_count', 1)
    db.session.add(UserConsent(user_id=olena.id, purpose='OPTIONAL_ANALYTICS',
                               status='GRANTED', policy_version='2026-10-01',
                               source='web'))
    db.session.add(ConsentEvent(user_id=olena.id, purpose='OPTIONAL_ANALYTICS',
                                action='GRANT', policy_version='2026-10-01',
                                source='web'))
    db.session.add(AnalyticsEvent(user_id=olena.id, name='CONTROL-EVENT'))
    db.session.add(MarketingDispatch(user_id=olena.id, campaign='CONTROL-CMP',
                                     policy_version='2026-10-01'))
    db.session.commit()
    return users


@pytest.fixture
def log_capture(app):
    """Перехоплює РЕАЛЬНИЙ output застосунку: той самий secure handler,
    що й у production (text + json), підключений до app.logger."""
    streams = {'text': io.StringIO(), 'json': io.StringIO()}
    handlers = [make_secure_handler(logging.StreamHandler(streams[f]), f)
                for f in streams]
    for h in handlers:
        app.logger.addHandler(h)
    app.logger.setLevel(logging.INFO)
    yield streams
    for h in handlers:
        app.logger.removeHandler(h)


def db_dump():
    """Повний текстовий дамп БД (усі таблиці) - для пошуку залишків PII."""
    raw = db.session.connection().connection.dbapi_connection
    return '\n'.join(raw.iterdump())
