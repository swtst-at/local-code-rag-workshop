package at.some.test.pageobjects;

import at.some.test.driverutil.WebDriverSession
import org.openqa.selenium.By
import org.openqa.selenium.support.ui.ExpectedConditions

class WikipediaStartPage(session: WebDriverSession) : MainPage(session) {

    fun isSearchbarPresent(): Boolean {
        return webDriver.findElements(By.id("searchInput")).size >= 1
    }

    fun submitSearch(): WikipediaContentPage {
        wdwait.until(ExpectedConditions.elementToBeClickable(By.cssSelector("button[type='submit']"))).click()
        return WikipediaContentPage(session)
    }

    fun searchFor(searchstring: String): WikipediaContentPage {
        wdwait.until { driver ->
            requireNotNull(
                ExpectedConditions.presenceOfElementLocated(By.id("searchInput")).apply(driver)
            ) { "Searchbar not found" }
        }.sendKeys(searchstring)
        return submitSearch()
    }

    fun searchForResults(searchstring: String): WikipediaSearchResultPage {
        wdwait.until { driver ->
            requireNotNull(
                ExpectedConditions.presenceOfElementLocated(By.id("searchInput")).apply(driver)
            ) { "Searchbar not found" }
        }.sendKeys(searchstring)
        wdwait.until(ExpectedConditions.elementToBeClickable(By.cssSelector("button[type='submit']"))).click()
        return WikipediaSearchResultPage(session)
    }
}
