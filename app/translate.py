import requests
from flask import current_app
from flask_babel import _


def translate(text, source_language, dest_language):
    # Check if the translation service is configured
    if 'MS_TRANSLATOR_KEY' not in current_app.config or not current_app.config['MS_TRANSLATOR_KEY']:
        return _('Error: the translation service is not configured.')

    auth = {
        'Ocp-Apim-Subscription-Key': current_app.config['MS_TRANSLATOR_KEY'],
        'Ocp-Apim-Subscription-Region': current_app.config['MS_TRANSLATOR_REGION']
    }

    # Make the translation request
    response = requests.post(
        f'https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&from={source_language}&to={dest_language}',
        headers=auth,
        json=[{'Text': text}]
    )

    # Check for a successful response
    if response.status_code != 200:
        print(response.status_code)  # Log the status code for debugging
        print(response.text)          # Log the response text for debugging
        return _('Error: the translation service failed.')

    return response.json()[0]['translations'][0]['text']
