# Cultural Scraper

Web scraper for cultural events in Barcelona. Collects events from various sources and generates an HTML calendar with category filtering.

## Features

- Scrapes events from multiple Barcelona cultural sources
- Filters by date (today, tomorrow, month)
- Category classification (theater, music, cinema, talks, etc.)
- Interactive HTML calendar with category filtering
- Rich CLI output with Typer

## Installation

```bash
# Clone the repository
git clone https://github.com/Ersand/cultural-scraper.git
cd cultural-scraper

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
```

Or use the Makefile:

```bash
make install
```

## Configuration

Edit `cultural_scraper/config/config.yaml` to configure:

- **Sources**: Add/remove websites to scrape
- **Filters**: Set date filter (today, tomorrow, month)
- **Categories**: Customize category keywords

## Usage

```bash
# Scrape events and generate HTML calendar
cultural-scraper scrape

# With custom config
cultural-scraper scrape -c path/to/config.yaml

# Validate config file
cultural-scraper validate
```

Or use Make:

```bash
make run
```

## Output

The scraper generates an HTML calendar with:

- Two-month view (current + next month)
- Category filtering in sidebar
- Click on any day to see event details
- Events colored by category

## Project Structure

```
cultural_scraper/
├── cli/              # CLI commands (Typer)
├── config/           # YAML configuration
├── core/             # Core utilities and types
├── data/             # Web scrapers
├── filters/          # Event filtering
└── formatter/        # Output formatters (HTML, Markdown)
```

## Development

```bash
# Lint
make lint

# Format
make format

# Type check
make typecheck

# Run tests
make test

# Clean
make clean
```


