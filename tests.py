#!/usr/bin/env python
from datetime import datetime, timezone, timedelta
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base, _db_session_var, init_db
from app.models import User, Post
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    ELASTICSEARCH_URL = None


class UserModelCase(unittest.TestCase):
    def setUp(self):
        init_db(TestConfig.SQLALCHEMY_DATABASE_URI)
        from app.db import get_engine
        engine = get_engine()
        Base.metadata.create_all(engine)
        self.db = Session(engine)
        self._token = _db_session_var.set(self.db)

        # Stub out state so model methods that reference it don't fail
        from app import state
        state.elasticsearch = None
        state.redis_client = None
        state.task_queue = None

    def tearDown(self):
        self.db.close()
        _db_session_var.reset(self._token)
        from app.db import get_engine
        Base.metadata.drop_all(get_engine())

    def test_password_hashing(self):
        u = User(username='susan', email='susan@example.com')
        u.set_password('cat')
        self.assertFalse(u.check_password('dog'))
        self.assertTrue(u.check_password('cat'))

    def test_avatar(self):
        u = User(username='john', email='john@example.com')
        self.assertEqual(u.avatar(128), (
            'https://www.gravatar.com/avatar/'
            'd4c74594d841139328695756648b6bd6'
            '?d=identicon&s=128'))

    def test_follow(self):
        u1 = User(username='john', email='john@example.com')
        u2 = User(username='susan', email='susan@example.com')
        self.db.add_all([u1, u2])
        self.db.commit()
        following = self.db.scalars(u1.following.select()).all()
        followers = self.db.scalars(u2.followers.select()).all()
        self.assertEqual(following, [])
        self.assertEqual(followers, [])

        u1.follow(u2)
        self.db.commit()
        self.assertTrue(u1.is_following(u2))
        self.assertEqual(u1.following_count(), 1)
        self.assertEqual(u2.followers_count(), 1)
        u1_following = self.db.scalars(u1.following.select()).all()
        u2_followers = self.db.scalars(u2.followers.select()).all()
        self.assertEqual(u1_following[0].username, 'susan')
        self.assertEqual(u2_followers[0].username, 'john')

        u1.unfollow(u2)
        self.db.commit()
        self.assertFalse(u1.is_following(u2))
        self.assertEqual(u1.following_count(), 0)
        self.assertEqual(u2.followers_count(), 0)

    def test_follow_posts(self):
        u1 = User(username='john', email='john@example.com')
        u2 = User(username='susan', email='susan@example.com')
        u3 = User(username='mary', email='mary@example.com')
        u4 = User(username='david', email='david@example.com')
        self.db.add_all([u1, u2, u3, u4])

        now = datetime.now(timezone.utc)
        p1 = Post(body='post from john', author=u1,
                  timestamp=now + timedelta(seconds=1))
        p2 = Post(body='post from susan', author=u2,
                  timestamp=now + timedelta(seconds=4))
        p3 = Post(body='post from mary', author=u3,
                  timestamp=now + timedelta(seconds=3))
        p4 = Post(body='post from david', author=u4,
                  timestamp=now + timedelta(seconds=2))
        self.db.add_all([p1, p2, p3, p4])
        self.db.commit()

        u1.follow(u2)
        u1.follow(u4)
        u2.follow(u3)
        u3.follow(u4)
        self.db.commit()

        f1 = self.db.scalars(u1.following_posts()).all()
        f2 = self.db.scalars(u2.following_posts()).all()
        f3 = self.db.scalars(u3.following_posts()).all()
        f4 = self.db.scalars(u4.following_posts()).all()
        self.assertEqual(f1, [p2, p4, p1])
        self.assertEqual(f2, [p2, p3])
        self.assertEqual(f3, [p3, p4])
        self.assertEqual(f4, [p4])


if __name__ == '__main__':
    unittest.main(verbosity=2)
