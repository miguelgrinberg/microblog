"""Завдання 3. Erasure / Anonymization workflow - перевірки стану БД."""
import re

import pytest
import sqlalchemy as sa

from app import db
from app.models import (User, Post, Message, Notification, UserConsent,
                        ConsentEvent, AnalyticsEvent, MarketingDispatch,
                        AuditEvent, followers)
from app.privacy import erasure
from privacy_tests.conftest import (OLENA, TARAS, POST_BODY, MSG_TO_TARAS,
                                    MSG_FROM_TARAS, bearer, basic, db_dump,
                                    make_user)

CONFIRM = {'confirm': 'ANONYMIZE'}


def _without_audit(dump):
    """Дамп БД без таблиці audit_event (вона легітимно росте)."""
    return '\n'.join(line for line in dump.splitlines()
                     if 'audit_event' not in line)


def _anonymize(client, subject_id, token, body=CONFIRM):
    return client.post(f'/api/users/{subject_id}/anonymize',
                       headers=bearer(token), json=body)


def _original_pii(user, token):
    return [OLENA['username'], OLENA['email'], OLENA['phone'],
            OLENA['about_me'], POST_BODY, MSG_TO_TARAS, MSG_FROM_TARAS,
            user.password_hash, token]


def _count(model, **where):
    stmt = sa.select(sa.func.count()).select_from(model)
    for k, v in where.items():
        stmt = stmt.where(getattr(model, k) == v)
    return db.session.scalar(stmt)


@pytest.fixture
def anonymized(client, seeded, log_capture):
    """Готує стан ДО, виконує workflow і повертає контекст для перевірок."""
    olena, tok = seeded['olena']
    ctx = {'oid': olena.id, 'pii': _original_pii(olena, tok),
           'taras_id': seeded['taras'][0].id, 'before': db_dump(),
           'posts': _count(Post), 'messages': _count(Message)}
    ctx['response'] = _anonymize(client, olena.id, tok)
    ctx['after'] = db_dump()
    ctx['logs'] = log_capture['text'].getvalue() + \
        log_capture['json'].getvalue()
    return ctx


def test_state_before_contains_all_control_pii(anonymized):
    assert all(v in anonymized['before'] for v in anonymized['pii'])
    r = anonymized['response']
    assert r.status_code == 200 and r.get_json()['status'] == 'anonymized'


def test_no_original_pii_left_in_any_table_or_log(anonymized):
    leaked = [v for v in anonymized['pii'] if v in anonymized['after']]
    assert not leaked, f'PII left in DB: {leaked}'      # усі таблиці!
    assert not [v for v in anonymized['pii'] if v in anonymized['logs']]


def test_user_row_becomes_neutral_anonymous_subject(anonymized):
    u = db.session.get(User, anonymized['oid'])
    assert u.username.startswith('deleted-')
    assert u.email.endswith('@anon.local')
    assert u.phone is u.about_me is u.password_hash is u.token is None
    assert u.anonymized_at is not None


def test_business_records_are_retained_without_content(anonymized):
    oid = anonymized['oid']
    assert _count(Post) == anonymized['posts']
    assert _count(Message) == anonymized['messages']
    assert db.session.scalar(sa.select(Post.body).where(
        Post.user_id == oid)) == erasure.ERASED_POST
    assert db.session.get(User, anonymized['taras_id']).email == \
        TARAS['email']                                 # контрагент цілий


def test_indirect_sources_are_deleted(anonymized):
    oid = anonymized['oid']
    for model in (Notification, AnalyticsEvent, MarketingDispatch):
        assert _count(model, user_id=oid) == 0, model.__tablename__
    links = db.session.scalar(sa.select(sa.func.count()).select_from(
        followers).where(sa.or_(followers.c.follower_id == oid,
                                followers.c.followed_id == oid)))
    assert links == 0


def test_consent_evidence_is_retained_and_withdrawn(anonymized):
    oid = anonymized['oid']
    c = db.session.scalar(sa.select(UserConsent).where(
        UserConsent.user_id == oid))
    assert (c.status, c.source) == ('WITHDRAWN', 'erasure')
    revoke_source = db.session.scalar(sa.select(ConsentEvent.source).where(
        ConsentEvent.user_id == oid, ConsentEvent.action == 'REVOKE'))
    assert revoke_source == 'erasure'


def test_referential_integrity_and_reports_after_workflow(client, seeded):
    olena, tok = seeded['olena']
    taras, taras_tok = seeded['taras']
    _anonymize(client, olena.id, tok)
    raw = db.session.connection().connection.dbapi_connection
    assert raw.execute('PRAGMA foreign_key_check').fetchall() == []
    orphans = db.session.execute(sa.text(
        'SELECT count(*) FROM post p LEFT JOIN user u ON p.user_id=u.id '
        'WHERE u.id IS NULL')).scalar()
    assert orphans == 0
    report = db.session.execute(
        sa.select(User.username, sa.func.count(Post.id))
        .join(Post).group_by(User.username)).all()   # звітний запит працює
    assert len(report) == 1 and report[0][0].startswith('deleted-')
    # експорт контрагента не падає і не розкриває видалені дані
    r = client.get(f'/api/users/{taras.id}/personal-data',
                   headers=bearer(taras_tok))
    assert r.status_code == 200
    received = r.get_json()['data']['messages']['received']
    assert received[0]['from'].startswith('deleted-')
    assert received[0]['body'] == erasure.ERASED_MESSAGE


