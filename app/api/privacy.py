"""ЛР4: API для прав суб'єкта даних та керування згодами."""
from flask import request

from app import db
from app.api import bp
from app.api.auth import token_auth
from app.api.errors import bad_request, error_response
from app.privacy import consent as consent_svc
from app.privacy.access import authorize_subject
from app.privacy.audit import record_audit
from app.privacy.erasure import anonymize_subject
from app.privacy.export import build_export, iso

NO_STORE = {'Cache-Control': 'no-store', 'Pragma': 'no-cache'}


# --- Завдання 2: Right of Access ------------------------------------------

@bp.route('/users/<int:id>/personal-data', methods=['GET'])
@token_auth.login_required
def export_personal_data(id):
    principal = token_auth.current_user()
    subject, requested_by = authorize_subject(principal, id)
    payload = build_export(subject, requested_by)
    record_audit('privacy.export', principal.id, subject.id, 'SUCCESS',
                 details={'sections': len(payload['data'])})
    db.session.commit()
    return payload, 200, NO_STORE


# --- Завдання 3: Right to Erasure -----------------------------------------

@bp.route('/users/<int:id>/anonymize', methods=['POST'])
@token_auth.login_required
def anonymize_user(id):
    principal = token_auth.current_user()
    principal_id = principal.id
    subject, _ = authorize_subject(principal, id)
    body = request.get_json(silent=True) or {}
    if body.get('confirm') != 'ANONYMIZE':
        return bad_request('confirmation required: {"confirm": "ANONYMIZE"}')
    try:
        result = anonymize_subject(subject.id, principal_id)
    except Exception:
        return error_response(500, 'anonymization failed and was rolled '
                                   'back; it is safe to retry')
    return {'status': result['status'],
            'subject': {'type': 'user', 'id': id},
            'anonymized_at': iso(result['anonymized_at']),
            'affected': result.get('affected', {})}, 200, NO_STORE


# --- Завдання 4: Consent Management ---------------------------------------

def _consent_error(e):
    status = 409 if e.code == 'policy_version_mismatch' else 400
    return error_response(status, e.message)


@bp.route('/users/<int:id>/consents', methods=['GET'])
@token_auth.login_required
def list_consents(id):
    subject, _ = authorize_subject(token_auth.current_user(), id)
    return {'subject': {'type': 'user', 'id': subject.id},
            'consents': consent_svc.state(subject.id)}, 200, NO_STORE


@bp.route('/users/<int:id>/consents/<purpose>', methods=['POST'])
@token_auth.login_required
def grant_consent(id, purpose):
    # згоду дає ЛИШЕ сам суб'єкт (officer не може погодитись «за нього»)
    subject, _ = authorize_subject(token_auth.current_user(), id,
                                   allow_officer=False)
    body = request.get_json(silent=True) or {}
    try:
        c, changed = consent_svc.grant(subject.id, purpose,
                                       body.get('policy_version'),
                                       body.get('source', 'api'))
    except consent_svc.ConsentError as e:
        return _consent_error(e)
    return {'purpose': purpose, 'status': c.status,
            'policy_version': c.policy_version, 'changed': changed}, \
        (201 if changed else 200)


@bp.route('/users/<int:id>/consents/<purpose>', methods=['DELETE'])
@token_auth.login_required
def revoke_consent(id, purpose):
    subject, _ = authorize_subject(token_auth.current_user(), id,
                                   allow_officer=False)
    body = request.get_json(silent=True) or {}
    try:
        c, changed = consent_svc.revoke(subject.id, purpose,
                                        body.get('source', 'api'))
    except consent_svc.ConsentError as e:
        return _consent_error(e)
    return {'purpose': purpose,
            'status': c.status if c else 'NOT_GIVEN',
            'changed': changed}, 200


# --- Залежні optional-операції під Policy Gate -----------------------------

@bp.route('/users/<int:id>/marketing/digest', methods=['POST'])
@token_auth.login_required
def send_digest(id):
    subject, _ = authorize_subject(token_auth.current_user(), id)
    decision, dispatch = consent_svc.send_marketing_digest(subject.id)
    if not decision.allowed:
        return {'decision': 'DENY', 'reason': decision.reason,
                'purpose': decision.purpose}, 403
    return {'decision': 'ALLOW', 'dispatch_id': dispatch.id,
            'campaign': dispatch.campaign}, 202


@bp.route('/analytics/events', methods=['POST'])
@token_auth.login_required
def track_event():
    user = token_auth.current_user()
    name = (request.get_json(silent=True) or {}).get('event', 'page_view')
    decision, ev = consent_svc.track_analytics_event(user.id, str(name))
    if not decision.allowed:
        return {'decision': 'DENY', 'reason': decision.reason,
                'recorded': False}, 403
    return {'decision': 'ALLOW', 'recorded': True, 'event_id': ev.id}, 201
