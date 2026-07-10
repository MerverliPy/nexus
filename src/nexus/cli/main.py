"""CLI entry point — Click commands for Nexus."""

import sys

import click
from rich.console import Console
from rich.table import Table

from nexus.utils import client as api
from nexus.utils.client import APIError

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Nexus Personal AI System CLI."""
    pass


# ── Auth ───────────────────────────────────────────────────────────────────


@cli.group()
def auth():
    """Authentication commands."""
    pass


@auth.command()
@click.option("--email", prompt=True, help="Email address")
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="Password",
)
def register(email: str, password: str):
    """Register a new user account."""
    try:
        result = api.register(email, password)
        console.print(f"[green]{result['detail']}[/green]")
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@auth.command()
@click.option("--email", prompt=True, help="Email address")
@click.option("--password", prompt=True, hide_input=True, help="Password")
def login(email: str, password: str):
    """Login to Nexus."""
    try:
        result = api.login(email, password)
        console.print(f"[green]{result['detail']}[/green]")
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@auth.command()
def whoami():
    """Show current user info."""
    if not api.logged_in():
        console.print("[yellow]Not logged in. Use 'nexus auth login' first.[/yellow]")
        return
    try:
        me = api.get_me()
        console.print(f"[bold]User:[/bold] {me['email']}")
        console.print(f"[bold]Active:[/bold] {'Yes' if me['is_active'] else 'No'}")
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@auth.command()
def logout():
    """Logout by removing stored tokens."""
    from nexus.utils.client import TOKEN_FILE

    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        console.print("[green]Logged out.[/green]")
    else:
        console.print("[yellow]Not logged in.[/yellow]")


# ── Task ───────────────────────────────────────────────────────────────────


@cli.group()
def task():
    """Task management commands."""
    pass


@task.command("add")
@click.argument("title")
@click.option("--desc", help="Task description")
@click.option(
    "--priority", type=int, default=0, help="Priority (0=normal, 1=high)"
)
def task_add(title: str, desc: str | None, priority: int):
    """Create a new task."""
    if not api.logged_in():
        console.print("[red]Not logged in. Run 'nexus auth login' first.[/red]")
        sys.exit(1)
    try:
        t = api.create_task(title, description=desc, priority=priority)
        console.print(
            f"[green]Created task #{t['id']}:[/green] {t['title']} "
            f"(priority {t['priority']}, status: {t['status']})"
        )
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@task.command("list")
@click.option(
    "--status",
    type=click.Choice(["pending", "in_progress", "completed", "cancelled"]),
    default=None,
    help="Filter by status",
)
def task_list(status: str | None):
    """List tasks."""
    if not api.logged_in():
        console.print("[red]Not logged in. Run 'nexus auth login' first.[/red]")
        sys.exit(1)
    try:
        tasks = api.list_tasks(status=status)
        if not tasks:
            console.print("[yellow]No tasks found.[/yellow]")
            return

        table = Table(title=f"Tasks{' (' + status + ')' if status else ''}")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="white")
        table.add_column("Status", style="yellow")
        table.add_column("Priority", justify="right")
        table.add_column("Created", style="dim")

        for t in tasks:
            table.add_row(
                str(t["id"]),
                t["title"],
                t["status"],
                str(t["priority"]),
                t["created_at"][:10],
            )

        console.print(table)
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


# ── Finance ────────────────────────────────────────────────────────────────


@cli.group()
def finance():
    """Financial management commands."""
    pass


@finance.command("log")
@click.argument("amount", type=float)
@click.argument("vendor")
@click.option("--category", help="Transaction category")
@click.option("--account", help="Account name")
def finance_log(amount: float, vendor: str, category: str, account: str):
    """Log a transaction."""
    console.print("[yellow]TODO: Log transaction (coming in Phase 2)[/yellow]")


@finance.command("list")
@click.option("--month", help="Month (YYYY-MM)")
def finance_list(month: str):
    """List transactions."""
    console.print("[yellow]TODO: List transactions (coming in Phase 2)[/yellow]")


# ── Note ───────────────────────────────────────────────────────────────────


@cli.group()
def note():
    """Knowledge management commands."""
    pass


@note.command("create")
@click.argument("title")
@click.option("--project", help="Research project name")
def note_create(title: str, project: str):
    """Create a new note."""
    console.print("[yellow]TODO: Create note (coming in Phase 4)[/yellow]")


@note.command("search")
@click.argument("query")
def note_search(query: str):
    """Search notes semantically."""
    console.print("[yellow]TODO: Search notes (coming in Phase 4)[/yellow]")


# ── System ─────────────────────────────────────────────────────────────────


@cli.command()
def status():
    """Show Nexus system status."""
    from nexus.config import get_settings

    settings = get_settings()
    console.print("[bold]Nexus System Status[/bold]")
    console.print(f"  API:     [green]{settings.database_url}[/green]")
    console.print(f"  Auth:    [green]{'Logged in' if api.logged_in() else 'Not logged in'}[/green]")
    console.print(f"  Env:     {settings.nexus_env}")
    console.print(f"  Debug:   {settings.nexus_debug}")
    console.print(f"  Version: 0.1.0")


if __name__ == "__main__":
    cli()
