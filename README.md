# Dynamic Site Scraper (Selenium + selenium-stealth)

For sites that render content client-side with JavaScript -- infinite
scroll feeds, dashboards, "Load more" buttons -- where a plain HTTP
request just returns an empty page shell.

## What this demonstrates for a client-facing gig

- Real browser automation via Selenium, driven headlessly for
  unattended runs
- `selenium-stealth` to reduce fingerprints that anti-bot systems
  check for (`navigator.webdriver`, WebGL vendor strings, etc.)
- `webdriver-manager` so there's no manual ChromeDriver
  install/version-matching step on the client's machine
- Retry-with-backoff on every page load, plus structured logging --
  the script reports what it's doing and recovers from transient
  failures instead of crashing

## Run it

```bash
pip install -r requirements.txt
python scraper.py
```

Output lands in `output.csv`.

## Adapting for a real client job

- Swap `BASE_URL` and the `By.CLASS_NAME` selectors for the target
  site's actual structure
- For infinite-scroll pages (no numbered pagination), replace the
  `page_num` loop with a scroll-and-wait loop:
  `driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")`
  then wait for new elements to appear
- If the target site requires login, add a one-time authenticated
  session step before the scrape loop

## When to reach for this vs. Scrapy

Use Scrapy (see project 01) by default -- it's faster and lighter.
Reach for Selenium only when the content genuinely doesn't exist in
the page source until JavaScript runs, or the flow needs real
interaction (clicks, scrolls, form fills, login).
