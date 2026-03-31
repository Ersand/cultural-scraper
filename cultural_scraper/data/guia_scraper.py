from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Any
import re
from urllib.parse import unquote
from cultural_scraper.core import BaseScraper, Event


@dataclass
class GuiaEventResult:
    events: list[Event] = field(default_factory=list)
    new_sources: list[str] = field(default_factory=list)
    permanent_venues: list[str] = field(default_factory=list)


class GuiaBarcelonaScraper(BaseScraper):
    """
    Scraper for Guia Barcelona
    Website: https://guia.barcelona.cat/

    Automatically discovers and scrapes:
    - Day-specific events with dates
    - Permanent venues (for later scraping)
    """

    def __init__(self, name: str, url: str, config: dict[str, Any] | None = None) -> None:
        super().__init__(name, url, config)
        self.organizer_cache: dict[str, str] = {}

    def scrape(self) -> list[Event]:
        all_events = []
        visited_urls: set[str] = set()

        # First pass: get initial listing URLs and venue URLs
        main_soup = None
        if self.manager:
            main_soup = self.manager.fetch_page(self.url)
        if main_soup:
            initial_urls = self._get_listing_urls(main_soup)
            venue_urls = self._get_venue_urls(main_soup)
            self.logger.info(
                f"Found {len(initial_urls)} listing URLs and {len(venue_urls)} venue URLs"
            )

        urls_to_scrape = initial_urls if main_soup else []
        if self.url not in urls_to_scrape:
            urls_to_scrape.insert(0, self.url)

        # Track separate events
        day_events = []
        permanent_events = []

        # Also track venues to scrape later for day-specific events
        all_venue_urls = list(venue_urls)

        while urls_to_scrape:
            url = urls_to_scrape.pop(0)
            if url in visited_urls:
                continue
            visited_urls.add(url)

            self.logger.info(f"Scraping: {url[:60]}")
            result = self._scrape_url(url)

            day_events.extend(result.events)
            all_venue_urls.extend(result.new_sources)

            # Track permanent venues (URLs without dates)
            permanent_events.extend(result.permanent_venues)

        self.logger.info(
            f"Day events: {len(day_events)}, Permanent venues: {len(permanent_events)}"
        )

        # Second pass: scrape venues for day-specific events
        visited_venues = set()
        for venue_url in all_venue_urls:
            if venue_url in visited_venues or venue_url in visited_urls:
                continue
            visited_venues.add(venue_url)

            venue_result = self._scrape_url(venue_url)
            if venue_result.events:
                self.logger.info(
                    f"Found {len(venue_result.events)} events from venue: {venue_url[:40]}"
                )
                day_events.extend(venue_result.events)

        # Combine all events
        all_events = day_events
        self.logger.info(f"Total events found: {len(all_events)}")
        return all_events

    def _scrape_url(self, url: str) -> GuiaEventResult:
        if not self.manager:
            return GuiaEventResult()
        soup = self.manager.fetch_page(url)
        if not soup:
            return GuiaEventResult()

        events = []
        new_sources = []
        permanent_venues = []

        for item in soup.select("div.item"):
            try:
                title_elem = item.select_one("h3 a, h3.properes a")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                if not title:
                    continue

                event_url = self._extract_url(title_elem)
                if event_url and not event_url.startswith("http"):
                    if not event_url.startswith("/"):
                        event_url = "/" + event_url
                    if (
                        "/ca/" not in event_url
                        and "/en/" not in event_url
                        and "/es/" not in event_url
                    ):
                        event_url = "/ca" + event_url
                    event_url = f"https://guia.barcelona.cat{event_url}"

                date = None
                location = None

                dts = item.select("dl dt")
                for dt in dts:
                    dt_text = dt.get_text(strip=True)
                    dd = dt.find_next_sibling("dd")
                    if not dd:
                        continue
                    dd_text = dd.get_text(strip=True)

                    if dt_text == "Quan:":
                        date = dd_text
                    elif dt_text == "On:":
                        location = dd_text

                category_elem = item.select_one(".categoria span")
                category = category_elem.get_text(strip=True) if category_elem else None

                # Check for llistat links (sub-categories)
                if event_url and "/llistat" in event_url:
                    new_sources.append(event_url)
                    continue

                is_permanent = date and "permanent" in date.lower()
                has_valid_info = (date and not is_permanent) or location

                if has_valid_info:
                    event = Event(
                        title=title,
                        date=date,
                        location=location,
                        url=event_url,
                        source=self.name,
                        organizer=location,
                        tags=[category, location]
                        if category and location
                        else [category or location],
                    )
                    events.append(event)
                elif event_url and "/ca/detall/" in event_url:
                    # This is a permanent venue - track it for later
                    permanent_venues.append(event_url)

            except Exception as e:
                self.logger.warning(f"Error parsing Guia Barcelona event: {e}")
                continue

        return GuiaEventResult(
            events=events, new_sources=new_sources, permanent_venues=permanent_venues
        )

    def _extract_url(self, title_elem) -> str:
        """Extract the real URL from the element, handling javascript links."""
        href = str(title_elem.get("href", ""))

        if href and href != "javascript: void(0)":
            return href

        # Try to extract from onclick
        onclick = str(title_elem.get("onclick", ""))
        if "guia.barcelona.cat" in onclick:
            match = re.search(r"p\[url\]=([^&'\"]+)", onclick)
            if match:
                return unquote(match.group(1))

        return ""

    def _get_listing_urls(self, soup: BeautifulSoup) -> list[str]:
        """Get initial listing URLs from the main page."""
        urls: list[str] = []
        for a in soup.select('a[href*="llistat"]'):
            href = str(a.get("href", ""))
            if href:
                if not href.startswith("http"):
                    href = f"https://guia.barcelona.cat{href}"
                if href not in urls:
                    urls.append(href)
        return urls

    def _get_venue_urls(self, soup: BeautifulSoup) -> list[str]:
        """Get venue/place URLs from the main page."""
        urls: list[str] = []
        for item in soup.select("div.item"):
            # Get date and location to identify venues vs events
            date = None
            dts = item.select("dl dt")
            for dt in dts:
                if dt.get_text(strip=True) == "Quan:":
                    dd = dt.find_next_sibling("dd")
                    if dd:
                        date = dd.get_text(strip=True)
                    break

            # If no date, it's a venue
            if not date:
                link = item.select_one("a")
                if link:
                    href = str(link.get("href", ""))
                    if href and not href.startswith("javascript") and "/ca/detall/" in href:
                        if not href.startswith("http"):
                            if not href.startswith("/"):
                                href = "/" + href
                            if "/ca/" not in href:
                                href = "/ca" + href
                            href = f"https://guia.barcelona.cat{href}"
                        if href not in urls:
                            urls.append(href)

        return urls
