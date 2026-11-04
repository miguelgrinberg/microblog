"""Завдання 4. Consent Management Engine + Policy Gate."""
import sqlalchemy as sa

from app import db
from app.models import (UserConsent, ConsentEvent, AnalyticsEvent,
                        MarketingDispatch)
from app.privacy.consent import (ConsentPolicyGate, MARKETING_EMAIL,
                                 OPTIONAL_ANALYTICS, marketing_digest_job)
from privacy_tests.conftest import OLENA, bearer, basic

V = '2026-10-01'


def grant(client, uid, tok, purpose, version=V, source='web'):
    return client.post(f'/api/users/{uid}/consents/{purpose}',
                       headers=bearer(tok),
                       json={'policy_version': version, 'source': source})


def revoke(client, uid, tok, purpose):
    return client.delete(f'/api/users/{uid}/consents/{purpose}',
                         headers=bearer(tok), json={'source': 'web'})


def digest(client, uid, tok):
    return client.post(f'/api/users/{uid}/marketing/digest',
                       headers=bearer(tok))


def dispatches(uid):
    return db.session.scalar(sa.select(sa.func.count()).select_from(
        MarketingDispatch).where(MarketingDispatch.user_id == uid))


def events(uid, purpose=None):
    stmt = sa.select(ConsentEvent).where(ConsentEvent.user_id == uid)
    if purpose:
        stmt = stmt.where(ConsentEvent.purpose == purpose)
    return db.session.scalars(stmt.order_by(ConsentEvent.id)).all()


def test_scenario_grant_allow_revoke_deny(client, users):
    """Інтеграційний сценарій для захисту: DENY -> GRANT -> ALLOW ->
    REVOKE -> DENY, із перевіркою побічного ефекту на кожному кроці."""
    olena, tok = users['olena']
    r = digest(client, olena.id, tok)                         # 0. DENY
    assert r.status_code == 403 and r.get_json()['reason'] == 'NO_CONSENT'
    assert dispatches(olena.id) == 0

    assert grant(client, olena.id, tok, MARKETING_EMAIL).status_code == 201
    r = digest(client, olena.id, tok)                         # 1. ALLOW
    assert r.status_code == 202 and r.get_json()['decision'] == 'ALLOW'
    assert dispatches(olena.id) == 1                          # ефект є

    assert revoke(client, olena.id, tok, MARKETING_EMAIL).status_code == 200
    r = digest(client, olena.id, tok)                         # 2. DENY
    assert r.status_code == 403 and r.get_json() == {
        'decision': 'DENY', 'reason': 'WITHDRAWN',
        'purpose': MARKETING_EMAIL}
    assert dispatches(olena.id) == 1                          # нового нема


def test_consent_for_one_purpose_does_not_allow_another(client, users):
    olena, tok = users['olena']
    grant(client, olena.id, tok, MARKETING_EMAIL)
    r = client.post('/api/analytics/events', headers=bearer(tok),
                    json={'event': 'page_view'})
    assert r.status_code == 403 and r.get_json()['reason'] == 'NO_CONSENT'
    assert db.session.scalar(sa.select(sa.func.count()).select_from(
        AnalyticsEvent)) == 0
    grant(client, olena.id, tok, OPTIONAL_ANALYTICS)
    revoke(client, olena.id, tok, MARKETING_EMAIL)
    assert client.post('/api/analytics/events', headers=bearer(tok),
                       json={'event': 'page_view'}).status_code == 201
    assert digest(client, olena.id, tok).status_code == 403


def test_grant_and_revoke_are_idempotent(client, users):
    olena, tok = users['olena']
    assert grant(client, olena.id, tok, MARKETING_EMAIL).status_code == 201
    r = grant(client, olena.id, tok, MARKETING_EMAIL)
    assert r.status_code == 200 and r.get_json()['changed'] is False
    assert revoke(client, olena.id, tok, MARKETING_EMAIL).get_json()[
        'changed'] is True
    r = revoke(client, olena.id, tok, MARKETING_EMAIL)
    assert r.status_code == 200 and r.get_json()['changed'] is False
    assert [e.action for e in events(olena.id)] == ['GRANT', 'REVOKE']
    assert db.session.scalar(sa.select(sa.func.count()).select_from(
        UserConsent)) == 1                       # жодних суперечливих записів


