"""Завдання 2. Personal Data Export: повнота, мінімізація, авторизація."""
import json

import pytest

from app import db
from app.models import AuditEvent
from privacy_tests.conftest import (OLENA, TARAS, POST_BODY, MSG_TO_TARAS,
                                    MSG_FROM_TARAS, bearer, make_user)

SECTIONS = ['profile', 'settings', 'social_graph', 'posts', 'messages',
            'notifications', 'tasks', 'consents', 'activity',
            'marketing_deliveries']
FORBIDDEN_KEYS = ['password_hash', 'password', 'token', 'token_expiration',
                  'can_manage_privacy', 'reset_token', 'secret']


def _export(client, subject_id, token):
    return client.get(f'/api/users/{subject_id}/personal-data',
                      headers=bearer(token))


def _all_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _all_keys(v)


@pytest.fixture
def own_export(client, seeded):
    olena, tok = seeded['olena']
    r = _export(client, olena.id, tok)
    assert r.status_code == 200
    return olena, r


def test_export_contract_metadata(own_export):
    olena, r = own_export
    body = r.get_json()
    assert r.headers['Cache-Control'] == 'no-store'
    assert (body['schema'], body['schema_version']) == \
        ('microblog.personal-data-export', '1.0')
    assert body['subject'] == {'type': 'user', 'id': olena.id}
    assert body['requested_by'] == 'self'
    assert body['generated_at'].endswith('+00:00')
    assert sorted(body['data']) == sorted(SECTIONS)
    cats = {c['name']: c['source'] for c in body['categories']}
    assert set(cats) == set(SECTIONS) and all(cats.values())
    assert body['excluded_fields']                 # documented omissions


def test_export_profile_section(own_export):
    profile = own_export[1].get_json()['data']['profile']
    assert profile['email'] == OLENA['email']
    assert profile['phone'] == OLENA['phone']
    assert profile['about_me'] == OLENA['about_me']


def test_export_user_content_sections(own_export):
    d = own_export[1].get_json()['data']
    assert [p['body'] for p in d['posts']] == [POST_BODY]
    assert [m['body'] for m in d['messages']['sent']] == [MSG_TO_TARAS]
    assert [m['body'] for m in d['messages']['received']] == [MSG_FROM_TARAS]
    assert d['messages']['received'][0]['from'] == TARAS['username']
    assert d['notifications'][0]['name'] == 'unread_message_count'


def test_export_relations_consents_and_activity(own_export):
    d = own_export[1].get_json()['data']
    assert d['social_graph'] == {'following': [TARAS['username']],
                                 'followers': [TARAS['username']]}
    assert d['consents']['current'][0]['purpose'] == 'OPTIONAL_ANALYTICS'
    assert d['consents']['history'][0]['action'] == 'GRANT'
    assert d['activity'][0]['event'] == 'CONTROL-EVENT'
    assert d['marketing_deliveries'][0]['campaign'] == 'CONTROL-CMP'


def test_export_excludes_security_sensitive_fields(client, seeded):
    olena, tok = seeded['olena']
    raw = _export(client, olena.id, tok).get_data(as_text=True)
    data_keys = set(_all_keys(json.loads(raw)['data']))
    assert not data_keys & set(FORBIDDEN_KEYS), data_keys & set(FORBIDDEN_KEYS)
    db.session.refresh(olena)
    assert olena.password_hash not in raw
    assert tok not in raw
    assert OLENA['password'] not in raw
    # жодних даних інших суб'єктів, окрім публічного username
    assert TARAS['email'] not in raw and TARAS['phone'] not in raw
    assert 'CONTROL-ABOUT-taras' not in raw


def test_foreign_subject_is_denied_without_existence_oracle(client, seeded):
    olena = seeded['olena'][0]
    _, taras_tok = seeded['taras']
    foreign = _export(client, olena.id, taras_tok)
    missing = _export(client, 99999, taras_tok)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.get_json() == missing.get_json() == {'error': 'Not Found'}
    assert OLENA['email'] not in foreign.get_data(as_text=True)


def test_nonexistent_subject_for_privacy_officer(client, seeded):
    _, dpo_tok = seeded['dpo']
    r = _export(client, 99999, dpo_tok)
    assert r.status_code == 404 and r.get_json() == {'error': 'Not Found'}


def test_privacy_officer_has_explicit_authority(client, seeded):
    olena = seeded['olena'][0]
    _, dpo_tok = seeded['dpo']
    r = _export(client, olena.id, dpo_tok)
    assert r.status_code == 200
    assert r.get_json()['requested_by'] == 'privacy_officer'


def test_unauthenticated_request_is_rejected(client, seeded):
    olena = seeded['olena'][0]
    r = client.get(f'/api/users/{olena.id}/personal-data')
    assert r.status_code == 401
    assert OLENA['email'] not in r.get_data(as_text=True)


def test_missing_categories_are_predictable_empty_structures(client, app):
    u, tok = make_user({'username': 'empty_test',
                        'email': 'empty.control@example.test',
                        'phone': None, 'password': 'Ctrl-Empty-1',
                        'about_me': None})
    d = _export(client, u.id, tok).get_json()['data']
    assert d['posts'] == [] and d['activity'] == []
    assert d['messages'] == {'sent': [], 'received': []}
    assert d['consents'] == {'current': [], 'history': []}
    assert d['social_graph'] == {'following': [], 'followers': []}
    assert d['profile']['phone'] is None          # ключ є завжди


def test_schema_is_stable_between_exports(client, seeded):
    olena, tok = seeded['olena']

    def shape(o):
        if isinstance(o, dict):
            return {k: shape(v) for k, v in o.items()}
        if isinstance(o, list):
            return [shape(o[0])] if o else []
        return type(o).__name__

    a = _export(client, olena.id, tok).get_json()
    b = _export(client, olena.id, tok).get_json()
    a.pop('generated_at'), b.pop('generated_at')
    assert shape(a) == shape(b)
    for ts in [p['timestamp'] for p in a['data']['posts']] + \
            [a['data']['profile']['last_seen']]:
        assert ts.endswith('+00:00')               # однозначна часова зона


def test_export_does_not_leak_into_logs_but_is_audited(
        client, seeded, log_capture):
    olena, tok = seeded['olena']
    client.get(f'/api/users/{olena.id}/personal-data',
               headers={**bearer(tok), 'X-Correlation-ID': 'cid-export-01'})
    out = log_capture['text'].getvalue() + log_capture['json'].getvalue()
    for value in (OLENA['email'], OLENA['phone'], POST_BODY, MSG_TO_TARAS,
                  OLENA['username'], '"schema_version"'):
        assert value not in out
    assert 'privacy.export' in out and 'cid-export-01' in out
    ev = db.session.scalars(db.select(AuditEvent)).all()[-1]
    assert (ev.action, ev.result, ev.correlation_id) == \
        ('privacy.export', 'SUCCESS', 'cid-export-01')
    assert ev.subject_ref.startswith('subj_')     # псевдонімний ref
    assert OLENA['username'] not in (ev.details_json or '')
