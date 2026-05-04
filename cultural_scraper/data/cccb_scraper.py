from typing import Any, Optional
from cultural_scraper.core import BaseScraper, Event
from cultural_scraper.utils import CATALAN_MONTHS, parse_time


class CCCBScraper(BaseScraper):
    """Scraper for CCCB (Centre de Cultura Contemporània de Barcelona)."""

    def scrape(self) -> list[Event]:
        soup = self.fetch_soup(self.url)
        if not soup:
            return []

        events = []

        for month_section in soup.select(".mp-component-agenda-list"):
            month_header = month_section.select_one("h2, h3")
            month_text = month_header.get_text(strip=True) if month_header else ""
            month_num, year = self._parse_month(month_text)
            if not month_num or not year:
                continue

            for date_row in month_section.select(".agenda-card-row"):
                day_elem = date_row.select_one(".agenda-card-date-num")
                day = int(day_elem.get_text(strip=True)) if day_elem else None
                if day is None:
                    continue

                for card in date_row.select(".agenda-card-item"):
                    try:
                        event = self._parse_card(card, day, month_num, year)
                        if event:
                            events.append(event)
                    except Exception as e:
                        self.logger.warning(f"Error parsing CCCB event: {e}")

        return events

    def _parse_month(self, month_text: str) -> tuple[Optional[int], Optional[int]]:
        parts = month_text.lower().strip().split()
        if len(parts) >= 2:
            month_name, year_str = parts[0], parts[1]
            try:
                year = int(year_str)
            except ValueError:
                from datetime import datetime

                year = datetime.now().year

            month_num = CATALAN_MONTHS.get(month_name)
            if month_num:
                return month_num, year

        return None, None

    def _parse_card(self, card: Any, day: int, month: int, year: int) -> Optional[Event]:
        title_elem = card.select_one(".agenda-card-title")
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        if not title:
            return None

        link = card.select_one("a")
        event_url = link.get("href", "") if link else ""
        if event_url and not event_url.startswith("http"):
            event_url = f"https://www.cccb.org{event_url}"

        time_elem = card.select_one(".agenda-card-date-time")
        raw_time = time_elem.get_text(strip=True) if time_elem else None
        time_value, location = self._parse_time_and_location(raw_time)

        category_elem = card.select_one(".agenda-card-pretitle span")
        category = category_elem.get_text(strip=True) if category_elem else None

        pretitle_elem = card.select_one(".agenda-card-pretitle")
        if pretitle_elem:
            pretitle_text = pretitle_elem.get_text(strip=True)
            if category and pretitle_text:
                location = pretitle_text.replace(category, "").strip()
            elif not location:
                location = pretitle_text if pretitle_text != category else None

        date_str = f"{day:02d}/{month:02d}/{year}"

        description_elem = card.select_one(".agenda-card-text")
        description = description_elem.get_text(strip=True) if description_elem else None

        return Event(
            title=title,
            date=date_str,
            time=time_value,
            location=location,
            description=description,
            url=event_url,
            source=self.name,
            organizer="CCCB",
            tags=[category, "CCCB"] if category else ["CCCB"],
        )

    def _parse_time_and_location(self, raw: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        if not raw:
            return None, None

        time_value = parse_time(raw)
        if time_value:
            return f"{time_value[0]:02d}:{time_value[1]:02d}", None

        date_patterns = [
            r"\d{1,2}\s+d['′]?\w+\s+\d{4}",
            r"\d{1,2}\s+de\s+\w+\s+\d{4}",
        ]
        for pattern in date_patterns:
            import re

            if re.search(pattern, raw, re.IGNORECASE):
                return None, None

        return None, raw
