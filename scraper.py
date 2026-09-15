"""
Dynamic (JS-rendered) site scraper -- Selenium + selenium-stealth.

Use this pattern when a site renders its content with JavaScript
after page load, so a plain requests+BeautifulSoup scraper would just
see an empty shell. Runs against quotes.toscrape.com/js -- a public
sandbox built to mimic exactly that kind of site -- as a stand-in for
a real target (e.g. a dashboard, a listings site with infinite
scroll, or a page behind a "Load more" button).

What this demonstrates for a client-facing gig:
  - Handling JS-rendered content a static scraper can't see
  - selenium-stealth to reduce automation fingerprinting on sites
    that actively try to detect and block headless browsers
  - webdriver-manager so the client never has to manually download or
    match a ChromeDriver version -- one less thing that breaks on
    their machine
  - Real error handling: retries with backoff, logging, and a script
    that keeps going instead of crashing on one bad page
"""

import csv
import logging
import time
from dataclasses import dataclass, asdict

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("dynamic_scraper")

BASE_URL = "https://quotes.toscrape.com/js/"
MAX_RETRIES = 3
PAGE_LOAD_TIMEOUT = 15


@dataclass
class Quote:
    text: str
    author: str
    tags: str
    source_page: str


def build_driver(headless: bool = True) -> webdriver.Chrome:
    """Creates a Chrome driver with stealth patches applied.

    webdriver-manager handles fetching the right ChromeDriver binary
    automatically, so this runs the same on the client's machine as
    on yours without a manual driver install step.
    """
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1366,900")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Masks common automation fingerprints (navigator.webdriver, etc.)
    # that anti-bot systems check for.
    stealth(
        driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver


def fetch_page_with_retries(driver, url: str) -> bool:
    """Loads a URL, retrying on timeout/transient errors.

    This is the difference between a script that survives a 6-hour
    unattended run and one that dies at page 4 of 40 because of one
    slow response.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            driver.get(url)
            WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                EC.presence_of_element_located((By.CLASS_NAME, "quote"))
            )
            return True
        except (TimeoutException, WebDriverException) as exc:
            wait = 2 ** attempt  # exponential backoff: 2s, 4s, 8s
            log.warning(
                f"Attempt {attempt}/{MAX_RETRIES} failed for {url} "
                f"({exc.__class__.__name__}). Retrying in {wait}s."
            )
            time.sleep(wait)
    log.error(f"Giving up on {url} after {MAX_RETRIES} attempts.")
    return False


def scrape_quotes(driver) -> list[Quote]:
    results: list[Quote] = []
    page_num = 1

    while True:
        url = f"{BASE_URL}page/{page_num}/"
        log.info(f"Fetching page {page_num}: {url}")

        if not fetch_page_with_retries(driver, url):
            break

        quote_elements = driver.find_elements(By.CLASS_NAME, "quote")
        if not quote_elements:
            log.info("No more quotes found -- reached the last page.")
            break

        for el in quote_elements:
            text = el.find_element(By.CLASS_NAME, "text").text
            author = el.find_element(By.CLASS_NAME, "author").text
            tags = [t.text for t in el.find_elements(By.CLASS_NAME, "tag")]
            results.append(
                Quote(text=text, author=author, tags=", ".join(tags), source_page=url)
            )

        page_num += 1

    return results


def save_to_csv(quotes: list[Quote], filepath: str = "output.csv") -> None:
    if not quotes:
        log.warning("Nothing to save -- quote list is empty.")
        return
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=asdict(quotes[0]).keys())
        writer.writeheader()
        for q in quotes:
            writer.writerow(asdict(q))
    log.info(f"Saved {len(quotes)} records to {filepath}")


def main():
    driver = build_driver(headless=True)
    try:
        quotes = scrape_quotes(driver)
        save_to_csv(quotes)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
