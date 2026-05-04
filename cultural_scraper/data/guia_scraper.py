from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Any, Optional
import re
from urllib.parse import unquote
from cultural_scraper.core import BaseScraper, Event


@dataclass
class GuiaEventResult:
    events: list[Event] = field(default_factory=list)
    new_sources: list[str] = field(default_factory=list)
    permanent_venues: list[str] = field(default_factory=list)


class GuiaBarcelonaScraper(BaseScraper):
    """Scraper for Guia Barcelona. Auto-discovers listing and venue URLs."""

    BASE_URL = "https://guia.barcelona.cat"

    def scrape(self) -> list[Event]:
        visited_urls: set[str] = set()
        all_venue_urls: list[str] = []

        main_soup = self.fetch_soup(self.url)
        if main_soup:
            initial_urls = self._get_listing_urls(main_soup)
            venue_urls = self._get_venue_urls(main_soup)
            self.logger.info(
                f"Found {len(initial_urls)} listing URLs and {len(venue_urls)} venue URLs"
            )
            all_venue_urls.extend(venue_urls)
        else:
            initial_urls = []

        urls_to_scrape = [self.url] + [u for u in initial_urls if u != self.url]
        day_events: list[Event] = []

        for url in urls_to_scrape:
            if url in visited_urls:
                continue
            visited_urls.add(url)

            self.logger.info(f"Scraping: {url[:60]}")
            result = self._scrape_url(url)
            day_events.extend(result.events)
            all_venue_urls.extend(result.new_sources)

        visited_venues: set[str] = set()
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

        self.logger.info(f"Total events found: {len(day_events)}")
        return day_events

    def _scrape_url(self, url: str) -> GuiaEventResult:
        soup = self.fetch_soup(url)
        if not soup:
            return GuiaEventResult()

        events: list[Event] = []
        new_sources: list[str] = []
        permanent_venues: list[str] = []

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
                    event_url = self._normalize_url(event_url)

                date, location = self._extract_meta(item)

                category_elem = item.select_one(".categoria span")
                category = category_elem.get_text(strip=True) if category_elem else None

                if event_url and "/llistat" in event_url:
                    new_sources.append(event_url)
                    continue

                is_permanent = date and "permanent" in date.lower()
                if (date and not is_permanent) or location:
                    events.append(
                        Event(
                            title=title,
                            date=date,
                            location=location,
                            url=event_url,
                            source=self.name,
                            organizer=location,
                            tags=[category, location]
                            if category and location
                            else [category or location or ""],
                        )
                    )
                elif event_url and "/ca/detall/" in event_url:
                    permanent_venues.append(event_url)
            except Exception as e:
                self.logger.warning(f"Error parsing Guia event: {e}")

        return GuiaEventResult(
            events=events, new_sources=new_sources, permanent_venues=permanent_venues
        )

    def _extract_meta(self, item: Any) -> tuple[Optional[str], Optional[str]]:
        date = location = None
        for dt in item.select("dl dt"):
            dt_text = dt.get_text(strip=True)
            dd = dt.find_next_sibling("dd")
            if not dd:
                continue
            dd_text = dd.get_text(strip=True)
            if dt_text == "Quan:":
                date = dd_text
            elif dt_text == "On:":
                location = dd_text
        return date, location

    def _extract_url(self, title_elem: Any) -> str:
        href = str(title_elem.get("href", ""))
        if href and href != "javascript: void(0)":
            return href

        onclick = str(title_elem.get("onclick", ""))
        if "guia.barcelona.cat" in onclick:
            match = re.search(r"p\[url\]=([^&'\"]+)", onclick)
            if match:
                return unquote(match.group(1))
        return ""

    def _normalize_url(self, url: str) -> str:
        if not url.startswith("/"):
            url = "/" + url
        if "/ca/" not in url and "/en/" not in url and "/es/" not in url:
            url = "/ca" + url
        return f"{self.BASE_URL}{url}"

    def _get_listing_urls(self, soup: BeautifulSoup) -> list[str]:
        urls: list[str] = []
        for a in soup.select('a[href*="llistat"]'):
            href = str(a.get("href", ""))
            if href and not href.startswith("http"):
                href = f"{self.BASE_URL}{href}"
            if href and href not in urls:
                urls.append(href)
        return urls

    def _get_venue_urls(self, soup: BeautifulSoup) -> list[str]:
        urls: list[str] = []
        for item in soup.select("div.item"):
            date = None
            for dt in item.select("dl dt"):
                if dt.get_text(strip=True) == "Quan:":
                    dd = dt.find_next_sibling("dd")
                    if dd:
                        date = dd.get_text(strip=True)
                    break

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
                            href = f"{self.BASE_URL}{href}"
                        if href not in urls:
                            urls.append(href)
        return urls
