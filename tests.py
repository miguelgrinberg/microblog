#!/usr/bin/env python
import copy
from datetime import datetime, timezone, timedelta
import unittest
from unittest.mock import patch, MagicMock
import requests
from app import create_app, db
from app.models import User, Post
from app.translate import translate
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    ELASTICSEARCH_URL = None


class UserModelCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_hashing(self):
        u = User(username='susan', email='susan@example.com')
        u.set_password('cat')
        self.assertFalse(u.check_password('dog'))
        self.assertTrue(u.check_password('cat'))

    def test_avatar(self):
        u = User(username='john', email='john@example.com')
        self.assertEqual(u.avatar(128), ('https://www.gravatar.com/avatar/'
                                         'd4c74594d841139328695756648b6bd6'
                                         '?d=identicon&s=128'))

    def test_follow(self):
        u1 = User(username='john', email='john@example.com')
        u2 = User(username='susan', email='susan@example.com')
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()
        following = db.session.scalars(u1.following.select()).all()
        followers = db.session.scalars(u2.followers.select()).all()
        self.assertEqual(following, [])
        self.assertEqual(followers, [])

        u1.follow(u2)
        db.session.commit()
        self.assertTrue(u1.is_following(u2))
        self.assertEqual(u1.following_count(), 1)
        self.assertEqual(u2.followers_count(), 1)
        u1_following = db.session.scalars(u1.following.select()).all()
        u2_followers = db.session.scalars(u2.followers.select()).all()
        self.assertEqual(u1_following[0].username, 'susan')
        self.assertEqual(u2_followers[0].username, 'john')

        u1.unfollow(u2)
        db.session.commit()
        self.assertFalse(u1.is_following(u2))
        self.assertEqual(u1.following_count(), 0)
        self.assertEqual(u2.followers_count(), 0)

    def test_follow_posts(self):
        # create four users
        u1 = User(username='john', email='john@example.com')
        u2 = User(username='susan', email='susan@example.com')
        u3 = User(username='mary', email='mary@example.com')
        u4 = User(username='david', email='david@example.com')
        db.session.add_all([u1, u2, u3, u4])

        # create four posts
        now = datetime.now(timezone.utc)
        p1 = Post(body="post from john", author=u1,
                  timestamp=now + timedelta(seconds=1))
        p2 = Post(body="post from susan", author=u2,
                  timestamp=now + timedelta(seconds=4))
        p3 = Post(body="post from mary", author=u3,
                  timestamp=now + timedelta(seconds=3))
        p4 = Post(body="post from david", author=u4,
                  timestamp=now + timedelta(seconds=2))
        db.session.add_all([p1, p2, p3, p4])
        db.session.commit()

        # setup the followers
        u1.follow(u2)  # john follows susan
        u1.follow(u4)  # john follows david
        u2.follow(u3)  # susan follows mary
        u3.follow(u4)  # mary follows david
        db.session.commit()

        # check the following posts of each user
        f1 = db.session.scalars(u1.following_posts()).all()
        f2 = db.session.scalars(u2.following_posts()).all()
        f3 = db.session.scalars(u3.following_posts()).all()
        f4 = db.session.scalars(u4.following_posts()).all()
        self.assertEqual(f1, [p2, p4, p1])
        self.assertEqual(f2, [p2, p3])
        self.assertEqual(f3, [p3, p4])
        self.assertEqual(f4, [p4])




