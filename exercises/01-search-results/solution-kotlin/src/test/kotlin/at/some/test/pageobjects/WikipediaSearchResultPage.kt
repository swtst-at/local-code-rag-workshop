package at.some.test.pageobjects

import at.some.test.driverutil.WebDriverSession
import org.openqa.selenium.By
import org.openqa.selenium.WebElement
import org.openqa.selenium.support.ui.ExpectedConditions

class WikipediaSearchResultPage(session: WebDriverSession) : MainPage(session) {

    private val resultLinks = By.cssSelector("li.mw-search-result .mw-search-result-heading a")

    private fun results(): List<WebElement> =
        wdwait.until(ExpectedConditions.presenceOfAllElementsLocatedBy(resultLinks))

    fun getResultTitles(): List<String> = results().map { it.text }

    fun openResult(index: Int): WikipediaContentPage {
        results()[index].click()
        return WikipediaContentPage(session)
    }
}
