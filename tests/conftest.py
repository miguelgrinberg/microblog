import os
import sys


# ensure the project root is on sys.path so tests can import the `tests` package
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest
# from app import create_app, db
# from config import Config

# class TestConfig(Config):
#     TESTING = True
#     SQLALCHEMY_DATABASE_URI = "sqlite://"
#     ELASTICSEARCH_URL = None

# @pytest.fixture(scope="session")
# def app():
#     app = create_app(TestConfig)
#     with app.app_context():
#         db.create_all()
#     yield app
#     with app.app_context():
#         db.drop_all()

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

@pytest.fixture(scope="session")
def driver():
    opts = Options()
    # opts.add_argument("--headless=new")
    # opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    yield drv
    drv.quit()


import pytest

from app import create_app, db
from app.models import User
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(ROOT, 'test.db')
    ELASTICSEARCH_URL = None

@pytest.fixture(scope="session")
def app():
    app = create_app(TestConfig)
    ctx = app.app_context()
    ctx.push()
    db.create_all()
    try:
        yield app
    finally:
        db.session.remove()
        db.drop_all()
        ctx.pop()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Ensure the database is empty before each test.

    The `app` fixture is session-scoped (to satisfy session-scoped fixtures
    such as `live_server` and `driver`). To keep tests isolated we delete
    all rows from every table before and after each test.
    """
    # remove any leftover state
    db.session.remove()
    for table in reversed(db.metadata.sorted_tables):
        db.session.execute(table.delete())
    db.session.commit()
    try:
        yield
    finally:
        db.session.remove()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()