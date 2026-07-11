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
@click.option("--code", default=None, help="TOTP or backup code (if MFA is enabled)")
def login(email: str, password: str, code: str | None):
    """Login to Nexus."""
    try:
        result = api.login(email, password, totp_code=code)
        console.print(f"[green]{result['detail']}[/green]")
    except APIError as e:
        # If the server requires a second factor, prompt for it and retry once.
        if e.status_code == 401 and "MFA code required" in str(e.detail):
            mfa_code = click.prompt("MFA code")
            try:
                result = api.login(email, password, totp_code=mfa_code)
                console.print(f"[green]{result['detail']}[/green]")
                return
            except APIError as e2:
                console.print(f"[red]{e2.detail}[/red]")
                sys.exit(1)
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
        console.print(f"[bold]MFA:[/bold] {'Enabled' if me.get('mfa_enabled') else 'Disabled'}")
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@auth.command()
@click.option("--device", type=int, default=None, help="Revoke a specific session by ID")
@click.option("--all", "all_sessions", is_flag=True, default=False, help="Revoke all sessions")
def logout(device: int | None, all_sessions: bool):
    """Logout — remove local tokens and optionally revoke server sessions."""
    from nexus.utils.client import TOKEN_FILE

    if device is not None:
        try:
            result = api.revoke_session(device)
            console.print(f"[green]{result['detail']}[/green]")
        except APIError as e:
            console.print(f"[red]{e.detail}[/red]")
    if all_sessions:
        try:
            result = api.revoke_all_sessions()
            console.print(f"[green]{result['detail']}[/green]")
        except APIError as e:
            console.print(f"[red]{e.detail}[/red]")

    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        console.print("[green]Logged out.[/green]")
    else:
        console.print("[yellow]Not logged in.[/yellow]")


@auth.command("sessions")
def list_auth_sessions():
    """List active login sessions."""
    if not api.logged_in():
        console.print("[yellow]Not logged in.[/yellow]")
        sys.exit(1)
    try:
        result = api.list_sessions()
        table = Table("ID", "IP", "User-Agent", "Last Used", "Current")
        for s in result.get("sessions", []):
            is_current = "★" if s.get("is_current") else ""
            table.add_row(
                str(s["id"]),
                s.get("ip_address", "") or "-",
                (s.get("user_agent", "") or "")[:50],
                s.get("last_used_at", ""),
                is_current,
            )
        console.print(table)
        console.print(f"Total: {result.get('total', 0)} session(s)")
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@auth.group("mfa")
def auth_mfa():
    """Multi-factor authentication (TOTP)."""
    pass


@auth_mfa.command("enable")
def mfa_enable():
    """Enable TOTP MFA: enroll, scan the QR, confirm a code, save backup codes."""
    if not api.logged_in():
        console.print("[yellow]Not logged in. Use 'nexus auth login' first.[/yellow]")
        sys.exit(1)
    try:
        enroll = api.mfa_enroll()
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)

    console.print("[bold]Add this account to your authenticator app:[/bold]")
    console.print(f"  Secret: [cyan]{enroll['secret']}[/cyan]")
    console.print(f"  URI:    {enroll['otpauth_uri']}")
    try:
        import qrcode

        qr = qrcode.QRCode(border=1)
        qr.add_data(enroll["otpauth_uri"])
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:  # noqa: BLE001 - QR is a convenience; secret/URI still shown
        pass

    code = click.prompt("Enter the 6-digit code from your app to confirm")
    try:
        result = api.mfa_verify(code)
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)

    console.print("[green]MFA enabled.[/green] Store these backup codes safely (shown once):")
    for c in result["backup_codes"]:
        console.print(f"  [yellow]{c}[/yellow]")


@auth_mfa.command("disable")
@click.option("--password", prompt=True, hide_input=True, help="Account password")
def mfa_disable(password: str):
    """Disable TOTP MFA (requires your account password)."""
    if not api.logged_in():
        console.print("[yellow]Not logged in.[/yellow]")
        sys.exit(1)
    try:
        result = api.mfa_disable(password)
        console.print(f"[green]{result['detail']}[/green]")
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


# ── Task ───────────────────────────────────────────────────────────────────


@cli.group()
def task():
    """Task management commands."""
    pass


