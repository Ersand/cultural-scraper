from dataclasses import dataclass, field
from cultural_scraper.core import BaseScraper, Event


@dataclass
class TimeoutEventResult:
    events: list[Event] = field(default_factory=list)
    detail_urls: list[str] = field(default_factory=list)
    venue_urls: list[str] = field(default_factory=list)


class TimeoutScraper(BaseScraper):
    """Scraper for Time Out Barcelona."""

    BASE_URL = "https://www.timeout.es"

    SECTIONS: list[tuple[str, str]] = [
        ("/barcelona/es/que-hacer", "Que fer"),
        ("/barcelona/es/teatro", "Teatre"),
        ("/barcelona/es/musica", "Música"),
        ("/barcelona/es/cine", "Cinema"),
        ("/barcelona/es/arte", "Art"),
        ("/barcelona/es/ninos", "Família"),
        ("/barcelona/es/comer-beber", "Gastronomia"),
    ]

    PERMANENT_KEYWORDS = {"permanent", "obra", "exposició permanent", "sempre"}

    def scrape(self) -> list[Event]:
        urls_to_scrape = [self.url] + [f"{self.BASE_URL}{path}" for path, _ in self.SECTIONS]

        visited_urls: set[str] = set()
        day_events: list[Event] = []
        all_article_urls: list[str] = []
        permanent_venues: list[str] = []

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
            f"Listing events: {len(day_events)}, Article URLs: {len(all_article_urls)}"
        )

        visited_articles: set[str] = set()
        for article_url in all_article_urls:
            if article_url in visited_articles or article_url in visited_urls:
                continue
            visited_articles.add(article_url)

            article_result = self._scrape_detail(article_url)
            day_events.extend(article_result.events)

        for venue_url in permanent_venues:
            if venue_url in visited_urls:
                continue
            venue_result = self._scrape_detail(venue_url)
            if venue_result.events:
                day_events.extend(venue_result.events)

        self.logger.info(f"Total Timeout events: {len(day_events)}")
        return day_events

    def _scrape_listing(self, url: str) -> TimeoutEventResult:
        soup = self.fetch_soup(url)
        if not soup:
            return TimeoutEventResult()

        result = TimeoutEventResult()
        category = self._get_category(url)

        articles = soup.select("article") or soup.select(".Card, .m-Teaser, .list-item, .teaser")

        for article in articles:
            try:
                link = article.select_one("a")
                if not link:
                    continue

                href = str(link.get("href", ""))
                if not href or href.startswith(("#", "javascript")):
                    continue
                if href.startswith("/"):
                    href = f"{self.BASE_URL}{href}"

                title_elem = article.select_one("h2, h3, [class*='title'], .title")
                title = title_elem.get_text(strip=True) if title_elem else ""

                result.detail_urls.append(href)

                date_elem = article.select_one(
                    "[class*='date'], .date, time, [datetime], .published"
                )
                date_text = None
                if date_elem:
                    date_text = str(date_elem.get("datetime") or date_elem.get_text(strip=True))

                if date_text and not self._is_permanent(date_text):
                    result.events.append(
                        Event(
                            title=title,
                            date=date_text,
                            url=href,
                            source=self.name,
                            organizer=title,
                            tags=[category, "Time Out"] if category else ["Time Out"],
                        )
                    )
                elif "/comer-beber/" in href or "/restaurante/" in href.lower():
                    result.venue_urls.append(href)
            except Exception as e:
                self.logger.warning(f"Error parsing Timeout listing: {e}")

        return result

    def _scrape_detail(self, url: str) -> TimeoutEventResult:
        soup = self.fetch_soup(url)
        if not soup:
            return TimeoutEventResult()

        result = TimeoutEventResult()

        try:
            title_elem = soup.select_one("h1, [class*='title']")
            title = title_elem.get_text(strip=True) if title_elem else ""

            date_text = None
            for selector in [
                "[class*='date']",
                "time[datetime]",
                ".event-date",
                ".date-published",
                "[property='datePublished']",
                ".meta__date",
                ".date",
            ]:
                date_elem = soup.select_one(selector)
                if date_elem:
                    date_text = str(date_elem.get("datetime") or date_elem.get_text(strip=True))
                    break

            if date_text and not self._is_permanent(date_text):
                result.events.append(
                    Event(
                        title=title,
                        date=date_text,
                        url=url,
                        source=self.name,
                        organizer=title,
                        tags=["Time Out"],
                    )
                )
            elif not date_text:
                result.venue_urls.append(url)
        except Exception as e:
            self.logger.warning(f"Error parsing Timeout detail: {e}")

        return result

    def _is_permanent(self, date_text: str) -> bool:
        lower = date_text.lower()
        return any(kw in lower for kw in self.PERMANENT_KEYWORDS)

    def _get_category(self, url: str) -> str:
        for path, category in self.SECTIONS:
            if path in url:
                return category
        return "Que fer"
