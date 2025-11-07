import pytest
from flask import url_for
from app import db
from app.models import User, Message
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

@pytest.mark.usefixtures("live_server")
def test_home_page(driver, app):
    url = url_for("main.index", _external=True)
    driver.get(url)
    assert "Sign In - Microblog" in driver.title

@pytest.mark.usefixtures("live_server")
def test_notifications(driver, app):
    driver.maximize_window()

    with app.app_context():
        user1 = User(username="user1", email="user1@example.com")
        user1.set_password("password1")
        user2 = User(username="user2", email="user2@example.com")
        user2.set_password("password2")
        db.session.add_all([user1, user2])
        db.session.commit()

        post = Message(body="Hello user2!", sender_id=user1.id, recipient_id=user2.id)
        db.session.add(post)
        db.session.commit()

    login_url = url_for("auth.login", _external=True)
    driver.get(login_url)

    username_field = driver.find_element(By.NAME, "username")
    username_field.clear()
    username_field.send_keys("user2")

    password_field = driver.find_element(By.NAME, "password")
    password_field.clear()
    password_field.send_keys("password2")

    submit_button = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="submit"], button[type="submit"], input[name="submit"]'))
    )
    submit_button.click()
    
    index_url = url_for("main.index", _external=True)
    driver.get(index_url)

    messages_span = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href="/messages"] span'))
    )

    style_attr = messages_span.get_attribute("style") or ""
    assert "visibility: visible" in style_attr
    assert messages_span.text.strip() == "1"

