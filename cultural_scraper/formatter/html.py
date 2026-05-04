from datetime import datetime, timedelta, date as date_type
import json
from typing import Any
from cultural_scraper.core import Event
from cultural_scraper.utils import CATALAN_WEEKDAY_NAMES, parse_date_range

CATEGORY_COLORS = {
    "teatre": "#e74c3c",
    "música": "#9b59b6",
    "cinema": "#f39c12",
    "balls": "#1abc9c",
    "xerrades": "#34495e",
    "exposicions": "#e91e63",
    "literatura": "#00bcd4",
    "infantil": "#4caf50",
    "fires": "#ff5722",
    "gastronomia": "#795548",
    "altres": "#95a5a6",
}

SOURCE_COLORS = {
    "cccb": "#e63946",
    "ateneu barcelonès": "#457b9d",
    "ateneu": "#457b9d",
    "biblioteques barcelona": "#2a9d8f",
    "biblioteques": "#2a9d8f",
    "guia barcelona": "#f4a261",
    "guia": "#f4a261",
}

DEFAULT_COLOR = "#6c757d"

CATALAN_MONTH_NAMES = {
    1: "Gener",
    2: "Febrer",
    3: "Març",
    4: "Abril",
    5: "Maig",
    6: "Juny",
    7: "Juliol",
    8: "Agost",
    9: "Setembre",
    10: "Octubre",
    11: "Novembre",
    12: "Desembre",
}

KNOWN_CATEGORIES = {
    "teatre",
    "música",
    "cinema",
    "balls",
    "xerrades",
    "exposicions",
    "literatura",
    "infantil",
    "fires",
    "gastronomia",
    "cursos i tallers",
    "debats",
    "audiovisuals",
    "accessible",
    "educació",
    "itineraris",
    "altres",
    "escena",
}

KNOWN_SOURCES = {
    "cccb",
    "ateneu barcelonès",
    "biblioteques barcelona",
    "guia barcelona",
    "biblioteques",
    "ateneu",
}


def _color(name: str, palette: dict[str, str]) -> str:
    return palette.get(name.lower(), DEFAULT_COLOR)