@task.command("add")
@click.argument("title")
@click.option("--desc", help="Task description")
@click.option("--priority", type=int, default=0, help="Priority (0=normal, 1=high)")
@click.option("--due", help="Due date (natural language: 'tomorrow', 'next monday', etc.)")
@click.option("--recur", help="Recurrence rule (RRULE format: 'FREQ=WEEKLY;BYDAY=MO')")
def task_add(title: str, desc: str | None, priority: int, due: str | None, recur: str | None):
    """Create a new task."""
    if not api.logged_in():
        console.print("[red]Not logged in. Run 'nexus auth login' first.[/red]")
        sys.exit(1)
    try:
        t = api.create_task(
            title, description=desc, priority=priority, due_date=due, recurrence_rule=recur
        )
        parts = [
            f"[green]Created task #{t['id']}:[/green] {t['title']} (priority {t['priority']}, status: {t['status']})"
        ]
        if t.get("due_date"):
            parts.append(f"due {t['due_date'][:10]}")
        if t.get("recurrence_rule"):
            from nexus.utils.recurrence import rrule_description

            parts.append(f"recurring: {rrule_description(t['recurrence_rule'])}")
        console.print(" ".join(parts))
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
@click.option("--account-id", type=int, help="Account ID")
@click.option("--desc", help="Transaction description")
@click.option("--date", help="Transaction date (natural language)")
def finance_log(amount: float, vendor: str, category: str, account_id: int, desc: str, date: str):
    """Log a transaction."""
    if not api.logged_in():
        console.print("[red]Not logged in. Run 'nexus auth login' first.[/red]")
        sys.exit(1)
    try:
        tx = api.create_transaction(
            amount=amount,
            vendor=vendor,
            category=category,
            account_id=account_id,
            description=desc,
            date_str=date,
        )
        color = "red" if amount > 0 else "green"
        sign = "-" if amount > 0 else "+"
        amt = float(tx["amount"])
        console.print(
            f"[{color}]Logged:[/{color}] {tx['vendor']} "
            rf"[bold]{sign}\${amt:.2f}[/bold] "
            f"({tx.get('category') or 'uncategorized'})"
        )
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@finance.command("list")
@click.option("--category", help="Filter by category")
@click.option("--vendor", help="Filter by vendor")
@click.option("--month", help="Month filter (YYYY-MM)")
@click.option("--limit", type=int, default=20, help="Max results")
def finance_list(category: str, vendor: str, month: str, limit: int):
    """List transactions."""
    if not api.logged_in():
        console.print("[red]Not logged in. Run 'nexus auth login' first.[/red]")
        sys.exit(1)
    try:
        date_from = None
        date_to = None
        if month:
            date_from = f"{month}-01"
            # Calculate end of month
            from calendar import monthrange

            y, m = map(int, month.split("-"))
            _, last_day = monthrange(y, m)
            date_to = f"{month}-{last_day}"

        txs = api.list_transactions(
            category=category, vendor=vendor, date_from=date_from, date_to=date_to, limit=limit
        )

        if not txs:
            console.print("[dim]No transactions found.[/dim]")
            return

        table = Table(title=f"Transactions ({len(txs)})")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Date")
        table.add_column("Vendor", style="white")
        table.add_column("Amount", justify="right")
        table.add_column("Category")

        total = 0
        for tx in txs:
            amt = float(tx["amount"])
            total += amt
            color = "red" if amt > 0 else "green"
            sign = "-" if amt > 0 else "+"
            table.add_row(
                str(tx["id"]),
                tx["transaction_date"],
                tx.get("vendor") or "[dim]—[/dim]",
                rf"[{color}]{sign}\${abs(amt):.2f}[/{color}]",
                tx.get("category") or "[dim]—[/dim]",
            )

        console.print(table)
        console.print(rf"[bold]Total expenses:[/bold] \${total:.2f}")
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@finance.command("accounts")
def finance_accounts():
    """List all accounts."""
    if not api.logged_in():
        console.print("[red]Not logged in. Run 'nexus auth login' first.[/red]")
        sys.exit(1)
    try:
        accounts = api.list_accounts()
        if not accounts:
            console.print(
                "[dim]No accounts found. Create one with 'nexus finance add-account'[/dim]"
            )
            return
        table = Table(title="Accounts")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Type")
        table.add_column("Balance", justify="right")
        table.add_column("Institution")
        for a in accounts:
            bal = float(a["balance"])
            color = "green" if bal >= 0 else "red"
            table.add_row(
                str(a["id"]),
                a["name"],
                a["account_type"],
                rf"[{color}]\${bal:.2f}[/{color}]",
                a.get("institution") or "[dim]—[/dim]",
            )
        console.print(table)
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@finance.command("add-account")
@click.argument("name")
@click.argument("type")
@click.option("--institution", help="Bank/institution name")
@click.option("--balance", type=float, default=0, help="Initial balance")
def finance_add_account(name: str, type: str, institution: str, balance: float):
    """Add a new account."""
    if not api.logged_in():
        console.print("[red]Not logged in. Run 'nexus auth login' first.[/red]")
        sys.exit(1)
    try:
        acct = api.create_account(name, type, institution=institution, balance=balance)
        console.print(
            f"[green]Created account #{acct['id']}:[/green] {acct['name']} ({acct['account_type']})"
        )
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@finance.command("import")
@click.argument("filepath", type=click.Path(exists=True))
def finance_import(filepath: str):
    """Import transactions from a CSV file."""
    if not api.logged_in():
        console.print("[red]Not logged in. Run 'nexus auth login' first.[/red]")
        sys.exit(1)
    try:
        result = api.import_csv(filepath)
        console.print(f"[green]Imported:[/green] {result['imported']} transactions")
        if result.get("skipped"):
            console.print(f"[yellow]Skipped:[/yellow] {result['skipped']} (duplicates)")
        if result.get("errors"):
            console.print("[red]Errors:[/red]")
            for err in result["errors"]:
                console.print(f"  [dim]{err}[/dim]")
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@finance.command("upload")
@click.argument("filepath", type=click.Path(exists=True))
def finance_upload(filepath: str):
    """Upload a receipt image for OCR."""
    if not api.logged_in():
        console.print("[red]Not logged in.[/red]")
        sys.exit(1)
    try:
        import os

        import httpx

        token = api.get_access_token()
        base_url = os.environ.get("NEXUS_API_URL", "http://localhost:8000")
        with open(filepath, "rb") as f:
            resp = httpx.post(
                f"{base_url}/api/v1/finance/transactions/scan",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (filepath, f, "image/jpeg")},
                timeout=30,
            )
        if resp.status_code != 200:
            raise APIError(resp)

        data = resp.json()
        tx = data["transaction"]
        ocr = data["ocr"]
        pred = data["prediction"]

        console.print("[bold]OCR Result:[/bold]")
        console.print(f"  Raw text: {ocr['raw_text'][:200]}")
        console.print(f"  Confidence: {ocr['confidence']}")
        console.print(f"  Reliable: {'✓' if ocr['is_reliable'] else '✗'}")

        console.print("[bold]Extracted:[/bold]")
        console.print(f"  Vendor: {tx.get('vendor') or '—'}")
        console.print(f"  Amount: ${tx.get('amount', 0):.2f}")
        console.print(f"  Date: {tx.get('transaction_date')}")

        if pred.get("category"):
            console.print(f"  [green]Suggested category: {pred['category']}[/green]")
        else:
            console.print(
                "  [yellow]Category: uncertain (use 'nexus finance categorize TX_ID')[/yellow]"
            )

        console.print(f"  [dim]Transaction #{tx['id']} created[/dim]")
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@finance.command("categorize")
@click.argument("transaction_id", type=int)
@click.option("--category", help="Set category (omit to just predict)")
def finance_categorize(transaction_id: int, category: str):
    """Predict or correct a transaction's category."""
    if not api.logged_in():
        console.print("[red]Not logged in.[/red]")
        sys.exit(1)
    try:
        if category:
            resp = api._request(
                "POST",
                f"/api/v1/finance/transactions/{transaction_id}/correct-category",
                json_body={"category": category},
            )
            console.print(f"[green]Updated to '{category}'[/green]")
        else:
            resp = api._request(
                "POST", f"/api/v1/finance/transactions/{transaction_id}/predict-category"
            )
            data = resp.json()
            if data.get("category"):
                conf = data["confidence"]
                console.print(
                    f"Predicted: [green]{data['category']}[/green] (confidence: {conf:.2f})"
                )
                console.print(
                    f"To accept: [dim]nexus finance categorize {transaction_id} --category {data['category']}[/dim]"
                )
            else:
                console.print(
                    f"[yellow]Could not predict ({data.get('detail', 'low confidence')})[/yellow]"
                )
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


