package io.secugrow.demo.pageobjects;

import io.secugrow.demo.webdriversession.WebDriverSession;
import org.openqa.selenium.By;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;

public class WikipediaStartPage extends MainPage {

    public WikipediaStartPage(WebDriverSession session) {
        super(session);
    }

    public WebElement getSearchbar() {
        return getWebDriverWait().until(ExpectedConditions.presenceOfElementLocated(By.id("searchInput")));
    }

    public WikiPediaSearchresultPage submitSearch() {
        getWebDriverWait().until(ExpectedConditions.elementToBeClickable(By.cssSelector("button[type='submit']"))).click();
        return new WikiPediaSearchresultPage(session);
    }

    public WikipediaContentPage searchFor(String searchstring) {
        getSearchbar().sendKeys(searchstring);
        submitSearch();
        return new WikipediaContentPage(session);
    }

    public WikiPediaSearchresultPage searchForResults(String searchstring) {
        getSearchbar().sendKeys(searchstring);
        return submitSearch();
    }
}
