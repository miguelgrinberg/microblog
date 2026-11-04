"""Privacy-safe audit та псевдонімні посилання на суб'єктів.

subject_ref = HMAC-SHA256(SECRET_KEY, "user:<id>")[:16]
  * у логах/аудиті не видно ні email, ні username, ні навіть числового id;
  * це ПСЕВДОНІМІЗАЦІЯ (зв'язати можна, маючи ключ і перебравши id), тому
    вона прийнятна лише для службових журналів. Після анонімізації рядок
    user не містить PII, тож навіть зв'язаний ref нікого не ідентифікує.
"""
import hashlib
import hmac
import json

from flask import current_app

from app import db
from app.models import AuditEvent
from app.privacy.secure_logging import current_correlation_id


def subject_ref(user_id):
    if user_id is None:
        return 'anonymous'
    key = current_app.config['SECRET_KEY'].encode()
    digest = hmac.new(key, f'user:{user_id}'.encode(), hashlib.sha256)
    return 'subj_' + digest.hexdigest()[:16]


def record_audit(action, actor_id, subject_id, result, details=None,
                 session=None):
    """Додає audit event у поточну (або передану) сесію. details -
    лише технічні лічильники/коди, НІКОЛИ не значення полів."""
    ev = AuditEvent(action=action, actor_ref=subject_ref(actor_id),
                    subject_ref=subject_ref(subject_id), result=result,
                    correlation_id=current_correlation_id(),
                    details_json=json.dumps(details or {}, sort_keys=True))
    (session or db.session).add(ev)
    current_app.logger.info('audit', extra={
        'operation': action, 'result': result,
        'actor_ref': ev.actor_ref, 'subject_ref': ev.subject_ref})
    return ev
