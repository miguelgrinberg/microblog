from behave import given, when, then
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

#THESE ARE EXAMPLES FILES.
#Todo delete these once we set a standard with our own tests

@given("the user is on the todo list page")
def open_browser(context):
    options = Options()
    options.add_argument("--headless") # Runs Chrome in headless mode.
    options.add_argument('--no-sandbox') # Bypass OS security model
    options.add_argument('start-maximized') #to maximize viewport this should still be headless
    options.add_argument('disable-infobars')
    options.add_argument("--disable-extensions")
    context.driver = webdriver.Chrome(options=options, service=ChromeService(ChromeDriverManager().install()))
    context.driver.implicitly_wait(5)
    context.driver.get("http://127.0.0.1:5000/")


@then("the page should have a text field to enter the title of the task")
def check_task_title_textbox(context):
    status = context.driver.find_element(By.NAME, "title").is_displayed()
    assert status is True


@then("the page should have a text field to enter the estimate of hours needed to complete the task")
def check_task_estimate_textbox(context):
    status = context.driver.find_element(By.NAME, "estimate").is_displayed()
    assert status is True


@then("the page should have a button to add the task")
def check_task_add_button(context):
    status = context.driver.find_element(By.XPATH, "//button[contains(text(),'Add')]").is_displayed()
    assert status is True
