"""`docent backup` / `docent restore` commands (extracted from cli.py).

Registered onto the root Typer app by ``register_backup_commands`` — cli.py
stays the single place that owns the app object; this module owns everything
Drive-backup-specific.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.panel import Panel

from docent.ui import get_console


def backup_command(
    local_only: bool = typer.Option(
        False, "--local-only", help="Create zip but skip Drive upload."
    ),
    out: Path = typer.Option(
        None, "--out", "-o", help="Save zip to this path (implies --local-only)."
    ),
    keep: int = typer.Option(
        10, "--keep", help="Number of Drive backups to retain (older ones deleted)."
    ),
    setup: bool = typer.Option(
        False, "--setup", help="Show Google Drive credential setup instructions."
    ),
) -> None:
    """Create a timestamped zip of Docent config, queue data, and research outputs
    then upload it to a 'Docent Backups' folder in Google Drive.

    Files larger than 100 MB are automatically excluded. Pass --local-only to
    skip Drive upload and keep the zip on disk instead.
    """
    console = get_console()

    if setup:
        console.print(
            Panel(
                "[bold]Google Drive Backup — Setup[/]\n\n"
                "1. Go to [cyan]https://console.cloud.google.com/[/]\n"
                "2. Create (or select) a project → Enable the [bold]Google Drive API[/]\n"
                "3. Credentials → Create Credentials → [bold]OAuth client ID[/]\n"
                "   • Application type: [bold]Desktop app[/]  • Name: Docent\n"
                "4. Download the JSON file and save it as:\n"
                "   [green]~/.docent/drive_credentials.json[/]\n\n"
                "Then run [cyan]docent backup[/] — a browser window will open for\n"
                "sign-in on the first run; the token is cached for future runs.",
                title="Setup",
                border_style="green",
            )
        )
        return

    import tempfile

    from docent.bundled_plugins.backup.manager import archive_name, create_archive

    local_only = local_only or (out is not None)

    # ── Build the archive ─────────────────────────────────────────────────────
    dest = Path(out) if out else Path(tempfile.mkdtemp()) / archive_name()
    fname = dest.name

    with console.status("[green]Creating backup archive…[/]"):
        manifest = create_archive(dest)

    n_in = manifest["files_included"]
    n_ex = manifest["files_excluded"]
    size_mb = manifest["archive_size_mb"]

    console.print(f"[green]✓[/] Archive: [cyan]{dest}[/]")
    console.print(f"  {n_in} files included · {size_mb} MB")
    if n_ex:
        console.print(
            f"  [yellow]Warning:[/] {n_ex} file(s) excluded (>100 MB). "
            "Use an external drive for raw data."
        )

    if local_only:
        return

    # ── Upload to Drive ───────────────────────────────────────────────────────
    from docent.bundled_plugins.backup.drive_client import (
        credentials_file_exists,
        get_or_create_backup_folder,
        get_service,
        trim_old_backups,
        upload_backup,
    )

    if not credentials_file_exists():
        console.print(
            "\n[yellow]Google Drive credentials not found.[/]\n"
            "Run [cyan]docent backup --setup[/] for setup instructions.\n"
            "Your local archive is saved at:\n  [green]{dest}[/]"
        )
        return

    try:
        with console.status("[green]Connecting to Google Drive…[/]"):
            service = get_service()
            folder_id = get_or_create_backup_folder(service)

        with console.status(f"[green]Uploading {fname} ({size_mb} MB)…[/]"):
            file_id = upload_backup(service, dest, folder_id, fname)

        console.print(f"[green]✓[/] Uploaded to Google Drive — file ID: [dim]{file_id}[/]")

        deleted = trim_old_backups(service, folder_id, keep)
        if deleted:
            console.print(
                f"  [dim]{deleted} old backup(s) removed (keeping {keep} most recent).[/]"
            )

    except Exception as exc:
        console.print(f"[red]Drive upload failed:[/] {exc}")
        console.print(f"Local archive kept at: [cyan]{dest}[/]")
        raise typer.Exit(1)
    finally:
        # Delete the temp zip if we didn't use --out
        if out is None and dest.exists():
            dest.unlink(missing_ok=True)


def restore_command(
    list_backups: bool = typer.Option(False, "--list", "-l", help="List available Drive backups."),
    backup_id: str = typer.Option("", "--id", help="Drive file ID to restore."),
    local: Path = typer.Option(None, "--local", help="Restore from a local zip file."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Restore Docent config and queue data from a backup.

    Use --list to see available Drive backups, --id to pick one by ID,
    or --local to restore from a local zip file.
    """
    console = get_console()
    import tempfile

    # ── Local restore ─────────────────────────────────────────────────────────
    if local:
        archive = Path(local)
        if not archive.exists():
            console.print(f"[red]File not found:[/] {archive}")
            raise typer.Exit(1)
        _do_restore(console, archive, yes)
        return

    # ── Drive operations ──────────────────────────────────────────────────────
    from docent.bundled_plugins.backup.drive_client import (
        credentials_file_exists,
        download_backup,
        get_or_create_backup_folder,
        get_service,
    )
    from docent.bundled_plugins.backup.drive_client import (
        list_backups as _list,
    )

    if not credentials_file_exists():
        console.print(
            "[yellow]Google Drive credentials not found.[/]\n"
            "Run [cyan]docent backup --setup[/] for setup instructions."
        )
        raise typer.Exit(1)

    with console.status("[green]Connecting to Google Drive…[/]"):
        service = get_service()
        folder_id = get_or_create_backup_folder(service)
        backups = _list(service, folder_id)

    if not backups:
        console.print("[yellow]No backups found in Google Drive.[/]")
        return

    # ── List ──────────────────────────────────────────────────────────────────
    if list_backups or not backup_id:
        from rich.table import Table

        t = Table(title="Docent Backups (Google Drive)", show_lines=True)
        t.add_column("#", style="dim", width=3)
        t.add_column("Name")
        t.add_column("Size", justify="right")
        t.add_column("Created")
        t.add_column("ID", style="dim")
        for i, b in enumerate(backups, 1):
            size = int(b.get("size", 0))
            size_str = f"{size / 1_048_576:.1f} MB" if size else "—"
            t.add_row(str(i), b["name"], size_str, b.get("createdTime", "")[:10], b["id"])
        console.print(t)
        if list_backups:
            console.print("[dim]Use --id <ID> to restore a specific backup.[/]")
            return
        # Default: offer to restore the latest
        backup_id = backups[0]["id"]
        bname = backups[0]["name"]
        console.print(f"\nLatest backup: [cyan]{bname}[/]")

    # Find the chosen backup
    chosen = next((b for b in backups if b["id"] == backup_id), None)
    if not chosen:
        console.print(f"[red]Backup ID not found:[/] {backup_id}")
        raise typer.Exit(1)

    # ── Download + restore ────────────────────────────────────────────────────
    tmp = Path(tempfile.mkdtemp()) / chosen["name"]
    try:
        with console.status(f"[green]Downloading {chosen['name']}…[/]"):
            download_backup(service, chosen["id"], tmp)
        _do_restore(console, tmp, yes)
    finally:
        tmp.unlink(missing_ok=True)


