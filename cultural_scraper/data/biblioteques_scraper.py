from cultural_scraper.core import BaseScraper, Event


class BibliotequesScraper(BaseScraper):
    """Scraper for Barcelona Libraries."""

    def scrape(self) -> list[Event]:
        soup = self.fetch_soup(self.url)
        if not soup:
            return []

        events = []

        for item in soup.select(".ajuntament-guia-item"):
            try:
                title_elem = item.select_one(".ajuntament-guia-item-name")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                if not title:
                    continue

                event_url = title_elem.get("href", "")
                if event_url and not event_url.startswith("http"):
                    event_url = f"https://ajuntament.barcelona.cat{event_url}"

                when_elem = item.select_one(".ajuntament-guia-item-when")
                date = None
                if when_elem:
                    date = when_elem.get_text(strip=True).replace("Quan:", "").strip()

                where_elem = item.select_one(".ajuntament-guia-item-where a")
                location = where_elem.get_text(strip=True) if where_elem else None

                address_elem = item.select_one(".ajuntament-guia-item-address")
                address = None
                if address_elem:
                    address = address_elem.get_text(strip=True).replace("Adreça:", "").strip()
                    if location:
                        location = f"{location} - {address}"
                    else:
                        location = address

                events.append(
                    Event(
                        title=title,
                        date=date,
                        location=location,
                        url=event_url,
                        source=self.name,
                        organizer="Biblioteques de Barcelona",
                    )
                )
            except Exception as e:
                self.logger.warning(f"Error parsing Biblioteques event: {e}")

        return events
