from datetime import datetime
from typing import Any, Optional
from cultural_scraper.core import BaseScraper, Event
from cultural_scraper.utils import CATALAN_MONTHS, strip_html


class AteneuScraper(BaseScraper):
    """Scraper for Ateneu Barcelonès. Uses WordPress REST API."""

    def __init__(self, name: str, url: str, config: dict[str, Any] | None = None) -> None:
        super().__init__(name, url, config)
        self.location_cache: dict[str, str] | None = None

    def _get_locations(self) -> dict[str, str]:
        if self.location_cache is not None:
            return self.location_cache

        self.location_cache = {}
        api_url = self._build_api_url("espais")
        data = self.fetch_json(api_url)
        if data:
            for item in data:
                loc_id = item.get("id")
                title = strip_html(item.get("title", {}).get("rendered", ""))
                if loc_id and title:
                    self.location_cache[str(loc_id)] = title

        return self.location_cache

    def _build_api_url(self, endpoint: str) -> str:
        base = (
            self.url.replace("/activitats/", "")
            if "/activitats/" in self.url
            else "https://ateneubcn.cat"
        )
        return f"{base}/wp-json/wp/v2/{endpoint}?per_page=50"

    def scrape(self) -> list[Event]:
        locations = self._get_locations()
        data = self.fetch_json(self._build_api_url("activitats"))
        if not data:
            return []

        events = []
        for item in data:
            try:
                event = self._parse_item(item, locations)
                if event:
                    events.append(event)
            except Exception as e:
                self.logger.warning(f"Error parsing Ateneu event: {e}")

        return events

    def _parse_item(self, item: dict, locations: dict[str, str]) -> Optional[Event]:
        title = strip_html(item.get("title", {}).get("rendered", ""))
        if not title:
            return None

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

        category = campos.get("tipus_de_localitzacio") or None
        price = self._format_price(campos.get("preu_socis", ""), campos.get("preu_no_socis", ""))

        return Event(
            title=title,
            date=date,
            time=time,
            location=location if location else None,
            price=price,
            url=link,
            source=self.name,
            organizer="Ateneu Barcelonès",
            tags=[category, "Ateneu Barcelonès"] if category else ["Ateneu Barcelonès"],
        )

    def _parse_date_time(self, date_inici: str) -> tuple[Optional[str], Optional[str]]:
        if not date_inici:
            return None, None

        try:
            dt = datetime.strptime(date_inici, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d/%m/%Y"), dt.strftime("%H:%M")
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
                    return f"{day:02d}/{month:02d}/{year}", None
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
