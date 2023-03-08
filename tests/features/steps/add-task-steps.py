from behave import *
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By

@given(u'I am on the todo list page')
def open_browser(context):
    context.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
    context.driver.implicitly_wait(5)
    context.driver.get("http://127.0.0.1:5000/")


@when('I enter "{title}" in the title field')
def step_impl(context, title):
    title_field = context.driver.find_element(By.NAME, "title")
    title_field.send_keys(title)


@when('I enter "{estimate}" in the estimate field')
def step_impl(context, estimate):
    estimate_field = context.driver.find_element(By.NAME, "estimate")
    estimate_field.send_keys(estimate)


@when(u'I click the "Add" button')
def step_impl(context):
    add_button = context.driver.find_element(By.XPATH, "//button[contains(text(),'Add')]")
    add_button.click()
    context.driver.implicitly_wait(5)


@then('the task "{title}" with estimate "{estimate}" should be added to the todo list')
def step_impl(context, title, estimate):
    dump_text = context.driver.page_source
    print(dump_text)
    assert ("Buy groceries | 2" in dump_text) is True

