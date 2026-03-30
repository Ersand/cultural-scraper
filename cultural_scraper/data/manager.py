import requests
from bs4 import BeautifulSoup
import logging
from typing import Any, Optional
from cultural_scraper.core import BaseScraper, Event

logger = logging.getLogger(__name__)


class ScraperManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.scrapers: list[BaseScraper] = []
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
        self._configure_session()

    def _configure_session(self) -> None:
        timeout = self.config.get("scraper", {}).get("timeout", 30)
        user_agent = self.config.get("scraper", {}).get("user_agent", "")

        self.session.headers.update({"User-Agent": user_agent})
        self.session.timeout = timeout

    def register_scraper(self, scraper: BaseScraper) -> None:
        scraper.manager = self
        self.scrapers.append(scraper)
        logger.info(f"Registered scraper: {scraper.name}")

    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        retry_count = self.config.get("scraper", {}).get("retry_count", 3)

        for attempt in range(retry_count):
            try:
                response = self.session.get(url)
                response.raise_for_status()
                return BeautifulSoup(response.content, "lxml")
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt == retry_count - 1:
                    logger.error(f"Failed to fetch {url} after {retry_count} attempts")
                    return None
        return None

    def run_all(self) -> dict[str, list[Event]]:
        results: dict[str, list[Event]] = {}
        errors: list[str] = []

        for scraper in self.scrapers:
            try:
                self.logger.info(f"Running scraper: {scraper.name}")
                events = scraper.scrape()
                results[scraper.name] = events
                self.logger.info(f"Found {len(events)} events from {scraper.name}")
            except Exception as e:
                error_msg = f"Error in {scraper.name}: {e}"
                self.logger.error(error_msg)
                errors.append(error_msg)
                results[scraper.name] = []

        if errors and self.config.get("output", {}).get("show_errors", True):
            results["_errors"] = errors  # type: ignore[assignment]

        return results

    def close(self) -> None:
        self.session.close()
