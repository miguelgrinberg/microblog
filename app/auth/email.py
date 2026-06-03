from app.email import send_email
from app.i18n import _
from config import Config


def send_password_reset_email(user) -> None:
    token = user.get_reset_password_token()
    from app.templates import jinja_env
    send_email(
        _('[Microblog] Reset Your Password'),
        sender=Config.ADMINS[0],
        recipients=[user.email],
        text_body=jinja_env.get_template('email/reset_password.txt').render(
            user=user, token=token),
        html_body=jinja_env.get_template('email/reset_password.html').render(
            user=user, token=token))
