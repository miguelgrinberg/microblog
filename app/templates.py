from fastapi.templating import Jinja2Templates
from fastapi import Request
from sqlalchemy.orm import Session

from app.i18n import gettext, moment, get_locale
from app.security import get_current_user, get_flashed_messages

jinja_env = None
_templates: Jinja2Templates = None


def setup_templates(app):
    global _templates, jinja_env
    _templates = Jinja2Templates(directory='app/templates')
    jinja_env = _templates.env
    jinja_env.globals['_'] = gettext
    jinja_env.globals['moment'] = moment


def render(request: Request, db: Session, template_name: str, **ctx):
    current_user = get_current_user(request, db)
    flashes = get_flashed_messages(request)
    locale = get_locale()

    search_form = None
    if current_user is not None:
        from app.main.forms import SearchForm
        search_form = SearchForm()

    return _templates.TemplateResponse(request, template_name, {
        'current_user': current_user,
        'messages': flashes,
        'locale': locale,
        'search_form': search_form,
        **ctx,
    })


def render_error(request: Request, template_name: str) -> str:
    return _templates.env.get_template(template_name).render(
        request=request,
        current_user=None,
        messages=[],
        locale='en',
        search_form=None,
    )
