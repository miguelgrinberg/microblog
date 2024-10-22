Feature: User login

  Scenario: Successful login with valid credentials
    Given a user is on the login page
    When the user enters valid credentials
    Then the user should be redirected to the home page

  Scenario: Failed login with invalid credentials
    Given a user is on the login page
    When the user enters invalid credentials
    Then an error message should be displayed
