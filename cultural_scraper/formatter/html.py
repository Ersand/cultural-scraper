from datetime import datetime, timedelta
import json
import re
from cultural_scraper.core import Event


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
    "agenda": "#3498db",
    "que fer": "#f1c40f",
    "art": "#e67e22",
    "família": "#27ae60",
    "cursos i tallers": "#8e44ad",
    "audiovisuals": "#2980b9",
    "amics cccb": "#c0392b",
    "accessible": "#16a085",
    "educació": "#d35400",
    "itineraris": "#2c3e50",
    "debat": "#7f8c8d",
    "altres": "#95a5a6",
}


class HtmlFormatter:
    def __init__(
        self,
        title: str = "Cultural Plans",
        date: str | None = None,
        category_classifier=None,
    ) -> None:
        self.title = title
        self.date = date or datetime.now().strftime("%d-%m-%Y")
        self.category_classifier = category_classifier

    def format(self, events_by_source: dict[str, list[Event]]) -> str:
        html_parts: list[str] = []
        html_parts.append("<!DOCTYPE html>")
        html_parts.append("<html lang='ca'>")
        html_parts.append("<head>")
        html_parts.append("<meta charset='UTF-8'>")
        html_parts.append("<meta name='viewport' content='width=device-width, initial-scale=1.0'>")
        html_parts.append(f"<title>{self.title}</title>")
        html_parts.append("<style>")
        html_parts.append(self._get_css())
        html_parts.append("</style>")
        html_parts.append("</head>")
        html_parts.append("<body>")
        html_parts.append(f"<header><h1>{self.title}</h1>")
        html_parts.append(f"<p class='date'>{self.date}</p></header>")

        events_with_category = self._add_categories(events_by_source)

        day_events_by_organizer = {}
        permanent_events_by_organizer = {}
        range_events_by_organizer = {}

        for source, events in events_with_category.items():
            if source == "_errors":
                continue

            if not events:
                continue

            for event in events:
                is_permanent = event.date and "permanent" in event.date.lower()
                is_range = event.date and (
                    "al " in event.date.lower()
                    or "del " in event.date.lower()
                    or "des de" in event.date.lower()
                )

                organizer = event.organizer or source

                if organizer not in day_events_by_organizer:
                    day_events_by_organizer[organizer] = []
                if organizer not in permanent_events_by_organizer:
                    permanent_events_by_organizer[organizer] = []
                if organizer not in range_events_by_organizer:
                    range_events_by_organizer[organizer] = []

                if is_permanent:
                    permanent_events_by_organizer[organizer].append(event)
                elif is_range:
                    range_events_by_organizer[organizer].append(event)
                else:
                    day_events_by_organizer[organizer].append(event)

        all_day_events = [e for events in day_events_by_organizer.values() for e in events] + [
            e for events in range_events_by_organizer.values() for e in events
        ]

        today = datetime.now().date()
        next_month = today.replace(day=28) + timedelta(days=4)
        next_month = next_month.replace(day=1)
        following_month = next_month.replace(day=1) + timedelta(days=32)
        following_month = following_month.replace(day=1)

        all_day_events = [
            e
            for e in all_day_events
            if self._parse_event_dates(e.date)
            and any(today <= d < following_month for d in self._parse_event_dates(e.date))
        ]

        categories_with_events = {}
        for event in all_day_events:
            if hasattr(event, "event_category") and event.event_category:
                cat = event.event_category
                if cat not in categories_with_events:
                    categories_with_events[cat] = 0
                categories_with_events[cat] += 1

        html_parts.append("<div class='container'>")

        if categories_with_events:
            html_parts.append("<aside class='sidebar'>")
            html_parts.append("<nav class='category-index'>")
            html_parts.append("<h2>Categories</h2>")
            html_parts.append("<div class='category-actions'>")
            html_parts.append(
                "<button onclick='selectAllCategories()' class='btn-select'>Tots</button>"
            )
            html_parts.append(
                "<button onclick='deselectAllCategories()' class='btn-deselect'>Cap</button>"
            )
            html_parts.append("</div>")
            html_parts.append("<ul>")
            for cat, count in sorted(categories_with_events.items(), key=lambda x: -x[1]):
                color = CATEGORY_COLORS.get(cat, "#95a5a6")
                cat_display = cat.capitalize()
                html_parts.append(
                    f"<li><label><input type='checkbox' class='category-filter' value='{cat}'> "
                    f"<span class='category-dot' style='background:{color}'></span>{cat_display} ({count})</label></li>"
                )
            html_parts.append("</ul>")
            html_parts.append("</nav>")
            html_parts.append("</aside>")

        html_parts.append("<div class='main-content'>")

        errors = events_with_category.get("_errors", [])
        if errors:
            html_parts.append("<section class='errors'>")
            html_parts.append("<h2>Errors</h2>")
            html_parts.append("<ul>")
            for error in errors:
                html_parts.append(f"<li>{error}</li>")
            html_parts.append("</ul>")
            html_parts.append("</section>")

        calendar_html = self._generate_two_months_calendar(all_day_events)
        html_parts.append("<div class='calendar-container'>")
        html_parts.append(calendar_html)
        html_parts.append("</div>")

        total_events = len(all_day_events) + sum(
            len(events) for events in permanent_events_by_organizer.values()
        )
        html_parts.append(f"<footer><p>Total: {total_events} esdeveniments</p></footer>")

        events_by_date_json = {}
        for event in all_day_events:
            dates = self._parse_event_dates(event.date)
            for d in dates:
                day_str = d.strftime("%Y-%m-%d")
                if day_str not in events_by_date_json:
                    events_by_date_json[day_str] = []
                event_cat = getattr(event, "event_category", "altres")
                category_color = CATEGORY_COLORS.get(event_cat, "#95a5a6")
                events_by_date_json[day_str].append(
                    {
                        "title": event.title,
                        "source": event.source,
                        "url": event.url,
                        "date": event.date,
                        "time": event.time,
                        "location": event.location,
                        "category": event_cat,
                        "color": category_color,
                    }
                )

        categories_json = json.dumps(CATEGORY_COLORS)

        html_parts.append(
            f"<script>window.allDayEvents = {json.dumps(events_by_date_json)};</script>"
        )
        html_parts.append(f"<script>window.categoryColors = {categories_json};</script>")

        html_parts.append("<script>")
        html_parts.append("function selectAllCategories() {")
        html_parts.append(
            "  document.querySelectorAll('.category-filter').forEach(cb => cb.checked = true);"
        )
        html_parts.append("  filterByCategory();")
        html_parts.append("}")
        html_parts.append("function deselectAllCategories() {")
        html_parts.append(
            "  document.querySelectorAll('.category-filter').forEach(cb => cb.checked = false);"
        )
        html_parts.append("  filterByCategory();")
        html_parts.append("}")
        html_parts.append("function filterByCategory() {")
        html_parts.append("  const checkboxes = document.querySelectorAll('.category-filter');")
        html_parts.append("  const selectedCategories = Array.from(checkboxes)")
        html_parts.append("    .filter(cb => cb.checked)")
        html_parts.append("    .map(cb => cb.value);")
        html_parts.append("  ")
        html_parts.append("  document.querySelectorAll('.calendar-day').forEach(dayEl => {")
        html_parts.append("    const dayStr = dayEl.dataset.day;")
        html_parts.append("    const events = (window.allDayEvents || {})[dayStr] || [];")
        html_parts.append(
            "    const visibleEvents = selectedCategories.length === 0 ? events : events.filter(e => selectedCategories.includes(e.category));"
        )
        html_parts.append("    ")
        html_parts.append("    const eventsContainer = dayEl.querySelector('.day-events');")
        html_parts.append("    if (eventsContainer) {")
        html_parts.append("      eventsContainer.innerHTML = '';")
        html_parts.append("      visibleEvents.slice(0, 3).forEach(e => {")
        html_parts.append("        const evtDiv = document.createElement('div');")
        html_parts.append("        evtDiv.className = 'calendar-event';")
        html_parts.append("        evtDiv.style.backgroundColor = e.color || '#3498db';")
        html_parts.append("        evtDiv.textContent = e.title.substring(0, 20);")
        html_parts.append("        evtDiv.title = e.title;")
        html_parts.append("        eventsContainer.appendChild(evtDiv);")
        html_parts.append("      });")
        html_parts.append("      if (visibleEvents.length > 3) {")
        html_parts.append("        const moreDiv = document.createElement('div');")
        html_parts.append("        moreDiv.className = 'calendar-event-more';")
        html_parts.append("        moreDiv.textContent = '+' + (visibleEvents.length - 3);")
        html_parts.append("        eventsContainer.appendChild(moreDiv);")
        html_parts.append("      }")
        html_parts.append("    }")
        html_parts.append("  });")
        html_parts.append("}")
        html_parts.append("document.querySelectorAll('.category-filter').forEach(cb => {")
        html_parts.append("  cb.addEventListener('change', filterByCategory);")
        html_parts.append("});")
        html_parts.append("</script>")

        html_parts.append("<div id='eventModal' class='calendar-modal' onclick='closeModal()'>")
        html_parts.append("<div class='calendar-modal-content' onclick='event.stopPropagation()'>")
        html_parts.append(
            "<span class='calendar-modal-close' onclick='closeModal()'>&times;</span>"
        )
        html_parts.append("<h3 id='modalTitle'></h3>")
        html_parts.append("<div id='modalContent'></div>")
        html_parts.append("</div>")
        html_parts.append("</div>")

        html_parts.append("<script>")
        html_parts.append("function showDayEvents(dayStr) {")
        html_parts.append("  const modal = document.getElementById('eventModal');")
        html_parts.append("  const content = document.getElementById('modalContent');")
        html_parts.append("  const title = document.getElementById('modalTitle');")
        html_parts.append("  ")
        html_parts.append("  const dateParts = dayStr.split('-');")
        html_parts.append(
            "  const dateObj = new Date(dateParts[0], dateParts[1] - 1, dateParts[2]);"
        )
        html_parts.append(
            "  const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };"
        )
        html_parts.append("  title.textContent = dateObj.toLocaleDateString('ca-ES', options);")
        html_parts.append("  ")
        html_parts.append("  const allEvents = window.allDayEvents || {};")
        html_parts.append("  const events = allEvents[dayStr] || [];")
        html_parts.append("  const colors = window.categoryColors || {};")
        html_parts.append("  ")
        html_parts.append(
            "  const selectedCategories = Array.from(document.querySelectorAll('.category-filter'))"
        )
        html_parts.append("    .filter(cb => cb.checked)")
        html_parts.append("    .map(cb => cb.value);")
        html_parts.append(
            "  const visibleEvents = selectedCategories.length === 0 ? events : events.filter(e => selectedCategories.includes(e.category));"
        )
        html_parts.append("  ")
        html_parts.append("  if (visibleEvents.length === 0) {")
        html_parts.append(
            "    content.innerHTML = '<p class=\"no-events\">No hi ha esdeveniments</p>';"
        )
        html_parts.append("  } else {")
        html_parts.append("    let html = '';")
        html_parts.append("    visibleEvents.forEach(e => {")
        html_parts.append("      const color = e.color || '#3498db';")
        html_parts.append(
            "      html += `<div class='modal-event' style='border-left: 4px solid ${color}'>`;"
        )
        html_parts.append("      if (e.url) {")
        html_parts.append(
            "        html += `<h4><a href='${e.url}' target='_blank'>${e.title}</a></h4>`;"
        )
        html_parts.append("      } else {")
        html_parts.append("        html += `<h4>${e.title}</h4>`;")
        html_parts.append("      }")
        html_parts.append("      html += `<div class='modal-event-info'>`;")
        html_parts.append("      if (e.date) {")
        html_parts.append("        html += `<span><strong>Data:</strong> ${e.date}</span>`;")
        html_parts.append("      }")
        html_parts.append("      if (e.time) {")
        html_parts.append("        html += `<span><strong>Hora:</strong> ${e.time}</span>`;")
        html_parts.append("      }")
        html_parts.append("      if (e.location) {")
        html_parts.append("        html += `<span><strong>Lloc:</strong> ${e.location}</span>`;")
        html_parts.append("      }")
        html_parts.append("      html += `</div>`;")
        html_parts.append(
            "      html += `<div class='modal-category' style='color:${color}'>${e.category}</div>`;"
        )
        html_parts.append("      html += `</div>`;")
        html_parts.append("    });")
        html_parts.append("    content.innerHTML = html;")
        html_parts.append("  }")
        html_parts.append("  ")
        html_parts.append("  modal.classList.add('active');")
        html_parts.append("}")
        html_parts.append("function closeModal() {")
        html_parts.append("  document.getElementById('eventModal').classList.remove('active');")
        html_parts.append("}")
        html_parts.append("</script>")

        html_parts.append("</div>")
        html_parts.append("</div>")

        html_parts.append("</body>")
        html_parts.append("</html>")

        return "\n".join(html_parts)

    def _add_categories(self, events_by_source: dict[str, list[Event]]) -> dict[str, list[Event]]:
        if not self.category_classifier:
            return events_by_source

        result = {}
        for source, events in events_by_source.items():
            categorized_events = []
            for event in events:
                event.event_category = self.category_classifier(event)
                categorized_events.append(event)
            result[source] = categorized_events
        return result

    def _get_css(self) -> str:
        return """
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               line-height: 1.6; color: #333; margin: 0 auto; padding: 20px; 
               background: #f5f5f5; }
        .container { display: flex; gap: 20px; max-width: 1600px; margin: 0 auto; }
        .sidebar { width: 280px; flex-shrink: 0; }
        .main-content { flex: 1; min-width: 0; }
        header { text-align: center; margin-bottom: 30px; padding: 20px; background: #2c3e50; color: white; border-radius: 8px; }
        header h1 { font-size: 2em; margin-bottom: 10px; }
        header .date { opacity: 0.8; }
        .category-index { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .category-index h2 { font-size: 1.2em; margin-bottom: 15px; color: #2c3e50; text-align: center; }
        .category-actions { display: flex; gap: 10px; margin-bottom: 15px; }
        .category-actions button { flex: 1; padding: 8px; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9em; }
        .btn-select { background: #3498db; color: white; }
        .btn-select:hover { background: #2980b9; }
        .btn-deselect { background: #e74c3c; color: white; }
        .btn-deselect:hover { background: #c0392b; }
        .category-index ul { list-style: none; }
        .category-index li { margin-bottom: 10px; }
        .category-index label { display: flex; align-items: center; gap: 10px; cursor: pointer; font-size: 1em; padding: 8px; border-radius: 4px; transition: background 0.2s; }
        .category-index label:hover { background: #f0f0f0; }
        .category-index input[type="checkbox"] { margin: 0; width: 18px; height: 18px; }
        .category-dot { width: 14px; height: 14px; border-radius: 3px; display: inline-block; }
        .calendar-container { display: flex; flex-direction: column; gap: 30px; align-items: center; width: 100%; }
        .calendar-wrapper { width: 100%; max-width: 100%; overflow-x: auto; }
        .calendar-inner { min-width: 700px; }
        .calendar-nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .calendar-nav h3 { margin: 0; font-size: 1.3em; color: #2c3e50; }
        .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; background: #ddd; border-radius: 8px; min-width: 700px; }
        .calendar-header { background: #2c3e50; color: white; padding: 12px 5px; text-align: center; font-weight: bold; font-size: 0.85em; }
        .calendar-day { background: white; min-height: 100px; padding: 5px; vertical-align: top; cursor: pointer; transition: background 0.2s; }
        .calendar-day:hover { background: #f8f8f8; }
        .calendar-day.other-month { background: #f5f5f5; color: #999; }
        .calendar-day.other-month .calendar-day-number { color: #999; }
        .calendar-day.today { background: #e8f4f8; }
        .calendar-day.today .calendar-day-number { background: #3498db; color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; }
        .calendar-day-number { font-weight: bold; margin-bottom: 5px; font-size: 0.9em; }
        .day-events { display: flex; flex-direction: column; gap: 2px; }
        .calendar-event { font-size: 0.65em; padding: 2px 4px; border-radius: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: white; }
        .calendar-event:hover { opacity: 0.9; }
        .calendar-event-more { font-size: 0.65em; padding: 2px 4px; background: #7f8c8d; color: white; border-radius: 2px; text-align: center; }
        .errors { background: #fee; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .errors h2 { color: #c00; }
        footer { text-align: center; padding: 20px; color: #666; clear: both; margin-top: 30px; }
        
        .calendar-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 1000; }
        .calendar-modal.active { display: flex; align-items: center; justify-content: center; }
        .calendar-modal-content { background: white; padding: 25px; border-radius: 12px; max-width: 600px; max-height: 80vh; overflow-y: auto; width: 90%; }
        .calendar-modal h3 { margin-bottom: 20px; color: #2c3e50; font-size: 1.4em; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
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

    def _generate_two_months_calendar(self, events: list[Event]) -> str:
        events_by_date: dict[datetime.date, list[Event]] = {}

        for event in events:
            dates = self._parse_event_dates(event.date)
            for d in dates:
                if d not in events_by_date:
                    events_by_date[d] = []
                events_by_date[d].append(event)

        today = datetime.now().date()
        current_month = today.replace(day=1)
        next_month = current_month.replace(day=28) + timedelta(days=4)
        next_month = next_month.replace(day=1)

        parts = []
        parts.append("<div class='calendar-wrapper'>")
        parts.append(self._render_month_calendar(current_month, events_by_date, today))
        parts.append("</div>")

        parts.append("<div class='calendar-wrapper'>")
        parts.append(self._render_month_calendar(next_month, events_by_date, today))
        parts.append("</div>")

        return "\n".join(parts)

    CATALAN_MONTHS = {
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

    def _render_month_calendar(
        self,
        month: datetime,
        events_by_date: dict[datetime.date, list[Event]],
        today: datetime.date,
    ) -> str:
        parts = []

        month_name = f"{self.CATALAN_MONTHS[month.month]} {month.year}"
        parts.append("<div class='calendar-nav'>")
        parts.append(f"<h3>{month_name}</h3>")
        parts.append("</div>")

        days = ["Dll", "Dm", "Dcx", "Dj", "Dv", "Ds", "Dg"]
        parts.append("<div class='calendar-inner'>")
        parts.append("<div class='calendar-grid'>")
        for day in days:
            parts.append(f"<div class='calendar-header'>{day}</div>")

        first_day = month.replace(day=1)
        last_day = (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        start_weekday = first_day.weekday()

        day_num = 1
        for i in range(42):
            if i < start_weekday:
                classes = "calendar-day other-month"
                parts.append(f"<div class='{classes}'></div>")
            elif day_num <= last_day.day:
                current_date = month.replace(day=day_num)
                classes = "calendar-day"
                if current_date == today:
                    classes += " today"

                day_events = events_by_date.get(current_date, [])
                day_str = current_date.strftime("%Y-%m-%d")

                parts.append(
                    f"<div class='{classes}' data-day='{day_str}' onclick=\"showDayEvents('{day_str}')\">"
                )
                parts.append(f"<div class='calendar-day-number'>{day_num}</div>")
                parts.append("<div class='day-events'>")

                for evt in day_events[:3]:
                    event_cat = getattr(evt, "event_category", "altres")
                    color = CATEGORY_COLORS.get(event_cat, "#3498db")
                    title_escaped = evt.title.replace("'", "\\'").replace('"', '\\"')
                    parts.append(
                        f"<div class='calendar-event' style='background:{color}' title='{title_escaped}'>{evt.title[:20]}</div>"
                    )

                if len(day_events) > 3:
                    parts.append(f"<div class='calendar-event-more'>+{len(day_events) - 3}</div>")

                parts.append("</div>")
                parts.append("</div>")
                day_num += 1
            else:
                classes = "calendar-day other-month"
                parts.append(f"<div class='{classes}'></div>")

        parts.append("</div>")
        parts.append("</div>")

        return "\n".join(parts)

    def _parse_event_dates(self, date_str: str) -> list[datetime.date]:
        dates = []
        if not date_str:
            return dates

        date_str = date_str.strip()

        for fmt in ["%d/%m/%Y", "%d/%m/%y"]:
            try:
                d = datetime.strptime(date_str, fmt).date()
                dates.append(d)
                return dates
            except ValueError:
                continue

        range_match = re.search(
            r"(?:Del|Des de)\s+(\d{1,2})/(\d{1,2})/(\d{2,4})\s+(?:al| fins)\s+(\d{1,2})/(\d{1,2})/(\d{2,4})",
            date_str,
            re.IGNORECASE,
        )
        if range_match:
            try:
                start_day, start_month, start_year = (
                    int(range_match.group(1)),
                    int(range_match.group(2)),
                    int(range_match.group(3)),
                )
                end_day, end_month, end_year = (
                    int(range_match.group(4)),
                    int(range_match.group(5)),
                    int(range_match.group(6)),
                )

                if start_year < 100:
                    start_year += 2000
                if end_year < 100:
                    end_year += 2000

                start_date = datetime(start_year, start_month, start_day).date()
                end_date = datetime(end_year, end_month, end_day).date()

                if (end_date - start_date).days > 31:
                    end_date = start_date + timedelta(days=31)

                current = start_date
                while current <= end_date:
                    dates.append(current)
                    current += timedelta(days=1)

                return dates
            except (ValueError, IndexError):
                pass

        month_match = re.match(r"(\d{2})/(\d{4})", date_str)
        if month_match:
            try:
                month_num = int(month_match.group(1))
                year = int(month_match.group(2))
                for day in range(1, 32):
                    try:
                        d = datetime(year, month_num, day).date()
                        dates.append(d)
                    except ValueError:
                        break
                return dates
            except ValueError:
                pass

        return dates
