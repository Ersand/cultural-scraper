from core import BaseScraper, Event


class ExampleScraper(BaseScraper):
    """
    Example scraper - customize this for your URLs.

    This scraper demonstrates the typical pattern for extracting
    cultural events from a website.
    """

    def scrape(self) -> list[Event]:
        soup = self.manager.fetch_page(self.url)
        if not soup:
            return []

        events: list[Event] = []

        # Customize these selectors based on the target website's HTML structure
        # Example selectors (adjust for actual website):
        # for item in soup.select(".event-card"):
        #     event = Event(
        #         title=item.select_one(".event-title").get_text(strip=True),
        #         date=item.select_one(".event-date").get_text(strip=True),
        #         time=item.select_one(".event-time").get_text(strip=True),
        #         location=item.select_one(".event-location").get_text(strip=True),
        #         price=item.select_one(".event-price").get_text(strip=True),
        #         description=item.select_one(".event-description").get_text(strip=True),
        #         url=item.select_one("a")["href"] if item.select_one("a") else None,
        #         source=self.name
        #     )
        #     events.append(event)

        return events


# To add a new scraper:
# 1. Create a new class extending BaseScraper
# 2. Implement the scrape() method
# 3. Register it in cli.py or main.py
