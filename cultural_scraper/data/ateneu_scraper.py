import requests
import re
from datetime import datetime
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


class AteneuScraper(BaseScraper):
    """
    Scraper for Ateneu Barcelonès
    Website: https://ateneubcn.cat/

    Uses WordPress REST API to fetch events.
    """

    def __init__(self, name: str, url: str, config: dict[str, Any] | None = None) -> None:
        super().__init__(name, url, config)
        self.location_cache: dict[str, str] | None = None

    def _get_locations(self) -> dict[str, str]:
        if self.location_cache is not None:
            return self.location_cache

        self.location_cache = {}
        try:
            response = requests.get(
                "https://ateneubcn.cat/wp-json/wp/v2/espais",
                headers={"User-Agent": self.get_user_agent()},
                timeout=self.get_timeout(),
            )
            if response.status_code == 200:
                for item in response.json():
                    loc_id = item.get("id")
                    title = item.get("title", {}).get("rendered", "")
                    title = self._strip_html(title)
                    self.location_cache[str(loc_id)] = title
        except Exception as e:
            self.logger.warning(f"Could not fetch locations: {e}")

        return self.location_cache

    def scrape(self) -> list[Event]:
        events = []

        base_url = self.url
        if "/activitats/" in base_url:
            api_url = base_url.split("/activitats/")[0] + "/wp-json/wp/v2/activitats?per_page=50"
        else:
            api_url = "https://ateneubcn.cat/wp-json/wp/v2/activitats?per_page=50"

        locations = self._get_locations()

        try:
            response = requests.get(
                api_url,
                headers={"User-Agent": self.get_user_agent()},
                timeout=self.get_timeout(),
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            self.logger.error(f"API error: {e}")
            return []

        for item in data:
            try:
                title = item.get("title", {}).get("rendered", "")
                if not title:
                    continue

                title = self._strip_html(title)
                link = item.get("link", "")

                acf = item.get("acf", {})
                campos = acf.get("campos_activitat", {})

                date_inici = campos.get("data_inici", "")
                date, time = self._parse_date_time(date_inici)

                location_id = str(campos.get("localitzacio", ""))
                location = locations.get(location_id, "")
                address = campos.get("adressa", "")
                if address and location:
                    location = f"{location} - {address}"
                elif address:
                    location = address

                category = campos.get("tipus_de_localitzacio", "")
                if not category:
                    category = None

                price_socis = campos.get("preu_socis", "")
                price_no_socis = campos.get("preu_no_socis", "")
                price = self._format_price(price_socis, price_no_socis)

                event = Event(
                    title=title,
                    date=date,
                    time=time,
                    location=location if location else None,
                    category=category,
                    price=price,
                    url=link,
                    source=self.name,
                    organizer="Ateneu Barcelonès",
                )
                events.append(event)

            except Exception as e:
                self.logger.warning(f"Error parsing Ateneu event: {e}")
                continue

        return events

    def _parse_date_time(self, date_inici: str) -> tuple[Optional[str], Optional[str]]:
        if not date_inici:
            return None, None

        try:
            dt = datetime.strptime(date_inici, "%Y-%m-%d %H:%M:%S")
            date = dt.strftime("%d/%m/%Y")
            time = dt.strftime("%H:%M")
            return date, time
        except ValueError:
            pass

        parts = date_inici.split()
        if len(parts) >= 2:
            try:
                day = int(parts[0])
                month_name = parts[1].lower()
                year = parts[2] if len(parts) > 2 else str(datetime.now().year)

                month = CATALAN_MONTHS.get(month_name)
                if month:
                    date = f"{day:02d}/{month:02d}/{year}"
                    return date, None
            except (ValueError, IndexError):
                pass

        return None, None

    def _format_price(self, price_socis: str, price_no_socis: str) -> Optional[str]:
        if price_socis and price_no_socis:
            return f"Socis: {price_socis}€ / No socis: {price_no_socis}€"
        elif price_no_socis:
            return f"{price_no_socis}€"
        elif price_socis:
            return f"Socis: {price_socis}€"
        return None

    def _strip_html(self, html_string: str) -> str:
        clean = re.sub(r"<[^>]+>", "", html_string)
        return clean.strip()