class TranslateResilienceTestCase(unittest.TestCase):
    """
    ЛР№2, Завдання 3: автоматизована верифікація стійкості translate().

    Зовнішній сервіс перекладу підміняється через unittest.mock (test
    double) — тест НЕ залежить від доступності реального Azure API чи
    локального mock_translator.py, тому детермінований і стабільний
    при повторних запусках.
    """

    def setUp(self):
        self.app = create_app(TestConfig)
        self.app.config['MS_TRANSLATOR_KEY'] = 'dummy-key-for-tests'
        self.app.config['TRANSLATOR_API_URL'] = \
            'http://mock-translator.test/translate'
        self.app_context = self.app.app_context()
        self.app_context.push()
        # test_request_context потрібен, бо flask_babel._() всередині
        # fallback-гілки translate() визначає locale через request.
        self.request_context = self.app.test_request_context()
        self.request_context.push()

    def tearDown(self):
        self.request_context.pop()
        self.app_context.pop()

    @patch('app.translate.requests.post')
    def test_translate_success_no_fallback(self, mock_post):
        # ПОЗИТИВНА ПЕРЕВІРКА: зовнішній сервіс відповідає нормально ->
        # fallback НЕ активується, зайвих retry немає.
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'translations': [{'text': 'Привіт'}]}]
        mock_post.return_value = mock_response

        result = translate('Hello', 'en', 'uk')

        self.assertEqual(result, 'Привіт')
        self.assertEqual(mock_post.call_count, 1)

    @patch('app.translate.time.sleep', return_value=None)
    @patch('app.translate.requests.post')
    def test_translate_timeout_triggers_fallback(self, mock_post, mock_sleep):
        # RESILIENCE TEST: зовнішня залежність постійно "висне" (timeout).
        mock_post.side_effect = requests.exceptions.Timeout()

        result = translate('Hello', 'en', 'uk')

        self.assertIn('Hello', result)
        self.assertIn('translation unavailable', result)
        self.assertEqual(mock_post.call_count, 3)  # рівно MAX_RETRIES

    @patch('app.translate.time.sleep', return_value=None)
    @patch('app.translate.requests.post')
    def test_translate_http_500_triggers_fallback(self, mock_post, mock_sleep):
        # RESILIENCE TEST: зовнішня залежність постійно повертає HTTP 500.
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        result = translate('Hello', 'en', 'uk')

        self.assertIn('translation unavailable', result)
        self.assertEqual(mock_post.call_count, 3)

    @patch('app.translate.time.sleep', return_value=None)
    @patch('app.translate.requests.post')
    def test_translate_connection_error_triggers_fallback(
            self, mock_post, mock_sleep):
        # RESILIENCE TEST: зовнішня залежність недоступна (ConnectionError).
        mock_post.side_effect = requests.exceptions.ConnectionError()

        result = translate('Hello', 'en', 'uk')

        self.assertIn('translation unavailable', result)
        self.assertEqual(mock_post.call_count, 3)

    # --- ЛР№3: захисні (characterization) тести перед рефакторингом ---

    @patch('app.translate.requests.post')
    def test_translate_not_configured_returns_error(self, mock_post):
        # Без ключа сервісу нічого не викликається: одразу повідомлення.
        self.app.config['MS_TRANSLATOR_KEY'] = ''

        result = translate('Hello', 'en', 'uk')

        self.assertIn('not configured', result)
        self.assertEqual(mock_post.call_count, 0)

    @patch('app.translate.time.sleep', return_value=None)
    @patch('app.translate.requests.post')
    def test_translate_retry_then_success(self, mock_post, mock_sleep):
        # Перша спроба невдала (HTTP 500), друга успішна -> без fallback.
        bad = MagicMock()
        bad.status_code = 500
        good = MagicMock()
        good.status_code = 200
        good.json.return_value = [{'translations': [{'text': 'Привіт'}]}]
        mock_post.side_effect = [bad, good]

        result = translate('Hello', 'en', 'uk')

        self.assertEqual(result, 'Привіт')
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(0.5)

    # --- ЛР№7: захист від мутації даних між спробами retry ---

    @patch('app.translate.time.sleep', return_value=None)
    @patch('app.translate.requests.post')
    def test_retry_does_not_mutate_request_payload(self, mock_post, mock_sleep):
        # Кожна спроба має надсилати ОДИН І ТОЙ САМИЙ текст користувача.
        sent = []

        def fake_post(url, headers=None, json=None, timeout=None):
            sent.append(copy.deepcopy(json))   # знімок на момент виклику
            response = MagicMock()
            response.status_code = 500
            return response

        mock_post.side_effect = fake_post

        translate('Hello World', 'en', 'uk')

        self.assertEqual(len(sent), 3)
        for payload in sent:
            self.assertEqual(payload, [{'Text': 'Hello World'}])

    @patch('app.translate.time.sleep', return_value=None)
    @patch('app.translate.requests.post')
    def test_translation_after_retry_is_not_corrupted(self, mock_post, mock_sleep):
        # Бізнес-результат: після однієї невдалої спроби користувач бачить
        # переклад свого тексту, а не службової позначки retry.
        calls = []

        def fake_post(url, headers=None, json=None, timeout=None):
            calls.append(copy.deepcopy(json))
            response = MagicMock()
            if len(calls) == 1:
                response.status_code = 500
            else:
                response.status_code = 200
                response.json.return_value = [
                    {'translations': [{'text': 'uk:' + json[0]['Text']}]}]
            return response

        mock_post.side_effect = fake_post

        result = translate('Hello World', 'en', 'uk')

        self.assertEqual(result, 'uk:Hello World')

    @patch('app.translate.time.sleep', return_value=None)
    @patch('app.translate.requests.post')
    def test_translate_backoff_delays_are_exponential(
            self, mock_post, mock_sleep):
        # Паузи між трьома невдалими спробами: 0.5 с, потім 1.0 с
        # (після останньої спроби пауза не потрібна).
        mock_post.side_effect = requests.exceptions.Timeout()

        translate('Hello', 'en', 'uk')

        delays = [c.args[0] for c in mock_sleep.call_args_list]
        self.assertEqual(delays, [0.5, 1.0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
