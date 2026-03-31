from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Any, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from scraper.manager import ScraperManager

logger = logging.getLogger(__name__)


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
