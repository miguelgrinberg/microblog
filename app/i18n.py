from contextvars import ContextVar
from markupsafe import Markup
from babel.support import Translations, NullTranslations

_locale_var: ContextVar[str] = ContextVar('locale', default='en')
_translations_cache: dict = {}


def get_locale() -> str:
    return _locale_var.get()


def set_locale(locale: str):
    return _locale_var.set(locale)


def _load_translations(locale: str) -> NullTranslations:
    if locale not in _translations_cache:
        try:
            _translations_cache[locale] = Translations.load('app/translations', [locale])
        except Exception:
            _translations_cache[locale] = NullTranslations()
    return _translations_cache[locale]


def gettext(text: str) -> str:
    return _load_translations(get_locale()).ugettext(text)


def ngettext(singular: str, plural: str, n: int) -> str:
    return _load_translations(get_locale()).ungettext(singular, plural, n)


class LazyString:
    """Lazy translation string — resolved against the current locale at render time."""
    def __init__(self, text: str):
        self._text = text

    def __str__(self) -> str:
        return gettext(self._text)

    def __repr__(self) -> str:
        return f'LazyString({self._text!r})'

    def __html__(self) -> str:
        return str(self)

    def __mod__(self, other):
        return str(self) % other

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(self._text)


_ = gettext
_l = LazyString


def select_locale(accept_languages_header: str, available: list) -> str:
    """Pick the best locale from an Accept-Language header string."""
    from babel import Locale
    try:
        tags = [tag.split(';')[0].strip() for tag in accept_languages_header.split(',')]
        for tag in tags:
            lang = tag.split('-')[0]
            if lang in available:
                return lang
    except Exception:
        pass
    return available[0] if available else 'en'


class MomentProxy:
    """Thin wrapper that emits moment.js-compatible HTML from Jinja2 templates."""
    def __init__(self, dt):
        self.dt = dt

    def fromNow(self) -> Markup:
        iso = self.dt.isoformat() + 'Z'
        return Markup(f'<span class="moment" data-format="fromNow" data-datetime="{iso}"></span>')

    def format(self, fmt: str) -> Markup:
        iso = self.dt.isoformat() + 'Z'
        return Markup(f'<span class="moment" data-format="{fmt}" data-datetime="{iso}"></span>')


def moment(dt) -> MomentProxy:
    return MomentProxy(dt)
