from dataclasses import dataclass, field
from typing import Any
from cultural_scraper.core import BaseScraper, Event


@dataclass
class TimeoutEventResult:
    events: list[Event] = field(default_factory=list)
    detail_urls: list[str] = field(default_factory=list)
    venue_urls: list[str] = field(default_factory=list)


class TimeoutScraper(BaseScraper):
    """
    Scraper for Time Out Barcelona
    Website: https://www.timeout.es/barcelona/es

    Iteratively scrapes:
    - First pass: get article links from listings and detail pages
    - Second pass: scrape each article detail page for actual dates
    - For venues (restaurants, etc.): scrape for events if available
    """

    SECTIONS: list[tuple[str, str]] = [
        ("/barcelona/es/que-hacer", "Que fer"),
        ("/barcelona/es/teatro", "Teatre"),
        ("/barcelona/es/musica", "Música"),
        ("/barcelona/es/cine", "Cinema"),
        ("/barcelona/es/arte", "Art"),
        ("/barcelona/es/ninos", "Família"),
        ("/barcelona/es/comer-beber", "Gastronomia"),
    ]

    def __init__(self, name: str, url: str, config: dict[str, Any] | None = None) -> None:
        super().__init__(name, url, config)
        self.organizer_cache: dict[str, str] = {}

    def scrape(self) -> list[Event]:
        all_events = []
        visited_urls: set[str] = set()

        urls_to_scrape = [self.url]
        for path, category in self.SECTIONS:
            section_url = f"https://www.timeout.es{path}"
            if section_url not in urls_to_scrape:
                urls_to_scrape.append(section_url)

        self.logger.info(f"Scraping {len(urls_to_scrape)} Timeout sections")

        day_events = []
        permanent_venues = []
        all_article_urls = []

        for url in urls_to_scrape:
            if url in visited_urls:
                continue
            visited_urls.add(url)

            self.logger.info(f"Scraping listing: {url[:60]}")
            result = self._scrape_listing(url)

            all_article_urls.extend(result.detail_urls)
            permanent_venues.extend(result.venue_urls)

            day_events.extend(result.events)

        self.logger.info(
            f"Day events from listings: {len(day_events)}, Venue URLs: {len(permanent_venues)}"
        )

        visited_articles = set()
        for article_url in all_article_urls:
            if article_url in visited_articles or article_url in visited_urls:
                continue
            visited_articles.add(article_url)

            article_result = self._scrape_detail_page(article_url)
            if article_result.events:
                day_events.extend(article_result.events)

        for venue_url in permanent_venues:
            if venue_url in visited_urls:
                continue

            venue_result = self._scrape_detail_page(venue_url)
            if venue_result.events:
                self.logger.info(
                    f"Found {len(venue_result.events)} events from venue: {venue_url[:40]}"
                )
                day_events.extend(venue_result.events)

        all_events = day_events
        self.logger.info(f"Total Timeout events: {len(all_events)}")
        return all_events

    def _scrape_listing(self, url: str) -> TimeoutEventResult:
        if not self.manager:
            return TimeoutEventResult()
        soup = self.manager.fetch_page(url)
        if not soup:
            return TimeoutEventResult()

        result = TimeoutEventResult()
        category = self._get_category_from_url(url)

        articles = soup.select("article")
        if not articles:
            articles = soup.select(".Card, .m-Teaser, .list-item, .teaser")

        for article in articles:
            try:
                link = article.select_one("a")
                if not link:
                    continue

                href = str(link.get("href", ""))
                if not href or href.startswith("#") or href.startswith("javascript"):
                    continue

                if href.startswith("/"):
                    href = f"https://www.timeout.es{href}"

                title_elem = article.select_one('h2, h3, [class*="title"], .title')
                title = str(title_elem.get_text(strip=True)) if title_elem else ""

                result.detail_urls.append(href)

                date_elem = article.select_one(
                    "[class*='date'], .date, time, [datetime], .published"
                )
                date_text: str | None = None
                if date_elem:
                    date_text = str(date_elem.get("datetime") or date_elem.get_text(strip=True))

                is_venue = "/comer-beber/" in href or "/restaurante/" in href.lower()

                if date_text and not self._is_permanent_date(date_text):
                    event = Event(
                        title=title,
                        date=date_text,
                        location=None,
                        url=href,
                        source=self.name,
                        organizer=title,
                        tags=[category, "Time Out"] if category else ["Time Out"],
                    )
                    result.events.append(event)
                elif is_venue:
                    result.venue_urls.append(href)

            except Exception as e:
                self.logger.warning(f"Error parsing Timeout listing: {e}")
                continue

        return result

    def _scrape_detail_page(self, url: str) -> TimeoutEventResult:
        if not self.manager:
            return TimeoutEventResult()
        soup = self.manager.fetch_page(url)
        if not soup:
            return TimeoutEventResult()

        result = TimeoutEventResult()

        try:
            title_elem = soup.select_one("h1, [class*='title']")
            title = str(title_elem.get_text(strip=True)) if title_elem else ""

            date_selectors = [
                "[class*='date']",
                "time[datetime]",
                ".event-date",
                ".date-published",
                "[property='datePublished']",
                ".meta__date",
                ".date",
            ]

            date_text: str | None = None
            for selector in date_selectors:
                date_elem = soup.select_one(selector)
                if date_elem:
                    date_text = str(date_elem.get("datetime") or date_elem.get_text(strip=True))
                    break

            if date_text and not self._is_permanent_date(date_text):
                event = Event(
                    title=title,
                    date=date_text,
                    location=None,
                    url=url,
                    source=self.name,
                    organizer=title,
                    tags=["Time Out"],
                )
                result.events.append(event)
            elif not date_text:
                result.venue_urls.append(url)

        except Exception as e:
            self.logger.warning(f"Error parsing Timeout detail page: {e}")

        return result

    def _is_permanent_date(self, date_text: str) -> bool:
        if not date_text:
            return False
        permanent_keywords = [
            "permanent",
            "permanent",
            "obra",
            "exposició permanent",
            "sempre",
        ]
        return any(kw in date_text.lower() for kw in permanent_keywords)

    def _get_category_from_url(self, url: str) -> str:
        for path, category in self.SECTIONS:
            if path in url:
                return category
        return "Que fer"
