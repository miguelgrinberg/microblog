Feature: Add tasks to todo list
  As a user
  I want to be able to add tasks to my todo list
  So thats I can keep track of my work

  Scenario: User visits the todo list page
    Given the user is on the todo list page
    Then the page should have a text field to enter the title of the task
    And the page should have a text field to enter the estimate of hours needed to complete the task
    And the page should have a button to add the task

  Scenario: Add a new task to the todo list
        Given I am on the todo list page
        When I enter 'Buy groceries' in the title field
        And I enter '2' in the estimate field
        And I click the 'Add' button
        Then the task 'Buy groceries' with estimate '2' should be added to the todo list