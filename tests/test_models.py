from datetime import datetime, timezone, timedelta
import hashlib

import pytest

from app import db
from app.models import User, Post
# from tests.utils import app


def test_password_hashing(app):
    u = User(username='susan', email='susan@example.com')
    u.set_password('cat')
    assert not u.check_password('dog')
    assert u.check_password('cat')


def test_avatar(app):
    email = 'john@example.com'
    u = User(username='john', email=email)
    email_hash = hashlib.md5(email.encode('utf-8')).hexdigest()
    assert u.avatar(128) == \
        f'https://www.gravatar.com/avatar/{email_hash}?d=identicon&s=128'


def test_follow(app):
    u1 = User(username='john', email='john@example.com')
    u2 = User(username='susan', email='susan@example.com')
    db.session.add(u1)
    db.session.add(u2)
    db.session.commit()
    following = db.session.scalars(u1.following.select()).all()
    followers = db.session.scalars(u2.followers.select()).all()
    assert following == []
    assert followers == []

    u1.follow(u2)
    db.session.commit()
    assert u1.is_following(u2)
    assert u1.following_count() == 1
    assert u2.followers_count() == 1
    u1_following = db.session.scalars(u1.following.select()).all()
    u2_followers = db.session.scalars(u2.followers.select()).all()
    assert u1_following[0].username == 'susan'
    assert u2_followers[0].username == 'john'

    u1.unfollow(u2)
    db.session.commit()
    assert not u1.is_following(u2)
    assert u1.following_count() == 0
    assert u2.followers_count() == 0


def test_follow_posts(app):
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
    assert f1 == [p2, p4, p1]
    assert f2 == [p2, p3]
    assert f3 == [p3, p4]
    assert f4 == [p4]
