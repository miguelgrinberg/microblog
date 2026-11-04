"""Завдання 2. Right of Access (GDPR Art. 15) - Personal Data Export.

Збирає дані суб'єкта з УСІХ джерел, визначених у PII inventory.
Кожна секція - явний allow-list полів (мінімізація by design): нове поле
в моделі НЕ потрапить в експорт, поки його свідомо не додадуть сюди.
"""
from datetime import datetime, timezone

import sqlalchemy as sa

from app import db
from app.models import (User, Post, Message, Notification, Task, UserConsent,
                        ConsentEvent, AnalyticsEvent, MarketingDispatch,
                        followers)

SCHEMA = 'microblog.personal-data-export'
SCHEMA_VERSION = '1.0'

# Поля, що НІКОЛИ не повертаються (documented exclusions)
EXCLUDED_FIELDS = [
    {'field': 'user.password_hash', 'reason': 'security credential'},
    {'field': 'user.token', 'reason': 'API access token (secret)'},
    {'field': 'user.token_expiration', 'reason': 'security session metadata'},
    {'field': 'user.can_manage_privacy', 'reason': 'internal security flag'},
    {'field': 'password reset JWT', 'reason': 'not stored; one-time secret'},
    {'field': 'audit_event', 'reason': 'security log; contains no PII, '
                                       'only pseudonymous refs'},
    {'field': 'other users\' email / ids', 'reason': 'data of other subjects'},
]


def iso(dt):
    """Однозначний формат часу: ISO 8601, завжди UTC з offset +00:00."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec='seconds')


def _profile(u):
    return {'username': u.username, 'email': u.email, 'phone': u.phone,
            'about_me': u.about_me, 'last_seen': iso(u.last_seen),
            'avatar_url': u.avatar(128),
            'anonymized_at': iso(u.anonymized_at)}


def _settings(u):
    return {
        'items': {'last_message_read_time': iso(u.last_message_read_time)},
        '_note': 'UI language is not stored; it is derived per request '
                 'from the Accept-Language header.',
    }


def _usernames(stmt):
    return sorted(db.session.scalars(stmt).all())


def _social_graph(u):
    following = sa.select(User.username).join(
        followers, followers.c.followed_id == User.id).where(
        followers.c.follower_id == u.id)
    followed_by = sa.select(User.username).join(
        followers, followers.c.follower_id == User.id).where(
        followers.c.followed_id == u.id)
    # лише публічні username, без email/id інших людей (мінімізація)
    return {'following': _usernames(following),
            'followers': _usernames(followed_by)}


def _rows(stmt, mapper):
    return [mapper(r) for r in db.session.scalars(stmt)]


def collect(u):
    def msg_sent(m):
        return {'id': m.id, 'to': m.recipient.username, 'body': m.body,
                'timestamp': iso(m.timestamp)}

    def msg_received(m):
        return {'id': m.id, 'from': m.author.username, 'body': m.body,
                'timestamp': iso(m.timestamp)}

    data = {
        'profile': _profile(u),
        'settings': _settings(u),
        'social_graph': _social_graph(u),
        'posts': _rows(sa.select(Post).where(Post.user_id == u.id)
                       .order_by(Post.id), lambda p: {
            'id': p.id, 'body': p.body, 'language': p.language,
            'timestamp': iso(p.timestamp)}),
        'messages': {
            'sent': _rows(sa.select(Message).where(Message.sender_id == u.id)
                          .order_by(Message.id), msg_sent),
            'received': _rows(sa.select(Message)
                              .where(Message.recipient_id == u.id)
                              .order_by(Message.id), msg_received),
        },
        'notifications': _rows(
            sa.select(Notification).where(Notification.user_id == u.id)
            .order_by(Notification.id), lambda n: {
                'name': n.name, 'payload': n.get_data(),
                'timestamp': iso(datetime.fromtimestamp(n.timestamp,
                                                        timezone.utc))}),
        'tasks': _rows(sa.select(Task).where(Task.user_id == u.id)
                       .order_by(Task.id), lambda t: {
            'name': t.name, 'description': t.description,
            'complete': t.complete}),
        'consents': {
            'current': _rows(sa.select(UserConsent)
                             .where(UserConsent.user_id == u.id)
                             .order_by(UserConsent.purpose), lambda c: {
                'purpose': c.purpose, 'status': c.status,
                'policy_version': c.policy_version, 'source': c.source,
                'granted_at': iso(c.granted_at),
                'withdrawn_at': iso(c.withdrawn_at),
                'updated_at': iso(c.updated_at)}),
            'history': _rows(sa.select(ConsentEvent)
                             .where(ConsentEvent.user_id == u.id)
                             .order_by(ConsentEvent.id), lambda e: {
                'purpose': e.purpose, 'action': e.action,
                'policy_version': e.policy_version, 'source': e.source,
                'occurred_at': iso(e.occurred_at)}),
        },
        'activity': _rows(sa.select(AnalyticsEvent)
                          .where(AnalyticsEvent.user_id == u.id)
                          .order_by(AnalyticsEvent.id), lambda a: {
            'event': a.name, 'occurred_at': iso(a.occurred_at)}),
        'marketing_deliveries': _rows(
            sa.select(MarketingDispatch)
            .where(MarketingDispatch.user_id == u.id)
            .order_by(MarketingDispatch.id), lambda d: {
                'campaign': d.campaign, 'policy_version': d.policy_version,
                'sent_at': iso(d.sent_at)}),
    }
    return data


SOURCES = {
    'profile': 'table user (identity & contact columns)',
    'settings': 'table user (UI state columns)',
    'social_graph': 'table followers',
    'posts': 'table post',
    'messages': 'table message (sender_id / recipient_id)',
    'notifications': 'table notification',
    'tasks': 'table task (background jobs)',
    'consents': 'tables user_consent + consent_event',
    'activity': 'table analytics_event (only with OPTIONAL_ANALYTICS consent)',
    'marketing_deliveries': 'table marketing_dispatch',
}


def _count(value):
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return sum(_count(v) for k, v in value.items()
                   if isinstance(v, list)) if any(
            isinstance(v, list) for v in value.values()) else 1
    return 1


def build_export(subject, requested_by):
    data = collect(subject)
    return {
        'schema': SCHEMA,
        'schema_version': SCHEMA_VERSION,
        'generated_at': iso(datetime.now(timezone.utc)),
        'timezone': 'UTC',
        'subject': {'type': 'user', 'id': subject.id},
        'requested_by': requested_by,
        'categories': [{'name': k, 'source': SOURCES[k],
                        'records': _count(v)} for k, v in data.items()],
        'excluded_fields': EXCLUDED_FIELDS,
        'data': data,
    }