def _do_restore(console, archive: Path, yes: bool) -> None:
    """Shared restore logic used by both Drive and local restore paths."""
    from docent.bundled_plugins.backup.manager import read_manifest, restore_archive

    manifest = read_manifest(archive)
    ts = manifest.get("timestamp", "unknown")[:19].replace("T", " ")
    version = manifest.get("docent_version", "?")
    n_files = manifest.get("files_included", "?")

    console.print(
        f"\n[bold]Backup details[/]\n"
        f"  Created:   {ts}\n"
        f"  Version:   {version}\n"
        f"  Files:     {n_files}\n"
    )

    if not yes:
        confirm = typer.confirm("This will overwrite your current Docent state. Continue?")
        if not confirm:
            console.print("[yellow]Restore cancelled.[/]")
            raise typer.Exit(0)

    with console.status("[green]Restoring…[/]"):
        restore_archive(archive)

    console.print("[green]✓ Restore complete.[/] Restart 'docent ui' to apply changes.")


def register_backup_commands(app: typer.Typer) -> None:
    """Attach `docent backup` / `docent restore` to the root app."""
    app.command("backup", help="Backup Docent state to Google Drive (or a local zip).")(
        backup_command
    )
    app.command("restore", help="Restore Docent state from a Google Drive backup.")(restore_command)
