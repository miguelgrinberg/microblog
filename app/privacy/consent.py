"""Завдання 4. Consent Management Engine (GDPR Art. 7) + Policy Gate.

* Згода окрема для кожної мети (purpose); одна мета НЕ поширюється на іншу.
* UserConsent - поточний стан, ConsentEvent - append-only історія (доказ).
* ConsentPolicyGate читає АКТУАЛЬНИЙ стан з БД безпосередньо перед дією
  (без кешу), тому REVOKE діє негайно, у т.ч. для вже поставлених у чергу
  background job-ів, які перевіряють згоду в момент ВИКОНАННЯ.
* Gate застосовується ЛИШЕ до optional-операцій. Договірні/системні функції
  (вхід, токени, пости, reset пароля) consent не перевіряють.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

import sqlalchemy as sa
from flask import current_app

from app import db
from app.models import UserConsent, ConsentEvent, AnalyticsEvent, \
    MarketingDispatch
from app.privacy.audit import subject_ref
from app.privacy.secure_logging import current_correlation_id

MARKETING_EMAIL = 'MARKETING_EMAIL'
OPTIONAL_ANALYTICS = 'OPTIONAL_ANALYTICS'

# purpose -> поточна версія політики (зміна версії вимагає нової згоди)
DEFAULT_POLICY_VERSIONS = {
    MARKETING_EMAIL: '2026-10-01',
    OPTIONAL_ANALYTICS: '2026-10-01',
}
ALLOWED_SOURCES = ('web', 'api', 'mobile')


class ConsentError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def policy_versions():
    return current_app.config.get('CONSENT_POLICY_VERSIONS',
                                  DEFAULT_POLICY_VERSIONS)


def validate_purpose(purpose):
    if purpose not in policy_versions():
        raise ConsentError('unknown_purpose',
                           f'unknown consent purpose: {purpose}')
    return purpose


def _current(user_id, purpose):
    return db.session.scalar(
        sa.select(UserConsent).where(UserConsent.user_id == user_id,
                                     UserConsent.purpose == purpose)
        .execution_options(populate_existing=True))


def _event(user_id, purpose, action, version, source, now):
    db.session.add(ConsentEvent(
        user_id=user_id, purpose=purpose, action=action,
        policy_version=version, source=source, occurred_at=now,
        correlation_id=current_correlation_id()))


def grant(user_id, purpose, policy_version, source='api'):
    """Ідемпотентно: повторний GRANT тієї ж версії не створює подію."""
    validate_purpose(purpose)
    if source not in ALLOWED_SOURCES:
        raise ConsentError('invalid_source', f'source must be one of '
                                             f'{", ".join(ALLOWED_SOURCES)}')
    current_version = policy_versions()[purpose]
    if policy_version != current_version:
        raise ConsentError('policy_version_mismatch',
                           f'current policy version for {purpose} is '
                           f'{current_version}')
    now = datetime.now(timezone.utc)
    c = _current(user_id, purpose)
    if c and c.status == 'GRANTED' and c.policy_version == policy_version:
        return c, False
    if c is None:
        c = UserConsent(user_id=user_id, purpose=purpose)
        db.session.add(c)
    c.status, c.policy_version, c.source = 'GRANTED', policy_version, source
    c.granted_at, c.withdrawn_at, c.updated_at = now, None, now
    _event(user_id, purpose, 'GRANT', policy_version, source, now)
    db.session.commit()
    _log('consent.grant', user_id, purpose)
    return c, True


def revoke(user_id, purpose, source='api'):
    """Ідемпотентно: повторний REVOKE - no-op, без суперечливих записів."""
    validate_purpose(purpose)
    if source not in ALLOWED_SOURCES:
        raise ConsentError('invalid_source', 'invalid source')
    c = _current(user_id, purpose)
    if c is None or c.status == 'WITHDRAWN':
        return c, False
    now = datetime.now(timezone.utc)
    c.status, c.withdrawn_at, c.updated_at, c.source = \
        'WITHDRAWN', now, now, source
    _event(user_id, purpose, 'REVOKE', c.policy_version, source, now)
    db.session.commit()
    _log('consent.revoke', user_id, purpose)
    return c, True


def state(user_id):
    result = []
    for purpose, version in sorted(policy_versions().items()):
        c = _current(user_id, purpose)
        result.append({
            'purpose': purpose, 'current_policy_version': version,
            'status': c.status if c else 'NOT_GIVEN',
            'policy_version': c.policy_version if c else None,
            'source': c.source if c else None,
            'granted_at': _iso(c.granted_at) if c else None,
            'withdrawn_at': _iso(c.withdrawn_at) if c else None,
        })
    return result


def _iso(dt):
    from app.privacy.export import iso
    return iso(dt)


def _log(op, user_id, purpose, result='OK'):
    current_app.logger.info(op, extra={'operation': op, 'result': result,
                                       'subject_ref': subject_ref(user_id),
                                       'purpose': purpose})


# --- Policy Gate ----------------------------------------------------------

@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    purpose: str

    @property
    def label(self):
        return 'ALLOW' if self.allowed else 'DENY'


class ConsentPolicyGate:
    """Окремий policy-компонент. Викликається безпосередньо перед дією."""

    @staticmethod
    def check(user_id, purpose):
        validate_purpose(purpose)
        c = _current(user_id, purpose)  # завжди свіжий стан з БД
        if c is None:
            d = Decision(False, 'NO_CONSENT', purpose)
        elif c.status != 'GRANTED':
            d = Decision(False, 'WITHDRAWN', purpose)
        elif c.policy_version != policy_versions()[purpose]:
            d = Decision(False, 'POLICY_VERSION_OUTDATED', purpose)
        else:
            d = Decision(True, 'GRANTED', purpose)
        _log('consent.gate', user_id, purpose, d.label)
        return d


# --- залежні (optional) бізнес-операції ------------------------------------

def send_marketing_digest(user_id, campaign='weekly-digest'):
    """Маркетингова розсилка. Побічний ефект = рядок MarketingDispatch
    (+ реальний лист, якщо налаштовано MAIL_SERVER)."""
    decision = ConsentPolicyGate.check(user_id, MARKETING_EMAIL)
    if not decision.allowed:
        return decision, None  # DENY: жодного побічного ефекту
    dispatch = MarketingDispatch(user_id=user_id, campaign=campaign,
                                 policy_version=policy_versions()[
                                     MARKETING_EMAIL])
    db.session.add(dispatch)
    db.session.commit()
    _deliver_email(user_id, campaign)
    return decision, dispatch


def _deliver_email(user_id, campaign):
    if not current_app.config.get('MAIL_SERVER'):
        return
    from app.email import send_email
    from app.models import User
    user = db.session.get(User, user_id)
    send_email(f'[Microblog] {campaign}',
               sender=current_app.config['ADMINS'][0],
               recipients=[user.email], text_body='Your weekly digest',
               html_body='<p>Your weekly digest</p>')


def marketing_digest_job(user_id, campaign='weekly-digest'):
    """Тіло background job (rq). Згода перевіряється в момент ВИКОНАННЯ,
    а не постановки в чергу: REVOKE між enqueue і run блокує розсилку."""
    decision, _ = send_marketing_digest(user_id, campaign)
    return decision.label


def track_analytics_event(user_id, name):
    decision = ConsentPolicyGate.check(user_id, OPTIONAL_ANALYTICS)
    if not decision.allowed:
        return decision, None
    ev = AnalyticsEvent(user_id=user_id, name=name[:64])
    db.session.add(ev)
    db.session.commit()
    return decision, ev
