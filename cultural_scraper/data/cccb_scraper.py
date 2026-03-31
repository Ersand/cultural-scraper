from datetime import datetime
import re
from typing import Any, Optional
from cultural_scraper.core import BaseScraper, Event


CATALAN_MONTHS: dict[str, int] = {
    "gener": 1,
    "febrer": 2,
    "març": 3,
    "abril": 4,
    "maig": 5,
    "juny": 6,
    "juliol": 7,
    "agost": 8,
    "setembre": 9,
    "octubre": 10,
    "novembre": 11,
    "desembre": 12,
}


class CCCBScraper(BaseScraper):
    """
    Scraper for CCCB (Centre de Cultura Contemporània de Barcelona)
    Website: https://www.cccb.org/ca/
    """

    def scrape(self) -> list[Event]:
        soup = self.manager.fetch_page(self.url)
        if not soup:
            return []

        events = []

        month_sections = soup.select(".mp-component-agenda-list")

        for month_section in month_sections:
            month_header = month_section.select_one("h2, h3")
            month_text = month_header.get_text(strip=True) if month_header else ""
            month_str, year = self._parse_month(month_text)

            if not month_str or not year:
                continue

            date_rows = month_section.select(".agenda-card-row")

            for date_row in date_rows:
                day_elem = date_row.select_one(".agenda-card-date-num")
                day: int | None = int(day_elem.get_text(strip=True)) if day_elem else None

                cards = date_row.select(".agenda-card-item")
                for card in cards:
                    if day is None:
                        continue
                    try:
                        event = self._parse_card(card, day, month_str, year)
                        if event:
                            events.append(event)
                    except Exception as e:
                        self.logger.warning(f"Error parsing CCCB event: {e}")
                        continue

        return events

    def _parse_month(self, month_text: str) -> tuple:
        """Parse month text like 'març 2026' to (3, 2026)"""
        parts = month_text.lower().strip().split()
        if len(parts) >= 2:
            month_name = parts[0]
            year_str = parts[1]

            try:
                year = int(year_str)
            except ValueError:
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

        event_category = category if category else None

        return Event(
            title=title,
            date=date_str,
            time=time_value,
            location=location,
            description=description,
            url=event_url,
            source=self.name,
            organizer="CCCB",
            tags=[event_category, "CCCB"] if event_category else ["CCCB"],
        )

    def _parse_time_and_location(self, raw: str | None) -> tuple:
        """Parse raw time string to extract time and determine if it's actually a date."""
        if not raw:
            return None, None

        time_pattern = re.compile(r"(\d{1,2}:\d{2})")
        match = time_pattern.search(raw)

        if match:
            time_value = match.group(1)
            return time_value, None

        date_patterns = [
            r"\d{1,2}\s+d['′]?\w+\s+\d{4}",
            r"\d{1,2}\s+de\s+\w+\s+\d{4}",
        ]
        for pattern in date_patterns:
            if re.search(pattern, raw, re.IGNORECASE):
                return None, None

        return None, raw
