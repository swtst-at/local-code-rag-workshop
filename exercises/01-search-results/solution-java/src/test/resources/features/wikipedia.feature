@all
Feature: [wikipedia] Example Feature

  @boris
  Scenario: [WIK-01 [wikipedia]
    Given the start page is loaded
    Then the searchbar is visible
    When the Selenium page is opened
    Then the header should be "Selenium"

  @search
  Scenario: [WIK-03 [wikipedia]
    Given the start page is loaded
    When the user searches for "selenium webdriver page object"
    Then at least 1 search result is shown
    When search result 1 is opened
    Then the article header is not empty