# ── Note ───────────────────────────────────────────────────────────────────


@cli.group()
def note():
    """Knowledge management commands."""
    pass


@note.command("create")
@click.argument("title")
@click.option("--content", "-c", prompt=True, help="Note body (markdown, supports [[links]])")
@click.option("--project-id", type=int, default=None, help="Research project ID")
@click.option("--tag", "tags", multiple=True, help="Tag (repeatable)")
def note_create(title: str, content: str, project_id: int | None, tags: tuple[str, ...]):
    """Create a new note."""
    if not api.logged_in():
        console.print("[yellow]Not logged in. Use 'nexus auth login' first.[/yellow]")
        sys.exit(1)
    try:
        result = api.create_note(title, content, project_id, list(tags) or None)
        embed_note = " (embedded)" if result.get("has_embedding") else " (full-text only)"
        console.print(f"[green]Created note #{result['id']}: {result['title']}[/green]{embed_note}")
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@note.command("search")
@click.argument("query")
@click.option("--limit", type=int, default=10, help="Max results")
def note_search(query: str, limit: int):
    """Search notes (semantic when embeddings available, else full-text)."""
    if not api.logged_in():
        console.print("[yellow]Not logged in. Use 'nexus auth login' first.[/yellow]")
        sys.exit(1)
    try:
        results = api.search_notes(query, limit)
        if not results:
            console.print("[yellow]No matching notes.[/yellow]")
            return
        table = Table("ID", "Title", "Score", "Method", "Snippet")
        for r in results:
            table.add_row(
                str(r["id"]),
                r["title"],
                f"{r['score']:.3f}",
                r["method"],
                (r["snippet"] or "").replace("\n", " ")[:60],
            )
        console.print(table)
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@note.command("list")
@click.option("--project-id", type=int, default=None, help="Filter by project ID")
@click.option("--tag", default=None, help="Filter by tag")
def note_list(project_id: int | None, tag: str | None):
    """List notes."""
    if not api.logged_in():
        console.print("[yellow]Not logged in. Use 'nexus auth login' first.[/yellow]")
        sys.exit(1)
    try:
        notes = api.list_notes(project_id, tag)
        if not notes:
            console.print("[yellow]No notes.[/yellow]")
            return
        table = Table("ID", "Title", "Tags", "Embedded")
        for n in notes:
            table.add_row(
                str(n["id"]),
                n["title"],
                ", ".join(n.get("tags") or []),
                "✓" if n.get("has_embedding") else "",
            )
        console.print(table)
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@note.command("export")
@click.argument("note_id", type=int)
@click.option("--format", "fmt", default="md", help="Export format: md, pdf, html, docx")
def note_export(note_id: int, fmt: str):
    """Export a note to a file."""
    if not api.logged_in():
        console.print("[yellow]Not logged in.[/yellow]")
        sys.exit(1)
    try:
        result = api.export_note(note_id, fmt)
        console.print(f"[green]Exported to {result['file']}[/green]")
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