def test_anonymized_identity_is_unique_and_not_derived(client, app):
    a, ta = make_user({'username': 'anon_a', 'email': 'a.ctrl@example.test',
                       'phone': None, 'password': 'Ctrl-A-1', 'about_me': None})
    b, tb = make_user({'username': 'anon_b', 'email': 'b.ctrl@example.test',
                       'phone': None, 'password': 'Ctrl-B-1', 'about_me': None})
    assert _anonymize(client, a.id, ta).status_code == 200
    assert _anonymize(client, b.id, tb).status_code == 200  # UNIQUE не падає
    ua, ub = db.session.get(User, a.id), db.session.get(User, b.id)
    assert ua.email != ub.email and ua.username != ub.username
    for u, orig in ((ua, 'a.ctrl'), (ub, 'b.ctrl')):
        assert orig not in u.email and orig not in u.username
        # 128 біт криптографічної випадковості, не hash/id: відновити нема з чого
        assert re.fullmatch(r'deleted-[0-9a-f]{32}@anon\.local', u.email)


def test_idempotent_repeat_does_not_restore_or_duplicate(client, seeded):
    olena, tok = seeded['olena']
    _, dpo_tok = seeded['dpo']
    _anonymize(client, olena.id, tok)
    snapshot = db_dump()
    users_before = _count(User)
    # сам суб'єкт більше не автентифікується (токен знищено)
    assert _anonymize(client, olena.id, tok).status_code == 401
    assert client.post('/api/tokens', headers=basic(
        OLENA['username'], OLENA['password'])).status_code == 401
    # повтор уповноваженим actor - керований no-op
    r = _anonymize(client, olena.id, dpo_tok)
    assert r.status_code == 200 and r.get_json()['status'] == \
        'already_anonymized'
    assert _count(User) == users_before                  # нових профілів нема
    assert _without_audit(db_dump()) == _without_audit(snapshot)           # нічого не змінилось


def test_partial_failure_rolls_back_everything(client, seeded, monkeypatch):
    olena, tok = seeded['olena']
    pii = _original_pii(olena, tok)
    before = db_dump()

    def boom(user):
        raise RuntimeError('simulated crash in followers step')
    steps = [(e, (lambda u, now: boom(u)) if e == 'followers' else s)
             for e, s in erasure.STEPS]
    monkeypatch.setattr(erasure, 'STEPS', steps)

    r = _anonymize(client, olena.id, tok)
    assert r.status_code == 500
    assert 'rolled back' in r.get_json()['message']
    db.session.expire_all()
    after = db_dump()
    assert all(v in after for v in pii)          # user + post вже були
    assert _without_audit(after) == _without_audit(before)  # rollback
    failed = db.session.scalars(sa.select(AuditEvent).where(
        AuditEvent.result == 'FAILED')).all()
    assert len(failed) == 1
    # після усунення збою безпечний повтор завершується успішно
    monkeypatch.undo()
    assert _anonymize(client, olena.id, tok).get_json()['status'] == \
        'anonymized'


def test_foreign_actor_is_forbidden_and_nothing_changes(client, seeded):
    olena = seeded['olena'][0]
    _, taras_tok = seeded['taras']
    before = db_dump()
    r = _anonymize(client, olena.id, taras_tok)
    assert r.status_code == 404 and r.get_json() == {'error': 'Not Found'}
    assert db_dump() == before


def test_requires_post_and_explicit_confirmation(client, seeded):
    olena, tok = seeded['olena']
    assert client.get(f'/api/users/{olena.id}/anonymize',
                      headers=bearer(tok)).status_code == 405
    assert _anonymize(client, olena.id, tok, body={}).status_code == 400
    assert db.session.get(User, olena.id).email == OLENA['email']


def test_audit_event_is_privacy_safe(client, seeded):
    olena, tok = seeded['olena']
    pii = _original_pii(olena, tok)
    _anonymize(client, olena.id, tok)
    ev = db.session.scalars(sa.select(AuditEvent).where(
        AuditEvent.action == 'privacy.anonymize')).one()
    assert ev.result == 'SUCCESS' and ev.correlation_id
    assert ev.actor_ref == ev.subject_ref and ev.subject_ref.startswith('subj_')
    audit_text = ' '.join(str(v) for v in (ev.actor_ref, ev.subject_ref,
                                           ev.details_json))
    assert not [v for v in pii if v in audit_text]
    assert '"post": 1' in ev.details_json          # лише лічильники
