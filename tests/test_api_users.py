import base64
import pytest

from app import db
from app.models import User
# from tests.utils import app

def _basic_auth_header(username, password):
    token = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')
    return {'Authorization': f'Basic {token}'}

def test_get_user(app):
    # create a user and commit to DB
    u = User(username='john', email='john@example.com')
    u.set_password('cat')
    db.session.add(u)
    db.session.commit()

    with app.test_client() as client:
        # obtain token via basic auth (POST /api/tokens)
        res = client.post('/api/tokens', headers=_basic_auth_header('john', 'cat'))
        assert res.status_code == 200
        token = res.get_json()['token']

        # request the user with the Bearer token
        res = client.get(f'/api/users/{u.id}', headers={'Authorization': f'Bearer {token}'})
        assert res.status_code == 200
        data = res.get_json()
        assert data['id'] == u.id
        assert data['username'] == 'john'

def test_get_multiple_users(app):
    u1 = User(username='john', email='john@example.com')
    u1.set_password('cat')
    db.session.add(u1)
    db.session.commit()

    u2 = User(username='greg', email='greg@example.com')
    u2.set_password('dog')
    db.session.add(u2)
    db.session.commit()

    with app.test_client() as client:
        # obtain token via basic auth (POST /api/tokens)
        res = client.post('/api/tokens', headers=_basic_auth_header('john', 'cat'))
        assert res.status_code == 200
        token = res.get_json()['token']

        res = client.get(f'/api/users', headers={'Authorization': f'Bearer {token}'})
        assert res.status_code == 200
        data = res.get_json()

        assert len(data['items']) == 2

def test_get_followers(app):
    u1 = User(username='john', email='john@example.com')
    u1.set_password('cat')
    db.session.add(u1)
    db.session.commit()

    u2 = User(username='greg', email='greg@example.com')
    u2.set_password('dog')
    db.session.add(u2)
    db.session.commit()

    u1.follow(u2) # u2 has 1 follower: u1

    with app.test_client() as client:
        # obtain token via basic auth (POST /api/tokens)
        res = client.post('/api/tokens', headers=_basic_auth_header('john', 'cat'))
        assert res.status_code == 200
        token = res.get_json()['token']

        res = client.get(f'/api/users/{u2.id}/followers', headers={'Authorization': f'Bearer {token}'})
        assert res.status_code == 200
        data = res.get_json()

        assert len(data['items']) == 1
        assert data['items'][0]['id'] == 1

def test_get_following(app):
    u1 = User(username='john', email='john@example.com')
    u1.set_password('cat')
    db.session.add(u1)
    db.session.commit()

    u2 = User(username='greg', email='greg@example.com')
    u2.set_password('dog')
    db.session.add(u2)
    db.session.commit()

    u1.follow(u2) # u1 is following 1 user: u2

    with app.test_client() as client:
        # obtain token via basic auth (POST /api/tokens)
        res = client.post('/api/tokens', headers=_basic_auth_header('john', 'cat'))
        assert res.status_code == 200
        token = res.get_json()['token']

        res = client.get(f'/api/users/{u1.id}/following', headers={'Authorization': f'Bearer {token}'})
        assert res.status_code == 200
        data = res.get_json()

        assert len(data['items']) == 1
        assert data['items'][0]['id'] == 2

def test_create_user(app):

    with app.test_client() as client:
        # correct data case
        payload = {
            'username': 'john',
            'password': 'cat',
            'email': 'john@example.com',
        }
        res = client.post('/api/users', json=payload)
        assert res.status_code in (200, 201)
        data = res.get_json()
        assert data is not None
        assert data.get('username') == 'john'
        # DB should contain the new user
        saved = User.query.filter_by(username='john').first()
        assert saved is not None
        assert saved.email == 'john@example.com'

        # conflicting username (same username, different email)
        payload_conflict_username = {
            'username': 'john',
            'password': 'cat2',
            'email': 'other@example.com',
        }
        res = client.post('/api/users', json=payload_conflict_username)
        assert res.status_code == 400

        # conflicting email (different username, same email)
        payload_conflict_email = {
            'username': 'another',
            'password': 'cat2',
            'email': 'john@example.com',
        }
        res = client.post('/api/users', json=payload_conflict_email)
        assert res.status_code == 400

        # empty payload
        res = client.post('/api/users', json={})
        assert res.status_code == 400

def test_update_user(app):
    # create two users
    u1 = User(username='john', email='john@example.com')
    u1.set_password('cat')
    u2 = User(username='greg', email='greg@example.com')
    u2.set_password('dog')
    db.session.add_all([u1, u2])
    db.session.commit()

    with app.test_client() as client:
        # obtain token for u1
        res = client.post('/api/tokens', headers=_basic_auth_header('john', 'cat'))
        assert res.status_code == 200
        token1 = res.get_json()['token']

        # u1 updates own profile
        update_payload = {'username': 'johnny', 'email': 'johnny@example.com'}
        res = client.put(f'/api/users/{u1.id}', json=update_payload,
                         headers={'Authorization': f'Bearer {token1}'})
        assert res.status_code == 200
        data = res.get_json()
        assert data.get('username') == 'johnny'
        # verify DB updated
        updated = db.session.get(User, u1.id)
        assert updated.username == 'johnny'
        assert updated.email == 'johnny@example.com'

        # try to change username to one already taken by u2 -> should fail
        conflict_payload = {'username': 'greg'}
        res = client.put(f'/api/users/{u1.id}', json=conflict_payload,
                         headers={'Authorization': f'Bearer {token1}'})
        assert res.status_code == 400

        # obtain token for u2 and try to update u1 -> should be forbidden
        res = client.post('/api/tokens', headers=_basic_auth_header('greg', 'dog'))
        assert res.status_code == 200
        token2 = res.get_json()['token']

        res = client.put(f'/api/users/{u1.id}', json={'username': 'hacker'},
                         headers={'Authorization': f'Bearer {token2}'})
        assert res.status_code in (403, 401)