"""Контроль доступу до операцій над персональними даними суб'єкта.

Правило: authenticated principal == subject  АБО  principal має явне
повноваження can_manage_privacy. Path parameter сам по собі нічого не дає.
Чужий і неіснуючий id дають ІДЕНТИЧНУ відповідь 404 без body-даних, тож
атакувальник не може перебором дізнатися, чи існує профіль (no oracle).
"""
from flask import abort

from app import db
from app.models import User


def authorize_subject(principal, subject_id, allow_officer=True):
    is_self = principal is not None and principal.id == subject_id
    is_officer = allow_officer and principal is not None and \
        bool(principal.can_manage_privacy)
    if not (is_self or is_officer):
        abort(404)
    subject = db.session.get(User, subject_id)
    if subject is None:
        abort(404)
    return subject, ('self' if is_self else 'privacy_officer')
