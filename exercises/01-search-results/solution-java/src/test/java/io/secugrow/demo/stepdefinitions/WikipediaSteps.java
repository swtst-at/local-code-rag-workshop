package io.secugrow.demo.stepdefinitions;

import io.secugrow.demo.pageobjects.WikiPediaSearchresultPage;
import io.secugrow.demo.pageobjects.WikipediaContentPage;
import io.secugrow.demo.pageobjects.WikipediaStartPage;
import io.secugrow.demo.utils.TestDataContainer;
import org.openqa.selenium.WebElement;

import static org.assertj.core.api.Assertions.assertThat;

public class WikipediaSteps extends AbstractStepDefs {

    TestDataContainer testDataContainer;

    public WikipediaSteps(TestDataContainer testDc) {
        super(testDc);
        testDataContainer = testDc;

        Given("the start page is loaded", () -> {
            getCurrentWebDriver().navigate().to(testDataContainer.getBaseUrl());
            new WikipediaStartPage(getCurrentWebDriverSession());
        });

        Then("the searchbar is visible", () -> {
            WebElement searchbar = getPage(WikipediaStartPage.class).getSearchbar();
            assertThat(searchbar.isEnabled()).isTrue();
        });

        When("the Selenium page is opened", () -> {
            getPage(WikipediaStartPage.class).searchFor("Selenium");
        });

        Then("the header should be {string}", (String expected_header) -> assertThat(expected_header).isEqualTo(getPage(WikipediaContentPage.class).getHeader()));

        // ── Search results (exercise 01) ──────────────────────────────────────
        // Added to this class on purpose: a second step class extending the abstract AbstractStepDefs
        // makes picocontainer fail with AmbiguousComponentResolutionException (see the exercise notes).

        When("the user searches for {string}", (String term) -> {
            getPage(WikipediaStartPage.class).searchForResults(term);
        });

        Then("at least {int} search result(s) is/are shown", (Integer minimum) -> {
            assertThat(getPage(WikiPediaSearchresultPage.class).getResultTitles()).hasSizeGreaterThanOrEqualTo(minimum);
        });

        When("search result {int} is opened", (Integer position) -> {
            getPage(WikiPediaSearchresultPage.class).openResult(position - 1);
        });

        Then("the article header is not empty", () -> {
            assertThat(getPage(WikipediaContentPage.class).getHeader()).isNotBlank();
        });

    }
}
