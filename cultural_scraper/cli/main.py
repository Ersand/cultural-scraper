import typer
from rich.console import Console
import yaml
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional

from cultural_scraper.data import ScraperManager
from cultural_scraper.core import Event, ScraperType
from cultural_scraper.data import (
    CCCBScraper,
    AteneuScraper,
    BibliotequesScraper,
    GuiaBarcelonaScraper,
    TimeoutScraper,
)
from cultural_scraper.formatter import MarkdownFormatter, HtmlFormatter
from cultural_scraper.filters import EventFilter, deduplicate_events


SCRAPER_CLASSES = {
    ScraperType.CCCB: CCCBScraper,
    ScraperType.ATENEU: AteneuScraper,
    ScraperType.BIBLIOTEQUES: BibliotequesScraper,
    ScraperType.GUIA: GuiaBarcelonaScraper,
    ScraperType.TIMEOUT: TimeoutScraper,
}

console = Console()
app = typer.Typer(name="cultural-scraper", help="Cultural plans scraper")


def load_config(config_path: str) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise typer.BadParameter(f"Config file not found: {config_path}")

    with open(path) as f:
        return yaml.safe_load(f)


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


@app.command()
def scrape(
    config: str = typer.Option("config.yaml", "--config", "-c", help="Path to config file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Scrape cultural events and generate summary"""
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    try:
        cfg = load_config(config)
    except Exception as e:
        raise typer.BadParameter(str(e))

    logger.info("Initializing scraper manager")
    manager = ScraperManager(cfg)

    sources = cfg.get("sources", [])
    if not sources:
        console.print("[red]No sources configured in config.yaml[/red]")
        console.print("[yellow]Add your URLs to the sources list in config.yaml[/yellow]")
        raise typer.Exit(1)

    for source in sources:
        if isinstance(source, str):
            url = source
            name = source
            scraper_type = ScraperType.from_url(url)
        else:
            name = source.get("name", "Unknown")
            url = source.get("url", "")
            type_str = source.get("type")
            if type_str:
                scraper_type = ScraperType(type_str)
            else:
                scraper_type = ScraperType.from_url(url)

        scraper_class = SCRAPER_CLASSES.get(scraper_type, CCCBScraper)
        scraper = scraper_class(name, url, cfg.get("scraper", {}))

        manager.register_scraper(scraper)

    logger.info(f"Running {len(manager.scrapers)} scraper(s)")
    results = manager.run_all()
    manager.close()

    event_filter = EventFilter(cfg)
    all_events = []
    for source_name, events in results.items():
        if source_name == "_errors":
            continue
        filtered = event_filter.filter_events(events)
        logger.info(f"Filtered {len(events)} -> {len(filtered)} events from {source_name}")
        for event in filtered:
            event.source = source_name
            all_events.extend([event])

    unique_events = deduplicate_events(all_events)
    logger.info(f"Total: {len(all_events)} events, {len(unique_events)} unique")

    filtered_results: dict[str, list[Event]] = {}
    for event in unique_events:
        source = event.source
        if source not in filtered_results:
            filtered_results[source] = []
        filtered_results[source].append(event)

    output_format = cfg.get("output", {}).get("format", "markdown")

    date_filter = cfg.get("filters", {}).get("date", "today")
    if date_filter == "today":
        display_date = datetime.now().strftime("%d-%m-%Y")
    elif date_filter == "tomorrow":
        display_date = (datetime.now() + timedelta(days=1)).strftime("%d-%m-%Y")
    elif date_filter == "month":
        display_date = datetime.now().strftime("%m-%Y")
    else:
        display_date = date_filter

    if output_format == "html":
        formatter = HtmlFormatter(
            "Cultural Plans",
            date=display_date,
            category_classifier=event_filter.classify_category,
        )
        extension = "html"
    else:
        formatter = MarkdownFormatter("Cultural Plans", date=display_date)
        extension = "md"

    output_text = formatter.format(filtered_results)

    output_folder = cfg.get("output", {}).get("folder", "output")
    if output:
        output_path = Path(output)
    else:
        Path(output_folder).mkdir(exist_ok=True)
        output_path = Path(output_folder) / f"{display_date}.{extension}"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_text)
    console.print(f"[green]Output written to: {output_path}[/green]")

    if extension == "html":
        docs_path = Path("docs")
        docs_path.mkdir(exist_ok=True)
        docs_index = docs_path / "index.html"
        docs_index.write_text(output_text)
        console.print(f"[green]GitHub Pages: docs/index.html updated[/green]")


@app.command()
def validate(
    config: str = typer.Option("config.yaml", "--config", "-c", help="Path to config file"),
) -> None:
    """Validate config file"""
    try:
        cfg = load_config(config)
        console.print("[green]Config is valid![/green]")

        sources = cfg.get("sources", [])
        console.print(f"Found {len(sources)} source(s) configured")

        for source in sources:
            name = source.get("name", "Unknown") if isinstance(source, dict) else "Unknown"
            url = source.get("url", "") if isinstance(source, dict) else str(source)
            console.print(f"  - [blue]{name}[/blue]: {url}")

    except Exception as e:
        raise typer.BadParameter(f"Config error: {e}")


if __name__ == "__main__":
    app()
