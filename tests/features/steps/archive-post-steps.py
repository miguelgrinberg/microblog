from behave import given, when, then
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


@given("I am on the todo list page")
def open_browser(context):

    # Implementation of headless from https://stackoverflow.com/questions/46920243/how-to-configure-chromedriver-to-initiate-chrome-browser-in-headless-mode-throug
    # Stackoverflow post desribes what is goin on with options to enable headless chrome

    options = Options()
    options.add_argument("--headless") # Runs Chrome in headless mode.
    options.add_argument('--no-sandbox') # Bypass OS security model
    options.add_argument('start-maximized') #to maximize viewport this should still be headless
    options.add_argument('disable-infobars')
    options.add_argument("--disable-extensions")
    context.driver = webdriver.Chrome(options=options, service=ChromeService(ChromeDriverManager().install()))
    context.driver.implicitly_wait(5)
    context.driver.get("http://127.0.0.1:5000/")


@when("I enter '{title}' in the title field")
def step_impl(context, title):
    title_field = context.driver.find_element(By.NAME, "title")
    title_field.send_keys(title)


@when("I enter '{estimate}' in the estimate field")
def step_impl(context, estimate):
    estimate_field = context.driver.find_element(By.NAME, "estimate")
    estimate_field.send_keys(estimate)


@when("I click the 'Add' button")
def step_impl(context):
    add_button = context.driver.find_element(By.XPATH, "//button[contains(text(),'Add')]")
    add_button.click()
    context.driver.implicitly_wait(5)


@then("the task '{title}' with estimate '{estimate}' should be added to the todo list")
def step_impl(context, title, estimate):
    dump_text = context.driver.page_source
    print(dump_text)
    assert ("Buy groceries | 2" in dump_text) is True



