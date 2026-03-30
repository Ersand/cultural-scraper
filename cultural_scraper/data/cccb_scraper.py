from datetime import datetime
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

    Note: CCCB calendar page shows events by month, not individual dates.
    We extract the month from the section header and try to determine dates.
    """

    def scrape(self) -> list[Event]:
        soup = self.manager.fetch_page(self.url)
        if not soup:
            return []

        events = []

        # Get all month sections
        month_sections = soup.select(".mp-component-agenda-list")

        for month_section in month_sections:
            # Get the month from the header
            month_header = month_section.select_one("h2, h3")
            month_text = month_header.get_text(strip=True) if month_header else ""
            month_str, year = self._parse_month(month_text)

            if not month_str or not year:
                continue

            # Get events in this month
            for card in month_section.select(".agenda-card-item"):
                try:
                    event = self._parse_card(card, month_str, year)
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

    def _parse_card(self, card, month: int, year: int) -> Event:
        title_elem = card.select_one(
            ".agenda-card-title, .featured-card-title, .content-card-title"
        )
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        if not title:
            return None

        link = card.select_one("a")
        event_url = link.get("href", "") if link else ""
        if event_url and not event_url.startswith("http"):
            event_url = f"https://www.cccb.org{event_url}"

        # Try to get specific day from the card
        day_elem = card.select_one(".agenda-card-date-num")

        day = None
        if day_elem:
            try:
                day = int(day_elem.get_text(strip=True))
            except ValueError:
                pass

        date_str = None
        if day:
            date_str = f"{day:02d}/{month:02d}/{year}"
        else:
            # No specific day - mark as month-wide event
            date_str = f"{month:02d}/{year}"

        time_elem = card.select_one(".agenda-card-date-time")
        time = time_elem.get_text(strip=True) if time_elem else None

        category_elem = card.select_one(".agenda-card-pretitle span")
        category = category_elem.get_text(strip=True) if category_elem else None

        location_elem = card.select_one(".agenda-card-pretitle")
        location = None
        if location_elem:
            location = location_elem.get_text(strip=True)
            if category and location:
                location = location.replace(category, "").strip()

        description_elem = card.select_one(
            ".agenda-card-subtitle, .featured-card-subtitle, .content-card-subtitle"
        )
        description = description_elem.get_text(strip=True) if description_elem else None

        return Event(
            title=title,
            date=date_str,
            time=time,
            location=location,
            category=category,
            description=description,
            url=event_url,
            source=self.name,
            organizer="CCCB",
        )
