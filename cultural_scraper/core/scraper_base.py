from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Any, Optional, TYPE_CHECKING
import logging
import requests
from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from cultural_scraper.data.manager import ScraperManager


@dataclass
class Event:
    title: str
    date: Optional[str] = None
    time: Optional[str] = None
    location: Optional[str] = None
    price: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    source: str = ""
    organizer: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    event_category: Optional[str] = None


class BaseScraper(ABC):
    def __init__(self, name: str, url: str, config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.url = url
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
        self.manager: Optional["ScraperManager"] = None

    @abstractmethod
    def scrape(self) -> list[Event]:
        pass

    def get_timeout(self) -> int:
        return self.config.get("timeout", 30)

    def get_user_agent(self) -> str:
        return self.config.get("user_agent", "CulturalScraper/1.0")

    def fetch_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch URL and return BeautifulSoup. Uses manager session if available."""
        if self.manager:
            return self.manager.fetch_page(url)

        session = requests.Session()
        session.headers.update({"User-Agent": self.get_user_agent()})
        retry_count = self.config.get("retry_count", 3)

        for attempt in range(retry_count):
            try:
                response = session.get(url, timeout=self.get_timeout())
                response.raise_for_status()
                return BeautifulSoup(response.content, "lxml")
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt == retry_count - 1:
                    self.logger.error(f"Failed to fetch {url} after {retry_count} attempts")
                    return None
        return None

    def fetch_json(self, url: str) -> Optional[Any]:
        """Fetch URL and return parsed JSON."""
        session = requests.Session()
        session.headers.update({"User-Agent": self.get_user_agent()})

        try:
            response = session.get(url, timeout=self.get_timeout())
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to fetch JSON from {url}: {e}")
            return None
