from datetime import datetime
from cultural_scraper.core import Event


class MarkdownFormatter:
    def __init__(self, title: str = "Cultural Plans", date: str | None = None) -> None:
        self.title = title
        self.date = date or datetime.now().strftime("%d-%m-%Y")

    def format(self, events_by_source: dict[str, list[Event]]) -> str:
        lines: list[str] = []
        lines.append(f"# {self.title}")
        lines.append(f"*{self.date}*")
        lines.append("")

        errors = events_by_source.get("_errors", [])
        if errors:
            lines.append("## Errors")
            for error in errors:
                lines.append(f"- {error}")
            lines.append("")

        total_events = 0
        for source, events in events_by_source.items():
            if source == "_errors":
                continue

            if not events:
                continue

            total_events += len(events)
            lines.append(f"## {source}")
            lines.append("")

            for event in events:
                lines.append(self._format_event(event))
                lines.append("")

        lines.append(f"*Total: {total_events} events*")
        return "\n".join(lines)

    def _format_event(self, event: Event) -> str:
        parts = []

        if event.title:
            if event.url:
                parts.append(f"### [{event.title}]({event.url})")
            else:
                parts.append(f"### {event.title}")

        details = []
        if event.date:
            details.append(f"**Date:** {event.date}")
        if event.time:
            details.append(f"**Time:** {event.time}")
        if event.location:
            details.append(f"**Location:** {event.location}")
        if event.price:
            details.append(f"**Price:** {event.price}")
        if event.category:
            details.append(f"**Category:** {event.category}")

        if details:
            parts.append(", ".join(details))

        if event.description:
            parts.append(f"\n{event.description}")

        return "\n".join(parts)
