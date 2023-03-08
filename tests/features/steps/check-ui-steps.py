from behave import *
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By


@given(u'the user is on the todo list page')
def open_browser(context):
    context.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
    context.driver.implicitly_wait(5)
    context.driver.get("http://127.0.0.1:5000/")


@then(u'the page should have a text field to enter the title of the task')
def check_task_title_textbox(context):
    status = context.driver.find_element(By.NAME, "title").is_displayed()
    assert status is True


@then(u'the page should have a text field to enter the estimate of hours needed to complete the task')
def check_task_estimate_textbox(context):
    status = context.driver.find_element(By.NAME, "estimate").is_displayed()
    assert status is True


@then(u'the page should have a button to add the task')
def check_task_add_button(context):
    status = context.driver.find_element(By.XPATH, "//button[contains(text(),'Add')]").is_displayed()
    assert status is True
