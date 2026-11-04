"""Завдання 3. Right to Erasure (GDPR Art. 17) - Anonymization Workflow.

Політика (ERASURE_POLICY) визначає дію для КОЖНОЇ сутності, пов'язаної з
суб'єктом. Workflow виконується в ОДНІЙ транзакції: або всі кроки, або
жодного (rollback). Повторний запуск - no-op (ідемпотентність).
"""
import secrets
from datetime import datetime, timezone

import sqlalchemy as sa
from flask import current_app

from app import db
from app.models import (User, Post, Message, Notification, Task, UserConsent,
                        ConsentEvent, AnalyticsEvent, MarketingDispatch,
                        followers)
from app.privacy.audit import record_audit

ERASED_POST = '[deleted]'
ERASED_MESSAGE = '[message removed: participant deleted their account]'

ERASURE_POLICY = [
    # entity, action, rationale
    ('user', 'ANONYMIZE',
     'Row kept as neutral anonymous subject so FKs stay valid; ALL PII '
     'columns replaced by random values / NULL; credentials destroyed.'),
    ('post', 'RETAIN+ANONYMIZE',
     'Retention rule (modelled): aggregate timeline statistics. Row kept, '
     'body replaced, timestamp coarsened to day to prevent re-identification '
     'by activity pattern.'),
    ('message', 'RETAIN+ANONYMIZE',
     'Joint record of two parties: counterpart keeps thread structure, '
     'body (may contain subject PII) is removed.'),
    ('followers', 'DELETE', 'Social graph reveals identity; no retention basis.'),
    ('notification', 'DELETE', 'Operational data, payload may contain PII.'),
    ('task', 'DELETE', 'Background job records of the subject.'),
    ('analytics_event', 'DELETE', 'Optional behavioural data.'),
    ('marketing_dispatch', 'DELETE', 'Marketing history, no retention basis.'),
    ('user_consent', 'RETAIN+WITHDRAW',
     'Accountability (Art. 7(1)): evidence of consent kept, contains no PII, '
     'all purposes set to WITHDRAWN.'),
    ('consent_event', 'RETAIN',
     'Append-only proof; REVOKE events with source=erasure are added.'),
    ('audit_event', 'RETAIN',
     'Contains only pseudonymous refs and counters, never PII values.'),
    ('application logs', 'SKIP',
     'Protected by secure logging (Task 1): PII never reaches logs.'),
]


class ErasureResult(dict):
    pass


def _random_identity():
    token = secrets.token_hex(16)  # криптографічно випадково, НЕ похідне від PII
    return f'deleted-{token[:12]}', f'deleted-{token}@anon.local'


# --- окремі кроки (окремі функції - щоб тест міг змоделювати збій) ---------

def _anonymize_user(user, now):
    username, email = _random_identity()
    user.username, user.email = username, email
    user.phone = user.about_me = user.password_hash = None
    user.token = user.token_expiration = None
    user.last_seen = user.last_message_read_time = None
    user.can_manage_privacy = False
    user.anonymized_at = now
    return 1


def _anonymize_posts(user):
    n = 0
    for post in db.session.scalars(sa.select(Post)
                                   .where(Post.user_id == user.id)):
        post.body = ERASED_POST
        ts = post.timestamp
        post.timestamp = ts.replace(hour=0, minute=0, second=0, microsecond=0)
        n += 1
    return n


def _anonymize_messages(user):
    res = db.session.execute(
        sa.update(Message)
        .where(sa.or_(Message.sender_id == user.id,
                      Message.recipient_id == user.id))
        .values(body=ERASED_MESSAGE))
    return res.rowcount


def _delete_followers(user):
    res = db.session.execute(sa.delete(followers).where(sa.or_(
        followers.c.follower_id == user.id,
        followers.c.followed_id == user.id)))
    return res.rowcount


def _delete_where(model, user):
    return db.session.execute(
        sa.delete(model).where(model.user_id == user.id)).rowcount


def _withdraw_consents(user, now):
    n = 0
    for c in db.session.scalars(sa.select(UserConsent)
                                .where(UserConsent.user_id == user.id)):
        if c.status != 'WITHDRAWN':
            c.status, c.withdrawn_at = 'WITHDRAWN', now
            db.session.add(ConsentEvent(
                user_id=user.id, purpose=c.purpose, action='REVOKE',
                policy_version=c.policy_version, source='erasure',
                occurred_at=now))
            n += 1
        c.source, c.updated_at = 'erasure', now
    return n


STEPS = [
    ('user', lambda u, now: _anonymize_user(u, now)),
    ('post', lambda u, now: _anonymize_posts(u)),
    ('message', lambda u, now: _anonymize_messages(u)),
    ('followers', lambda u, now: _delete_followers(u)),
    ('notification', lambda u, now: _delete_where(Notification, u)),
    ('task', lambda u, now: _delete_where(Task, u)),
    ('analytics_event', lambda u, now: _delete_where(AnalyticsEvent, u)),
    ('marketing_dispatch', lambda u, now: _delete_where(MarketingDispatch, u)),
    ('user_consent', lambda u, now: _withdraw_consents(u, now)),
]


def anonymize_subject(subject_id, actor_id):
    """Атомарний та ідемпотентний workflow. Повертає ErasureResult."""
    user = db.session.get(User, subject_id)
    if user.anonymized_at is not None:
        record_audit('privacy.anonymize', actor_id, subject_id, 'NOOP')
        db.session.commit()
        return ErasureResult(status='already_anonymized',
                             anonymized_at=user.anonymized_at)

    now = datetime.now(timezone.utc)
    affected = {}
    try:
        for entity, step in STEPS:
            affected[entity] = step(user, now)
        # audit у ТІЙ САМІЙ транзакції: факт + лічильники, без значень
        record_audit('privacy.anonymize', actor_id, subject_id, 'SUCCESS',
                     details={'affected': affected})
        db.session.commit()
    except Exception:
        db.session.rollback()  # жодного часткового стану
        current_app.logger.exception('privacy.anonymize failed; rolled back')
        record_audit('privacy.anonymize', actor_id, subject_id, 'FAILED',
                     details={'failed_after': list(affected)})
        db.session.commit()
        raise
    return ErasureResult(status='anonymized', anonymized_at=now,
                         affected=affected)