class HtmlFormatter:
    def __init__(
        self,
        title: str = "Larry",
        date: str | None = None,
        last_updated: str | None = None,
        category_classifier=None,
    ) -> None:
        self.title = title
        self.date = date or datetime.now().strftime("%d-%m-%Y")
        self.last_updated = last_updated
        self.category_classifier = category_classifier

    def format(self, events_by_source: dict[str, list[Event]]) -> str:
        categorized = self._add_categories(events_by_source)
        all_events = self._collect_events(categorized)
        all_events = self._filter_by_date_range(all_events)

        self._attach_flags(all_events)
        sources, categories = self._aggregate_flags(all_events)

        parts = [
            "<!DOCTYPE html>",
            "<html lang='ca'>",
            "<head>",
            "<meta charset='UTF-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            f"<title>{self.title}</title>",
            "<style>",
            self._get_css(),
            "</style>",
            "</head>",
            "<body>",
        ]
        parts.extend(self._render_header())
        parts.append("<div class='update-button'>")
        parts.append(
            "<a href='https://github.com/Ersand/cultural-scraper/actions/workflows/deploy.yml' "
            "target='_blank' class='btn-update'>Actualitzar</a>"
        )
        parts.append("</div>")

        if categories or sources:
            parts.append("<aside class='sidebar'>")
            parts.extend(self._render_sources(sources))
            parts.extend(self._render_categories(categories))
            parts.append("</aside>")

        parts.append("<div class='main-content'>")
        parts.extend(self._render_errors(categorized))
        parts.append("<div class='calendar-container'>")
        parts.append(self._generate_calendar(all_events))
        parts.append("</div>")

        parts.append(f"<footer><p>Total: {len(all_events)} esdeveniments</p></footer>")
        parts.extend(self._render_data_scripts(all_events))
        parts.extend(self._render_js())
        parts.extend(self._render_modal())
        parts.append("</div>")
        parts.append("</div>")
        parts.append("</body>")
        parts.append("</html>")

        return "\n".join(parts)

    def _add_categories(self, events_by_source: dict[str, list[Event]]) -> dict[str, list[Event]]:
        if not self.category_classifier:
            return events_by_source

        result = {}
        for source, events in events_by_source.items():
            for event in events:
                event.event_category = self.category_classifier(event)
            result[source] = events
        return result

    def _collect_events(self, events_by_source: dict[str, list[Event]]) -> list[Event]:
        events = []
        for source, source_events in events_by_source.items():
            if source == "_errors":
                continue
            for event in source_events:
                if event.date and "permanent" not in event.date.lower():
                    event.organizer = event.organizer or source
                    events.append(event)
        return events

    def _filter_by_date_range(self, events: list[Event]) -> list[Event]:
        today = datetime.now().date()
        next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        following = (next_month + timedelta(days=32)).replace(day=1)

        return [e for e in events if any(today <= d < following for d in parse_date_range(e.date))]

    def _attach_flags(self, events: list[Event]) -> None:
        for event in events:
            event.flags = self._extract_flags(event)  # type: ignore[attr-defined]

    def _extract_flags(self, event: Event) -> list[str]:
        flags = []
        cat = event.event_category or "altres"
        flags.append(f"category:{cat}")

        source_lower = event.source.lower().strip() if event.source else ""
        if source_lower and source_lower not in KNOWN_CATEGORIES:
            flags.append(f"source:{event.source}")

        for tag in event.tags or []:
            if not tag:
                continue
            tag_lower = tag.lower()
            existing = {f.split(":", 1)[1] for f in flags}
            if tag_lower in KNOWN_CATEGORIES and tag_lower not in existing:
                flags.append(f"category:{tag}")
            elif tag_lower in KNOWN_SOURCES and f"source:{tag}" not in flags:
                flags.append(f"source:{tag}")

        return flags

    def _aggregate_flags(self, events: list[Event]) -> tuple[dict[str, int], dict[str, int]]:
        sources: dict[str, int] = {}
        categories: dict[str, int] = {}

        for event in events:
            for flag in getattr(event, "flags", []):
                if flag.startswith("source:"):
                    name = flag[7:]
                    sources[name] = sources.get(name, 0) + 1
                elif flag.startswith("category:"):
                    name = flag[9:]
                    categories[name] = categories.get(name, 0) + 1

        return (
            sources or {"Altres": 0},
            categories or {"Altres": 0},
        )

    def _render_header(self) -> list[str]:
        parts = [
            "<header>",
            f"<h1>{self.title}</h1>",
            f"<p class='date'>Avui: {self.date}</p>",
        ]
        if self.last_updated:
            parts.append(f"<p class='last-updated'>Darrera actualització: {self.last_updated}</p>")
        parts.append("</header>")
        return parts

    def _render_sources(self, sources: dict[str, int]) -> list[str]:
        if not sources:
            return []
        parts = [
            "<nav class='source-index'>",
            "<h2>Llocs</h2>",
            "<div class='category-actions'>",
            "<button onclick='selectAllSources()' class='btn-select'>Tots</button>",
            "<button onclick='deselectAllSources()' class='btn-deselect'>Cap</button>",
            "</div>",
            "<ul>",
        ]
        for src, count in sorted(sources.items(), key=lambda x: -x[1]):
            color = _color(src, SOURCE_COLORS)
            parts.append(
                f"<li><label><input type='checkbox' class='source-filter' value='{src}'> "
                f"<span class='category-dot' style='background:{color}'></span>"
                f"{src.capitalize()} ({count})</label></li>"
            )
        parts.append("</ul></nav>")
        return parts

    def _render_categories(self, categories: dict[str, int]) -> list[str]:
        if not categories:
            return []
        parts = [
            "<nav class='category-index'>",
            "<h2>Categories</h2>",
            "<div class='category-actions'>",
            "<button onclick='selectAllCategories()' class='btn-select'>Tots</button>",
            "<button onclick='deselectAllCategories()' class='btn-deselect'>Cap</button>",
            "</div>",
            "<ul>",
        ]
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            color = _color(cat, CATEGORY_COLORS)
            parts.append(
                f"<li><label><input type='checkbox' class='category-filter' value='{cat}'> "
                f"<span class='category-dot' style='background:{color}'></span>"
                f"{cat.capitalize()} ({count})</label></li>"
            )
        parts.append("</ul></nav>")
        return parts

    def _render_errors(self, events_by_source: dict[str, list[Event]]) -> list[str]:
        errors = events_by_source.get("_errors", [])
        if not errors:
            return []
        parts = ["<section class='errors'>", "<h2>Errors</h2>", "<ul>"]
        for error in errors:
            parts.append(f"<li>{error}</li>")
        parts.append("</ul></section>")
        return parts

    def _generate_calendar(self, events: list[Event]) -> str:
        events_by_date: dict[date_type, list[Event]] = {}
        for event in events:
            for d in parse_date_range(event.date):
                events_by_date.setdefault(d, []).append(event)

        today = datetime.now().date()
        current = datetime(today.year, today.month, 1)
        next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)

        return "\n".join(
            [
                f"<div class='calendar-wrapper'>{self._render_month(current, events_by_date, today)}</div>",
                f"<div class='calendar-wrapper'>{self._render_month(next_month, events_by_date, today)}</div>",
            ]
        )

    def _render_month(
        self,
        month: datetime,
        events_by_date: dict[date_type, list[Event]],
        today: date_type,
    ) -> str:
        parts = [
            "<div class='calendar-nav'>",
            f"<h3>{CATALAN_MONTH_NAMES[month.month]} {month.year}</h3>",
            "</div>",
            "<div class='calendar-inner'>",
            "<div class='calendar-grid'>",
        ]

        for day in CATALAN_WEEKDAY_NAMES:
            parts.append(f"<div class='calendar-header'>{day}</div>")

        first = month.replace(day=1)
        last = (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        start_weekday = first.weekday()

        day_num = 1
        for i in range(42):
            if i < start_weekday:
                parts.append("<div class='calendar-day other-month'></div>")
            elif day_num <= last.day:
                current_date = month.replace(day=day_num)
                classes = "calendar-day"
                if current_date == today:
                    classes += " today"

                day_str = current_date.strftime("%Y-%m-%d")
                day_events = events_by_date.get(current_date, [])

                parts.append(
                    f"<div class='{classes}' data-day='{day_str}' onclick=\"showDayEvents('{day_str}')\">"
                )
                parts.append(f"<div class='calendar-day-number'>{day_num}</div>")
                parts.append("<div class='day-events'>")

                for evt in day_events[:3]:
                    cat = getattr(evt, "event_category", "altres") or "altres"
                    color = _color(cat, CATEGORY_COLORS)
                    title_esc = evt.title.replace("'", "\\'").replace('"', '\\"')
                    parts.append(
                        f"<div class='calendar-event' style='background:{color}' "
                        f"title='{title_esc}'>{evt.title[:20]}</div>"
                    )

                if len(day_events) > 3:
                    parts.append(f"<div class='calendar-event-more'>+{len(day_events) - 3}</div>")

                parts.append("</div></div>")
                day_num += 1
            else:
                parts.append("<div class='calendar-day other-month'></div>")

        parts.append("</div></div>")
        return "\n".join(parts)

    def _render_data_scripts(self, events: list[Event]) -> list[str]:
        by_date: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            for d in parse_date_range(event.date):
                day_str = d.strftime("%Y-%m-%d")
                cat = getattr(event, "event_category", "altres") or "altres"
                by_date.setdefault(day_str, []).append(
                    {
                        "title": event.title,
                        "source": event.source,
                        "url": event.url,
                        "date": event.date,
                        "time": event.time,
                        "location": event.location,
                        "category": cat,
                        "color": _color(cat, CATEGORY_COLORS),
                        "flags": getattr(event, "flags", []),
                    }
                )

        return [
            f"<script>window.allDayEvents = {json.dumps(by_date)};</script>",
            f"<script>window.categoryColors = {json.dumps({**CATEGORY_COLORS, 'default': DEFAULT_COLOR})};</script>",
        ]

    def _render_js(self) -> list[str]:
        return ["<script>", JS_FILTER_FUNCTIONS, "</script>"]

    def _render_modal(self) -> list[str]:
        return [
            "<div id='eventModal' class='calendar-modal' onclick='closeModal()'>",
            "<div class='calendar-modal-content' onclick='event.stopPropagation()'>",
            "<span class='calendar-modal-close' onclick='closeModal()'>&times;</span>",
            "<h3 id='modalTitle'></h3>",
            "<div id='modalContent'></div>",
            "</div></div>",
            "<script>",
            JS_MODAL_FUNCTIONS,
            "</script>",
        ]

    def _get_css(self) -> str:
        return CSS


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       line-height: 1.6; color: #333; margin: 0 auto; padding: 20px; background: #f5f5f5; }
.container { display: flex; gap: 20px; max-width: 1600px; margin: 0 auto; }
.sidebar { width: 280px; flex-shrink: 0; }
.main-content { flex: 1; min-width: 0; }
header { text-align: center; margin-bottom: 30px; padding: 20px; background: #2c3e50;
         color: white; border-radius: 8px; }
header h1 { font-size: 1.5em; margin-bottom: 10px; }
header .date { opacity: 0.8; margin: 5px 0; }
header .last-updated { opacity: 0.6; font-size: 0.8em; margin: 5px 0; }
.update-button { text-align: center; margin-bottom: 20px; }
.btn-update { display: inline-block; padding: 10px 20px; background: #95a5a6;
              color: white; text-decoration: none; border-radius: 6px; font-size: 0.9em; }
.btn-update:hover { background: #7f8c8d; }
.source-index { background: white; padding: 20px; border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
.category-index { background: white; padding: 20px; border-radius: 8px;
                  box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.source-index h2, .category-index h2 { font-size: 1.2em; margin-bottom: 15px;
                                        color: #2c3e50; text-align: center; }
.category-actions { display: flex; gap: 10px; margin-bottom: 15px; }
.category-actions button { flex: 1; padding: 8px; border: none; border-radius: 4px;
                           cursor: pointer; font-size: 0.9em; }
.btn-select, .btn-deselect { background: #95a5a6; color: white; }
.btn-select:hover, .btn-deselect:hover { background: #7f8c8d; }
.source-index ul, .category-index ul { list-style: none; }
.source-index li, .category-index li { margin-bottom: 10px; }
.source-index label, .category-index label { display: flex; align-items: center; gap: 10px;
    cursor: pointer; font-size: 1em; padding: 8px; border-radius: 4px; transition: background 0.2s; }
.source-index label:hover, .category-index label:hover { background: #f0f0f0; }
.source-index input[type="checkbox"], .category-index input[type="checkbox"] { margin: 0; width: 18px; height: 18px; }
.category-dot { width: 14px; height: 14px; border-radius: 3px; display: inline-block; }
.calendar-container { display: flex; flex-direction: column; gap: 30px; align-items: center; width: 100%; }
.calendar-wrapper { width: 100%; max-width: 100%; overflow-x: auto; }
.calendar-inner { min-width: 700px; }
.calendar-nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.calendar-nav h3 { margin: 0; font-size: 1.3em; color: #2c3e50; }
.calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px;
                 background: #ddd; border-radius: 8px; min-width: 700px; }
.calendar-header { background: #2c3e50; color: white; padding: 12px 5px; text-align: center;
                   font-weight: bold; font-size: 0.85em; }
.calendar-day { background: white; min-height: 100px; padding: 5px; vertical-align: top;
                cursor: pointer; transition: background 0.2s; }
.calendar-day:hover { background: #f8f8f8; }
.calendar-day.other-month { background: #f5f5f5; color: #999; }
.calendar-day.other-month .calendar-day-number { color: #999; }
.calendar-day.today { background: #e8f4f8; }
.calendar-day.today .calendar-day-number { background: #3498db; color: white; border-radius: 50%;
    width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; }
.calendar-day-number { font-weight: bold; margin-bottom: 5px; font-size: 0.9em; }
.day-events { display: flex; flex-direction: column; gap: 2px; }
.calendar-event { font-size: 0.65em; padding: 2px 4px; border-radius: 2px;
                  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: white; }
.calendar-event:hover { opacity: 0.9; }
.calendar-event-more { font-size: 0.65em; padding: 2px 4px; background: #7f8c8d;
                        color: white; border-radius: 2px; text-align: center; }
.errors { background: #fee; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
.errors h2 { color: #c00; }
footer { text-align: center; padding: 20px; color: #666; clear: both; margin-top: 30px; }
.calendar-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                  background: rgba(0,0,0,0.6); z-index: 1000; }
.calendar-modal.active { display: flex; align-items: center; justify-content: center; }
.calendar-modal-content { background: white; padding: 25px; border-radius: 12px;
                          max-width: 600px; max-height: 80vh; overflow-y: auto; width: 90%; }
.calendar-modal h3 { margin-bottom: 20px; color: #2c3e50; font-size: 1.4em;
                     border-bottom: 2px solid #3498db; padding-bottom: 10px; }
.calendar-modal-close { float: right; cursor: pointer; font-size: 1.8em; color: #666; line-height: 1; }
.calendar-modal-close:hover { color: #333; }
.modal-event { padding: 15px; margin-bottom: 15px; background: #fafafa; border-radius: 6px; }
.modal-event h4 { margin: 0 0 10px 0; font-size: 1.1em; }
.modal-event h4 a { color: #2980b9; text-decoration: none; }
.modal-event h4 a:hover { text-decoration: underline; }
.modal-event-info { display: flex; flex-wrap: wrap; gap: 15px; font-size: 0.9em; color: #555; }
.modal-event-info span { display: flex; gap: 5px; }
.modal-event-info strong { color: #333; }
.modal-category { font-size: 0.8em; font-weight: bold; margin-top: 8px; text-transform: uppercase; }
.no-events { color: #999; font-style: italic; text-align: center; padding: 20px; }
@media (max-width: 900px) {
    .container { flex-direction: column; }
    .sidebar { width: 100%; }
    .calendar-wrapper { max-width: 100%; }
}
"""

JS_FILTER_FUNCTIONS = """
function selectAllCategories() {
  document.querySelectorAll('.category-filter').forEach(cb => cb.checked = true);
  filterByCategory();
}
function deselectAllCategories() {
  document.querySelectorAll('.category-filter').forEach(cb => cb.checked = false);
  filterByCategory();
}
function selectAllSources() {
  document.querySelectorAll('.source-filter').forEach(cb => cb.checked = true);
  filterByCategory();
}
function deselectAllSources() {
  document.querySelectorAll('.source-filter').forEach(cb => cb.checked = false);
  filterByCategory();
}
function filterByCategory() {
  const cats = Array.from(document.querySelectorAll('.category-filter'))
    .filter(cb => cb.checked).map(cb => 'category:' + cb.value);
  const srcs = Array.from(document.querySelectorAll('.source-filter'))
    .filter(cb => cb.checked).map(cb => 'source:' + cb.value);

  document.querySelectorAll('.calendar-day').forEach(dayEl => {
    const dayStr = dayEl.dataset.day;
    const events = (window.allDayEvents || {})[dayStr] || [];
    const visible = events.filter(e => {
      const flags = e.flags || [];
      const catOk = cats.length === 0 || cats.some(f => flags.includes(f));
      const srcOk = srcs.length === 0 || srcs.some(f => flags.includes(f));
      return catOk && srcOk;
    });
    const container = dayEl.querySelector('.day-events');
    if (container) {
      container.innerHTML = '';
      visible.slice(0, 3).forEach(e => {
        const d = document.createElement('div');
        d.className = 'calendar-event';
        d.style.backgroundColor = e.color || '#3498db';
        d.textContent = e.title.substring(0, 20);
        d.title = e.title;
        container.appendChild(d);
      });
      if (visible.length > 3) {
        const m = document.createElement('div');
        m.className = 'calendar-event-more';
        m.textContent = '+' + (visible.length - 3);
        container.appendChild(m);
      }
    }
  });
}
document.querySelectorAll('.category-filter, .source-filter').forEach(cb => {
  cb.addEventListener('change', filterByCategory);
});
"""

JS_MODAL_FUNCTIONS = """
function showDayEvents(dayStr) {
  const modal = document.getElementById('eventModal');
  const content = document.getElementById('modalContent');
  const title = document.getElementById('modalTitle');

  const parts = dayStr.split('-');
  const dateObj = new Date(parts[0], parts[1] - 1, parts[2]);
  title.textContent = dateObj.toLocaleDateString('ca-ES', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  });

  const allEvents = window.allDayEvents || {};
  const events = allEvents[dayStr] || [];
  const cats = Array.from(document.querySelectorAll('.category-filter'))
    .filter(cb => cb.checked).map(cb => 'category:' + cb.value);
  const srcs = Array.from(document.querySelectorAll('.source-filter'))
    .filter(cb => cb.checked).map(cb => 'source:' + cb.value);
  const visible = events.filter(e => {
    const flags = e.flags || [];
    const catOk = cats.length === 0 || cats.some(f => flags.includes(f));
    const srcOk = srcs.length === 0 || srcs.some(f => flags.includes(f));
    return catOk && srcOk;
  });

  if (visible.length === 0) {
    content.innerHTML = '<p class="no-events">No hi ha esdeveniments</p>';
  } else {
    let html = '';
    visible.forEach(e => {
      const color = e.color || '#3498db';
      html += `<div class='modal-event' style='border-left: 4px solid ${color}'>`;
      html += e.url
        ? `<h4><a href='${e.url}' target='_blank'>${e.title}</a></h4>`
        : `<h4>${e.title}</h4>`;
      html += `<div class='modal-event-info'>`;
      if (e.date) html += `<span><strong>Data:</strong> ${e.date}</span>`;
      if (e.time) html += `<span><strong>Hora:</strong> ${e.time}</span>`;
      if (e.location) html += `<span><strong>Lloc:</strong> ${e.location}</span>`;
      html += `</div>`;
      html += `<div class='modal-category' style='color:${color}'>${e.category}</div>`;
      html += `</div>`;
    });
    content.innerHTML = html;
  }
  modal.classList.add('active');
}
function closeModal() {
  document.getElementById('eventModal').classList.remove('active');
}
"""
