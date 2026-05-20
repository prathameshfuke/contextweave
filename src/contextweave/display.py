from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from rich.console import Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

PRIMARY = "bright_magenta"
SUCCESS = "bright_green"
WARNING = "yellow"
ERROR = "bright_red"
MUTED = "bright_black"
DATA = "bright_cyan"
AGENT = "bright_blue"


def _status_dot(online: bool) -> Text:
    return Text("●", style=SUCCESS if online else ERROR)


def draw_projects_table(projects: list[tuple[str, str]]) -> Table:
    table = Table(title="ContextWeave Projects", expand=True)
    table.add_column("Slug", style=DATA, no_wrap=True)
    table.add_column("Description", style=MUTED)
    for slug, description in projects:
        table.add_row(slug, description or "")
    return table


def draw_status_dashboard(
    project_slug: str,
    last_session: dict[str, Any] | None,
    handoff: dict[str, Any] | None,
    open_questions: int,
    notes_indexed: int,
    sessions_7d: int,
    web_captures: int,
    obsidian_online: bool,
    ollama_online: bool,
) -> Panel:
    table = Table.grid(expand=True)
    table.add_column(ratio=1)
    table.add_column(justify="right", ratio=1)

    left = Table.grid(padding=(0, 1))
    left.add_row(Text("LAST SESSION", style=PRIMARY, justify="left"))
    if last_session:
        left.add_row("Agent", Text(str(last_session.get("agent", "unknown")), style=AGENT))
        started = str(last_session.get("started", ""))
        if started:
            try:
                started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                delta = datetime.now(started_dt.tzinfo) - started_dt if started_dt.tzinfo else datetime.now() - started_dt
                hours = max(1, round(delta.total_seconds() / 3600))
                age = f"{hours} hours ago" if hours > 1 else "1 hour ago"
            except Exception:
                age = started
            left.add_row("Updated", Text(age, style=MUTED))
        left.add_row("Feature", Text(str(last_session.get("feature", "unknown")), style=DATA))
        left.add_row("Status", Text(str(last_session.get("status", "unknown")), style=SUCCESS))
    else:
        left.add_row(Text("No sessions yet", style=MUTED))

    right = Table.grid(padding=(0, 1))
    right.add_row(Text("NEXT STEP", style=PRIMARY, justify="left"))
    right.add_row(Text(str(handoff.get("next_task", "None") if handoff else "None"), style=DATA))

    stats = Table.grid(expand=True)
    stats.add_column(ratio=1)
    stats.add_column(justify="right", ratio=1)
    stats.add_row(Text(f"OPEN QUESTIONS  {open_questions}", style=WARNING), Text(f"NOTES INDEXED  {notes_indexed}", style=DATA))
    stats.add_row(Text(f"SESSIONS (7d)   {sessions_7d}", style=AGENT), Text(f"WEB CAPTURES   {web_captures}", style=DATA))

    health = Table.grid(expand=True)
    health.add_column(ratio=1)
    health.add_column(ratio=1)
    health.add_row(
        Text.assemble("Obsidian API  ", _status_dot(obsidian_online), " ", "online" if obsidian_online else "offline", style=SUCCESS if obsidian_online else ERROR),
        Text.assemble("Ollama  ", _status_dot(ollama_online), " ", "online" if ollama_online else "offline", style=SUCCESS if ollama_online else ERROR),
    )

    outer = Table.grid(expand=True)
    outer.add_row(left, right)
    outer.add_row(stats)
    outer.add_row(health)

    return Panel(outer, title=f"ContextWeave — {project_slug}", border_style=PRIMARY, padding=(1, 2))


def draw_doctor(checks: Iterable[tuple[bool, str, str, str]], passed: int, total: int) -> Panel:
    table = Table.grid(expand=True)
    table.add_column(justify="center", width=2)
    table.add_column(ratio=2)
    table.add_column(ratio=1)
    table.add_column(ratio=2)

    for ok, label, target, detail in checks:
        marker = Text("●" if ok else "✗", style=SUCCESS if ok else ERROR)
        table.add_row(marker, Text(label, style="bold"), Text(target, style=DATA), Text(detail, style=MUTED if ok else WARNING))

    footer = Text(f"{passed} / {total} checks passed", style=SUCCESS if passed == total else WARNING)
    return Panel(Group(Text("Checking ContextWeave setup...", style=PRIMARY), table, footer), border_style=PRIMARY, title="ContextWeave Doctor")


def draw_brief_header(project_slug: str) -> Panel:
    today = datetime.now().strftime("%Y-%m-%d")
    return Panel(
        Text.assemble(("ContextWeave Brief", PRIMARY), "\n", (project_slug, DATA), " · ", (today, MUTED)),
        border_style=PRIMARY,
        padding=(1, 2),
    )


def draw_markdown(markdown_text: str) -> Markdown:
    return Markdown(markdown_text)


def draw_handoff_panel(handoff: dict[str, Any]) -> Panel:
    body = Table.grid(padding=(0, 1))
    body.add_column(ratio=1)
    body.add_column(ratio=2)
    created = str(handoff.get("created", "unknown"))
    try:
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        delta = datetime.now(created_dt.tzinfo) - created_dt if created_dt.tzinfo else datetime.now() - created_dt
        hours = max(1, round(delta.total_seconds() / 3600))
        left_off = f"{hours} hours ago" if hours > 1 else "1 hour ago"
    except Exception:
        left_off = created
    body.add_row("Feature", Text(str(handoff.get("feature", "unknown")), style=DATA))
    body.add_row("Left off", Text(left_off, style=MUTED))
    body.add_row("", "")
    body.add_row("Next step", Text(str(handoff.get("next_task", "None")), style=SUCCESS))
    return Panel(body, title=f"Handoff from {handoff.get('from_agent', 'unknown')}", border_style=AGENT)


def draw_diff_header(project_slug: str, session_a: str, session_b: str) -> Panel:
    table = Table.grid(expand=True)
    table.add_column(ratio=1)
    table.add_column(ratio=1)
    table.add_row(Text(f"OLD: {session_a}", style=ERROR), Text(f"NEW: {session_b}", style=SUCCESS))
    return Panel(table, title=f"Context Diff — {project_slug}", border_style=PRIMARY)


def draw_watch_status(project_slug: str, last_indexed: Any, files_count: int, last_note: str = "") -> Panel:
    if isinstance(last_indexed, datetime):
        delta = datetime.now() - last_indexed.replace(tzinfo=None) if last_indexed.tzinfo else datetime.now() - last_indexed
        seconds = max(1, int(delta.total_seconds()))
        if seconds < 60:
            last_indexed_text = f"{seconds} seconds ago"
        else:
            minutes = max(1, round(seconds / 60))
            last_indexed_text = f"{minutes} minutes ago"
    else:
        last_indexed_text = str(last_indexed)

    row = Table.grid(expand=True)
    row.add_column(ratio=1)
    row.add_column(justify="right")
    row.add_row(
        Text.assemble(("Watching ", PRIMARY), (project_slug, DATA)),
        Text.assemble(("Last indexed: ", MUTED), (last_indexed_text, SUCCESS), ("  Files: ", MUTED), (str(files_count), DATA)),
    )
    if last_note:
        row.add_row(Text.assemble(("↻ ", PRIMARY), (last_note, MUTED)), "")
    return Panel(row, border_style=PRIMARY)


def create_watch_live(renderable, console):
    return Live(renderable, console=console, refresh_per_second=4, transient=False)
