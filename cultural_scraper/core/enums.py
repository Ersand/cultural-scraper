from enum import Enum


class ScraperType(str, Enum):
    CCCB = "cccb"
    ATENEU = "ateneu"
    BIBLIOTEQUES = "biblioteques"
    GUIA = "guia"
    TIMEOUT = "timeout"

    @classmethod
    def from_url(cls, url: str) -> "ScraperType":
        url_lower = url.lower()
        if "cccb.org" in url_lower:
            return cls.CCCB
        elif "ateneubcn.cat" in url_lower:
            return cls.ATENEU
        elif "biblioteques" in url_lower:
            return cls.BIBLIOTEQUES
        elif "guia.barcelona.cat" in url_lower:
            return cls.GUIA
        elif "timeout" in url_lower:
            return cls.TIMEOUT
        return cls.CCCB


class DateFilter(str, Enum):
    TODAY = "today"
    TOMORROW = "tomorrow"
    ALL = "all"


class AgeGroup(str, Enum):
    ADULTS = "adults"
    FAMILY = "family"
    ALL = "all"


class OutputFormat(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"
