package io.secugrow.demo.pageobjects;

import io.secugrow.demo.webdriversession.WebDriverSession;
import org.openqa.selenium.By;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;

import java.util.List;

public class WikiPediaSearchresultPage extends MainPage{

    private static final By RESULT_LINKS = By.cssSelector("li.mw-search-result .mw-search-result-heading a");

    public WikiPediaSearchresultPage(WebDriverSession session) {
        super(session);
    }

    public WikipediaContentPage openFromResults(String partLink) {
        logger.info("::: some logmessage for testing purposes :::");
        getWebDriver().findElement(By.cssSelector("li.mw-search-result a[href='" + partLink + "']")).click();
        return new WikipediaContentPage(session);
    }

    private List<WebElement> results() {
        return getWebDriverWait().until(ExpectedConditions.presenceOfAllElementsLocatedBy(RESULT_LINKS));
    }

    public List<String> getResultTitles() {
        return results().stream().map(WebElement::getText).toList();
    }

    public WikipediaContentPage openResult(int index) {
        results().get(index).click();
        return new WikipediaContentPage(session);
    }
}
