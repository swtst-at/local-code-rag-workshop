package at.some.test.stepdefinitions

import at.some.test.pageobjects.WikipediaContentPage
import at.some.test.pageobjects.WikipediaSearchResultPage
import at.some.test.pageobjects.WikipediaStartPage
import org.assertj.core.api.Assertions.assertThat

class SearchSteps(testDataContainer: TestDataContainer) : AbstractStepDefs(testDataContainer) {

    init {
        When("the user searches for {string}") { term: String ->
            getPage(WikipediaStartPage::class).searchForResults(term)
        }

        Then("at least {int} search result(s) is/are shown") { minimum: Int ->
            assertThat(getPage(WikipediaSearchResultPage::class).getResultTitles()).hasSizeGreaterThanOrEqualTo(minimum)
        }

        When("search result {int} is opened") { position: Int ->
            getPage(WikipediaSearchResultPage::class).openResult(position - 1)
        }

        Then("the article header is not empty") {
            assertThat(getPage(WikipediaContentPage::class).getHeader()).isNotBlank()
        }
    }
}