# ── Research ───────────────────────────────────────────────────────────


@cli.group()
def research():
    """Research and discovery commands."""
    pass


@research.command("papers")
@click.argument("query")
@click.option("--limit", type=int, default=10, help="Max results")
def research_papers(query: str, limit: int):
    """Search arXiv for academic papers."""
    if not api.logged_in():
        console.print("[yellow]Not logged in.[/yellow]")
        sys.exit(1)
    try:
        papers = api.search_papers(query, limit)
        if not papers:
            console.print("[yellow]No papers found.[/yellow]")
            return
        table = Table("#", "Title", "Authors", "Cred", "Year")
        for i, p in enumerate(papers, 1):
            authors = ", ".join(p.get("authors", [])[:2])
            if len(p.get("authors", [])) > 2:
                authors += " et al."
            year = p.get("published", "")[:4]
            table.add_row(
                str(i),
                p["title"],
                authors,
                f"{p.get('credibility', 0):.1f}",
                year,
            )
        console.print(table)
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


@research.command("plan")
@click.argument("topic")
def research_plan(topic: str):
    """Generate research questions for a topic (LLM-powered)."""
    if not api.logged_in():
        console.print("[yellow]Not logged in.[/yellow]")
        sys.exit(1)
    try:
        data = api.research_plan(topic)
        console.print(f"[bold]Research Plan: {data['topic']}[/bold]")
        for i, q in enumerate(data["questions"], 1):
            console.print(f"  {i}. {q}")
    except APIError as e:
        console.print(f"[red]{e.detail}[/red]")
        sys.exit(1)


# ── System ─────────────────────────────────────────────────────────────────


@cli.command()
def status():
    """Show Nexus system status."""
    from nexus.config import get_settings

    settings = get_settings()
    console.print("[bold]Nexus System Status[/bold]")
    console.print(f"  API:     [green]{settings.database_url}[/green]")
    console.print(
        f"  Auth:    [green]{'Logged in' if api.logged_in() else 'Not logged in'}[/green]"
    )
    console.print(f"  Env:     {settings.nexus_env}")
    console.print(f"  Debug:   {settings.nexus_debug}")
    console.print("  Version: 0.1.0")


if __name__ == "__main__":
    cli()
