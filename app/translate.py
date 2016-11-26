try:
    import httplib  # Python 2
except ImportError:
    import http.client as httplib  # Python 3
try:
    from urllib import urlencode  # Python 2
except ImportError:
    from urllib.parse import urlencode  # Python 3
import json
from app import app
from flask_babel import gettext
from config import MS_TRANSLATOR_CLIENT_ID, MS_TRANSLATOR_CLIENT_SECRET


def microsoft_translate(text, sourceLang, destLang):
    if MS_TRANSLATOR_CLIENT_ID == "" or MS_TRANSLATOR_CLIENT_SECRET == "":
        return gettext('Error: translation service not configured.')
    try:
        # get access token
        params = urlencode({
            'client_id': MS_TRANSLATOR_CLIENT_ID,
            'client_secret': MS_TRANSLATOR_CLIENT_SECRET,
            'scope': 'http://api.microsofttranslator.com',
            'grant_type': 'client_credentials'
        })
        conn = httplib.HTTPSConnection("datamarket.accesscontrol.windows.net")
        conn.request("POST", "/v2/OAuth2-13", params)
        response = json.loads(conn.getresponse().read())
        token = response[u'access_token']

        # translate
        conn = httplib.HTTPConnection('api.microsofttranslator.com')
        params = {'appId': 'Bearer ' + token,
                  'from': sourceLang,
                  'to': destLang,
                  'text': text.encode("utf-8")}
        conn.request("GET",
                     '/V2/Ajax.svc/Translate?' + urlencode(params))
        response = json.loads('{"response":' +
                              conn.getresponse().read().decode('utf-8') + '}')
        return response["response"]
    except:
        raise


def google_translate(text, sourceLang, destLang):
    if not app.debug:
        return gettext('Error: translation service not available.')
    try:
        params = urlencode({
            'client': 't',
            'text': text.encode("utf-8"),
            'sl': sourceLang,
            'tl': destLang,
            'ie': 'UTF-8',
            'oe': 'UTF-8'})
        conn = httplib.HTTPSConnection("translate.google.com")
        conn.request("GET", "/translate_a/t?" + params,
                     headers={'User-Agent': 'Mozilla/5.0'})
        httpresponse = conn.getresponse().read().replace(
            ",,,", ",\"\",\"\",").replace(",,", ",\"\",")
        response = json.loads("{\"response\":" + httpresponse + "}")
        return response["response"][0][0][0]
    except:
        return gettext('Error: Unexpected error.')
