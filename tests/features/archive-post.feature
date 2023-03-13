Feature: Archive Posts
  As a user,
  I would like to archive posts
  so i can view the post even if the original post is deleted

  Scenario: Successfully archive a post
    Given that I am on a explore page
    When I click on the "Archive" link on a post
    Then the link should change to "Remove from Archive"
    And a banner shows that the post has been archived


  Scenario: Successfully remove an archived post from the explore page
    Given that I am on an review page
    When I click on the "Remove from Archive" link
    Then the link should change to "Archive"
    And a banner shows that the post has been removed from my archives


  Scenario: Successfully remove an archived post from the archived page
    Given that I am on an archived page
    When I click on the "Remove from Archive" link
    Then the archived post should disappear
    And a banner shows that the post has been removed from my archives


  Scenario: View archived posts
    Given that I am on my user profile page
    When I click on the "View Archived Posts" link
    Then I should be directed to a page displaying all my archived posts
