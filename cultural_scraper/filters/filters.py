import re
from datetime import date
from typing import Any, Optional
from cultural_scraper.core import Event
from cultural_scraper.utils import (
    parse_date as _parse_date,
    parse_time as _parse_time,
)


class EventFilter:
    def __init__(self, config: dict[str, Any]) -> None:
        filter_cfg = config.get("filters", {})
        categories = config.get("categories", {})

        self.date_filter: str = filter_cfg.get("date", "today")
        self.time_from: Optional[str] = filter_cfg.get("time_from")
        self.age_group: str = filter_cfg.get("age_group", "adults")
        self.family_keywords: list[str] = categories.get("family_keywords", [])
        self.category_keywords: dict[str, list[str]] = categories.get("category_keywords", {})

    GENERIC_CATEGORIES = {
        "agenda",
        "que fer",
        "altres",
        "otros",
        "other",
        "general",
        "sala_ateneu",
        "accessible",
        "escena",
        "educació",
        "exposició",
        "itineraris",
        "cursos i tallers",
        "audiovisuals",
        "debats",
        "marina port vell",
        "teatre lliure",
        "palau de la música catalana",
        "palau sant jordi",
        "teatre nacional de catalunya",
        "disseny hub barcelona",
        "espai francesca bonnemaison",
        "biblioteca francesca bonnemaison",
        "la virreina",
        "casa batlló",
        "razzmatazz",
        "jamboree",
        "centre cívic",
        "fundació joan miró",
        "amics cccb",
        "biblioteques barcelona",
        "guia barcelona",
        "ateneu barcelonès",
        "virreina",
        "recorregut",
        "biblioteca francesc",
        "cccb",
        "ateneu",
        "biblioteques",
    }

    GENERIC_PARTIALS = [
        "virreina",
        "recorregut",
        "biblioteca francesc",
        "espai francesca",
    ]

    def filter_events(self, events: list[Event]) -> list[Event]:
        return [e for e in events if self._should_include(e)]

    def classify_category(self, event: Event) -> str:
        text = " ".join(
            str(getattr(event, f) or "") for f in ("title", "description", "location")
        ).lower()

        best_match = None
        best_score = 0

        for cat_name, keywords in self.category_keywords.items():
            score = sum(len(kw) for kw in keywords if kw.lower() in text)
            if score > best_score:
                best_score = score
                best_match = cat_name

        if best_match:
            return best_match

        if event.tags:
            for tag in event.tags:
                if not tag:
                    continue
                tag_lower = tag.lower()
                if tag_lower in self.GENERIC_CATEGORIES:
                    continue
                if any(p in tag_lower for p in self.GENERIC_PARTIALS):
                    continue
                return tag_lower

        fallback = event.source.lower().strip() if event.source else ""
        return fallback if fallback and fallback not in self.GENERIC_CATEGORIES else "altres"

    def _should_include(self, event: Event) -> bool:
        return self._check_date(event) and self._check_time(event) and self._check_age_group(event)

    def _check_date(self, event: Event) -> bool:
        if self.date_filter == "all":
            return True

        event_date = _parse_date(event.date)
        if not event_date:
            return True

        today = date.today()

        if self.date_filter == "today":
            return event_date == today
        elif self.date_filter == "tomorrow":
            from datetime import timedelta

            return event_date == today + timedelta(days=1)
        elif self.date_filter == "month":
            next_month = (today.replace(day=28) + __import__("datetime").timedelta(days=4)).replace(
                day=1
            )
            following = (next_month + __import__("datetime").timedelta(days=32)).replace(day=1)
            return today <= event_date < following
        else:
            from datetime import datetime

            try:
                target = datetime.strptime(self.date_filter, "%d-%m-%Y").date()
                return event_date == target
            except ValueError:
                return True

    def _check_time(self, event: Event) -> bool:
        if not self.time_from:
            return True

        event_time = _parse_time(event.time)
        if not event_time:
            return True

        hour, minute = map(int, self.time_from.split(":"))
        return event_time >= (hour, minute)

    def _check_age_group(self, event: Event) -> bool:
        if self.age_group == "all":
            return True

        text = " ".join(
            str(getattr(event, f) or "") for f in ("title", "description", "location")
        ).lower()
        if event.tags:
            text += " " + " ".join(str(t) for t in event.tags).lower()

        is_family = any(kw in text for kw in self.family_keywords)

        if self.age_group == "adults":
            return not is_family
        elif self.age_group == "family":
            return is_family

        return True


def deduplicate_events(events: list[Event]) -> list[Event]:
    seen: set[str] = set()
    unique: list[Event] = []

    for event in events:
        key = _normalize_key(event)
        if key not in seen:
            seen.add(key)
            unique.append(event)

    return unique


def _normalize_key(event: Event) -> str:
    title = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", (event.title or "").lower().strip()))
    date_str = (event.date or "").lower().strip()
    organizer = re.sub(
        r"\s+", " ", re.sub(r"[^\w\s]", "", (event.organizer or event.source or "").lower().strip())
    )
    return f"{title}|{date_str}|{organizer}"
