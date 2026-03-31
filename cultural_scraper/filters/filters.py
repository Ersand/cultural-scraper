import re
from datetime import datetime, date, timedelta
from typing import Any, Optional
from dataclasses import dataclass
from cultural_scraper.core import Event


CATALAN_WEEKDAYS = {
    "dilluns": 0,
    "dimarts": 1,
    "dimecres": 2,
    "dijous": 3,
    "divendres": 4,
    "dissabte": 5,
    "diumenge": 6,
}

CATALAN_MONTHS = {
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


@dataclass
class FilterConfig:
    date_filter: str = "today"
    time_from: Optional[str] = None
    age_group: str = "adults"
    family_keywords: list[str] | None = None
    category_keywords: dict[str, list[str]] | None = None

    def __post_init__(self) -> None:
        if self.family_keywords is None:
            self.family_keywords = []
        if self.category_keywords is None:
            self.category_keywords = {}


class EventFilter:
    def __init__(self, config: dict[str, Any]) -> None:
        filter_cfg = config.get("filters", {})
        categories = config.get("categories", {})

        self.config = FilterConfig(
            date_filter=filter_cfg.get("date", "today"),
            time_from=filter_cfg.get("time_from"),
            age_group=filter_cfg.get("age_group", "adults"),
            family_keywords=categories.get("family_keywords", []),
            category_keywords=categories.get("category_keywords", {}),
        )

    def filter_events(self, events: list[Event]) -> list[Event]:
        filtered = []
        for event in events:
            if self._should_include(event):
                filtered.append(event)
        return filtered

    GENERIC_CATEGORIES = {"agenda", "que fer", "altres", "otros", "other", "general"}

    def classify_category(self, event: Event) -> str:
        if event.tags:
            for tag in event.tags:
                if tag and tag.lower() not in self.GENERIC_CATEGORIES:
                    return tag.lower()

        fields = [
            str(event.title) if event.title else "",
            str(event.description) if event.description else "",
            str(event.location) if event.location else "",
        ]
        text_to_check = " ".join(fields).lower()

        category_keywords = self.config.category_keywords or {}

        for cat_name, keywords in category_keywords.items():
            for kw in keywords:
                if kw.lower() in text_to_check:
                    return cat_name

        fallback = event.source.lower().strip() if event.source else "altres"
        if fallback in self.GENERIC_CATEGORIES or not fallback:
            return "altres"
        return fallback

    def _should_include(self, event: Event) -> bool:
        if not self._check_date(event):
            return False
        if not self._check_time(event):
            return False
        if not self._check_age_group(event):
            return False
        return True

    def _check_date(self, event: Event) -> bool:
        date_filter = self.config.date_filter
        if date_filter == "all":
            return True

        event_date = self._parse_date(event.date)
        if not event_date:
            return True

        today = date.today()

        if date_filter == "today":
            return event_date == today
        elif date_filter == "tomorrow":
            tomorrow = today + timedelta(days=1)
            return event_date == tomorrow
        elif date_filter == "month":
            next_month = today.replace(day=28) + timedelta(days=4)
            next_month = next_month.replace(day=1)
            following_month = next_month.replace(day=1) + timedelta(days=32)
            following_month = following_month.replace(day=1)
            return today <= event_date < following_month
        else:
            try:
                target_date = datetime.strptime(date_filter, "%d-%m-%Y").date()
                return event_date == target_date
            except ValueError:
                return True

    def _check_time(self, event: Event) -> bool:
        time_from = self.config.time_from
        if not time_from:
            return True

        event_time = self._parse_time(event.time)
        if not event_time:
            return True

        hour, minute = map(int, time_from.split(":"))
        return event_time >= (hour, minute)

    def _check_age_group(self, event: Event) -> bool:
        age_group = self.config.age_group
        if age_group == "all":
            return True

        fields = [
            str(event.title) if event.title else "",
            str(event.description) if event.description else "",
            str(event.location) if event.location else "",
        ]
        if event.tags:
            fields.extend(str(t) for t in event.tags)

        text_to_check = " ".join(fields).lower()

        is_family = any(kw in text_to_check for kw in self.config.family_keywords or [])

        if age_group == "adults":
            return not is_family
        elif age_group == "family":
            return is_family

        return True

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        if not date_str:
            return None

        date_str = date_str.strip()
        today = date.today()

        formats = [
            "%d/%m/%Y",
            "%Y-%m-%d",
            "%d/%m/%y",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt).date()
                return parsed
            except ValueError:
                continue

        parsed = self._parse_catalan_date(date_str, today)
        if parsed:
            return parsed

        return None

    def _parse_catalan_date(self, date_str: str, today: date) -> Optional[date]:
        date_str_lower = date_str.lower()

        month_match = re.search(r"(\d{1,2})\s+de\s+(\w+)", date_str_lower)
        if month_match:
            day = int(month_match.group(1))
            month_name = month_match.group(2)
            month_num = CATALAN_MONTHS.get(month_name)
            if month_num:
                year = today.year
                if month_num < today.month and not re.search(r"202\d", date_str):
                    year = today.year + 1
                try:
                    return date(year, month_num, day)
                except ValueError:
                    pass

        weekday_match = re.search(
            r"(dilluns|dimarts|dimecres|dijous|divendres|dissabte|diumenge)", date_str_lower
        )
        if weekday_match:
            weekday_name = weekday_match.group(1)
            target_weekday = CATALAN_WEEKDAYS[weekday_name]
            current_weekday = today.weekday()
            days_ahead = (target_weekday - current_weekday) % 7
            if days_ahead == 0:
                days_ahead = 7
            return today + timedelta(days=days_ahead)

        day_only = re.match(r"^\d{1,2}$", date_str.strip())
        if day_only:
            try:
                day = int(date_str.strip())
                if 1 <= day <= 31:
                    if day >= today.day and day <= 31:
                        return today.replace(day=day)
            except ValueError:
                pass

        month_year = re.match(r"(\d{2})/(\d{4})", date_str.strip())
        if month_year:
            month_num = int(month_year.group(1))
            year = int(month_year.group(2))
            if 1 <= month_num <= 12:
                return date(year, month_num, 1)

        return None

    def _parse_time(self, time_str: Optional[str]) -> Optional[tuple[int, int]]:
        if not time_str:
            return None

        time_str = time_str.strip()
        time_str = time_str.replace("h", ":").replace(":", " ").strip()

        match = re.search(r"(\d{1,2})[:.]?(\d{2})?", time_str)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            if 0 <= hour <= 23:
                return (hour, minute)

        return None


def deduplicate_events(events: list[Event]) -> list[Event]:
    seen = set()
    unique = []

    for event in events:
        key = normalize_event_key(event)
        if key not in seen:
            seen.add(key)
            unique.append(event)

    return unique


def normalize_event_key(event: Event) -> str:
    title = (event.title or "").lower().strip()
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title)

    date = (event.date or "").lower().strip()

    organizer = (event.organizer or event.source or "").lower().strip()
    organizer = re.sub(r"[^\w\s]", "", organizer)
    organizer = re.sub(r"\s+", " ", organizer)

    return f"{title}|{date}|{organizer}"
