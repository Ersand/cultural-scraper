"""Shared constants and utilities for cultural scraper."""

from datetime import date, datetime, timedelta
import re
from typing import Optional

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

CATALAN_MONTHS_NAMES: dict[int, str] = {v: k.capitalize() for k, v in CATALAN_MONTHS.items()}

CATALAN_WEEKDAYS: dict[str, int] = {
    "dilluns": 0,
    "dimarts": 1,
    "dimecres": 2,
    "dijous": 3,
    "divendres": 4,
    "dissabte": 5,
    "diumenge": 6,
}

CATALAN_WEEKDAY_NAMES = ["Dl", "Dm", "Dc", "Dj", "Dv", "Ds", "Dg"]


def strip_html(html_string: str) -> str:
    """Remove HTML tags from string."""
    return re.sub(r"<[^>]+>", "", html_string).strip()


def normalize_url(url: str, base: str) -> str:
    """Ensure URL is absolute."""
    if not url:
        return ""
    if url.startswith("http"):
        return url
    if url.startswith("/"):
        return f"{base.rstrip('/')}{url}"
    return f"{base.rstrip('/')}/{url}"


def parse_date(date_str: Optional[str], *, today: Optional[date] = None) -> Optional[date]:
    """Parse date string in various formats. Returns None if unparseable."""
    if not date_str:
        return None

    date_str = date_str.strip()
    today = today or date.today()

    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    return _parse_catalan_date(date_str, today)


def _parse_catalan_date(date_str: str, today: date) -> Optional[date]:
    """Parse Catalan-format dates like '15 de maig' or 'dilluns' or just a day number."""
    lower = date_str.lower()

    month_match = re.search(r"(\d{1,2})\s+de\s+(\w+)", lower)
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
        r"(dilluns|dimarts|dimecres|dijous|divendres|dissabte|diumenge)", lower
    )
    if weekday_match:
        target_weekday = CATALAN_WEEKDAYS[weekday_match.group(1)]
        days_ahead = (target_weekday - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)

    day_only = re.match(r"^\d{1,2}$", date_str.strip())
    if day_only:
        day = int(date_str.strip())
        if 1 <= day <= 31 and day >= today.day:
            try:
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


def parse_date_range(date_str: str) -> list[date]:
    """Parse date string that may contain a range. Returns list of dates."""
    if not date_str:
        return []

    date_str = date_str.strip()

    single = parse_date(date_str)
    if single:
        return [single]

    range_match = re.search(
        r"(?:Del|Des de)\s+(\d{1,2})/(\d{1,2})/(\d{2,4})\s+(?:al|fins)\s+(\d{1,2})/(\d{1,2})/(\d{2,4})",
        date_str,
        re.IGNORECASE,
    )
    if range_match:
        try:
            sd, sm, sy = (
                int(range_match.group(1)),
                int(range_match.group(2)),
                int(range_match.group(3)),
            )
            ed, em, ey = (
                int(range_match.group(4)),
                int(range_match.group(5)),
                int(range_match.group(6)),
            )
            if sy < 100:
                sy += 2000
            if ey < 100:
                ey += 2000
            start = date(sy, sm, sd)
            end = date(ey, em, ed)
            if (end - start).days > 31:
                end = start + timedelta(days=31)
            result = []
            current = start
            while current <= end:
                result.append(current)
                current += timedelta(days=1)
            return result
        except (ValueError, IndexError):
            pass

    month_match = re.match(r"(\d{2})/(\d{4})", date_str)
    if month_match:
        try:
            month_num = int(month_match.group(1))
            year = int(month_match.group(2))
            result = []
            for day in range(1, 32):
                try:
                    result.append(date(year, month_num, day))
                except ValueError:
                    break
            return result
        except ValueError:
            pass

    return []


def parse_time(time_str: Optional[str]) -> Optional[tuple[int, int]]:
    """Parse time string like '18:30' or '18h30'. Returns (hour, minute) or None."""
    if not time_str:
        return None

    time_str = time_str.strip().replace("h", ":").replace(":", " ").strip()
    match = re.search(r"(\d{1,2})[:.]?(\d{2})?", time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        if 0 <= hour <= 23:
            return (hour, minute)

    return None