def test_evidence_and_history_are_stored(client, users):
    olena, tok = users['olena']
    grant(client, olena.id, tok, MARKETING_EMAIL, source='mobile')
    revoke(client, olena.id, tok, MARKETING_EMAIL)
    grant(client, olena.id, tok, MARKETING_EMAIL, source='web')
    hist = events(olena.id, MARKETING_EMAIL)
    assert [(e.action, e.source, e.policy_version) for e in hist] == [
        ('GRANT', 'mobile', V), ('REVOKE', 'web', V), ('GRANT', 'web', V)]
    assert all(e.occurred_at for e in hist)
    c = db.session.scalar(sa.select(UserConsent))
    db.session.refresh(c)
    assert c.status == 'GRANTED' and c.withdrawn_at is None
    assert c.granted_at >= hist[1].occurred_at and c.updated_at
    state = client.get(f'/api/users/{olena.id}/consents',
                       headers=bearer(tok)).get_json()['consents']
    assert {s['purpose']: s['status'] for s in state} == {
        MARKETING_EMAIL: 'GRANTED', OPTIONAL_ANALYTICS: 'NOT_GIVEN'}


def test_validation_of_purpose_version_and_source(client, users):
    olena, tok = users['olena']
    assert grant(client, olena.id, tok, 'EVERYTHING').status_code == 400
    assert grant(client, olena.id, tok, MARKETING_EMAIL,
                 version='2020-01-01').status_code == 409
    assert grant(client, olena.id, tok, MARKETING_EMAIL,
                 source='carrier-pigeon').status_code == 400
    assert events(olena.id) == []


def test_commands_require_the_subject_itself(client, users):
    olena, _ = users['olena']
    _, taras_tok = users['taras']
    _, dpo_tok = users['dpo']
    assert grant(client, olena.id, taras_tok,
                 MARKETING_EMAIL).status_code == 404
    assert grant(client, olena.id, dpo_tok,
                 MARKETING_EMAIL).status_code == 404   # не «за користувача»
    assert client.post(f'/api/users/{olena.id}/consents/{MARKETING_EMAIL}',
                       json={'policy_version': V}).status_code == 401
    assert events(olena.id) == []


def test_outdated_policy_version_is_denied(app, client, users):
    olena, tok = users['olena']
    grant(client, olena.id, tok, MARKETING_EMAIL)
    app.config['CONSENT_POLICY_VERSIONS'] = {
        **app.config['CONSENT_POLICY_VERSIONS'], MARKETING_EMAIL: '2027-01-01'}
    d = ConsentPolicyGate.check(olena.id, MARKETING_EMAIL)
    assert (d.allowed, d.reason) == (False, 'POLICY_VERSION_OUTDATED')
    assert digest(client, olena.id, tok).status_code == 403
    assert dispatches(olena.id) == 0


def test_background_job_rechecks_consent_at_execution(client, users):
    olena, tok = users['olena']
    grant(client, olena.id, tok, MARKETING_EMAIL)
    queued_job = (marketing_digest_job, (olena.id,))   # поставлено в чергу
    revoke(client, olena.id, tok, MARKETING_EMAIL)     # відкликано ДО запуску
    fn, args = queued_job
    assert fn(*args) == 'DENY'                         # worker виконує
    assert dispatches(olena.id) == 0


def test_contractual_functions_are_not_blocked_by_consent(client, users):
    """Consent - не універсальний прапорець: без жодної згоди працюють
    вхід, токени, профіль, експорт (інші законні підстави)."""
    olena, tok = users['olena']
    revoke(client, olena.id, tok, MARKETING_EMAIL)
    assert client.post('/api/tokens', headers=basic(
        OLENA['username'], OLENA['password'])).status_code == 200
    assert client.get(f'/api/users/{olena.id}',
                      headers=bearer(tok)).status_code == 200
    assert client.put(f'/api/users/{olena.id}', headers=bearer(tok),
                      json={'about_me': 'updated'}).status_code == 200
    assert client.get(f'/api/users/{olena.id}/personal-data',
                      headers=bearer(tok)).status_code == 200
