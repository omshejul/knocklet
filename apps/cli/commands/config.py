"""CLI configuration management."""

import json
from datetime import date

import typer
from rich.console import Console
from rich.table import Table

from local_paths import local_data_dir

app = typer.Typer(no_args_is_help=True)
console = Console()

CONFIG_DIR = local_data_dir()
CONFIG_FILE = CONFIG_DIR / "cli_config.json"

# Defaults for all settings
DEFAULTS = {
    "rate_limits.calls_per_minute": 15,
    "rate_limits.daily_limit": 80,
    "browser.headless": True,
}
DEFAULT_DAILY_LIMIT = DEFAULTS["rate_limits.daily_limit"]
MIN_DAILY_LIMIT = 1
MAX_DAILY_LIMIT = 1000


def _load_config() -> dict:
    """Load config from disk, return empty dict if missing."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_config(config: dict):
    """Save config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_setting(key: str, default=None):
    """Get a setting by dotted key (e.g. 'rate_limits.daily_limit').

    Walks nested dicts. Returns default if not found.
    """
    config = _load_config()
    parts = key.split(".")
    node = config
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return default if default is not None else DEFAULTS.get(key)
    return node


def set_setting(key: str, value):
    """Set a setting by dotted key. Creates nested dicts as needed."""
    config = _load_config()
    parts = key.split(".")
    node = config
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value
    _save_config(config)


def set_daily_limit(value: int) -> None:
    """Validate and persist the daily LinkedIn request budget."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not MIN_DAILY_LIMIT <= value <= MAX_DAILY_LIMIT
    ):
        raise ValueError(
            f"Daily call limit must be between {MIN_DAILY_LIMIT} and "
            f"{MAX_DAILY_LIMIT}."
        )
    set_setting("rate_limits.daily_limit", value)


def get_rate_limit_usage() -> dict:
    """Return today's persisted request usage and configured budgets."""
    today = str(date.today())
    daily_calls = 0
    daily_file = CONFIG_DIR / "daily_calls.json"
    if daily_file.exists():
        try:
            data = json.loads(daily_file.read_text())
        except (json.JSONDecodeError, OSError) as error:
            raise RuntimeError(
                "LinkedIn request usage could not be read."
            ) from error
        if data.get("date") == today:
            count = data.get("count", 0)
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise RuntimeError("LinkedIn request usage is invalid.")
            daily_calls = count

    daily_limit = get_setting("rate_limits.daily_limit", DEFAULT_DAILY_LIMIT)
    calls_per_minute = get_setting("rate_limits.calls_per_minute", 15)
    return {
        "date": today,
        "daily_calls": daily_calls,
        "daily_limit": daily_limit,
        "default_daily_limit": DEFAULT_DAILY_LIMIT,
        "remaining": max(daily_limit - daily_calls, 0),
        "calls_per_minute": calls_per_minute,
    }


@app.command("show")
def show():
    """Show all CLI settings with current and default values."""
    config = _load_config()

    table = Table(title="CLI Settings")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Default", style="dim")

    for key, default_val in sorted(DEFAULTS.items()):
        current = get_setting(key)
        is_default = current == default_val
        val_style = "dim" if is_default else "bold green"
        table.add_row(key, f"[{val_style}]{current}[/{val_style}]", str(default_val))

    console.print(table)

    # Also show daily usage
    daily_file = CONFIG_DIR / "daily_calls.json"
    if daily_file.exists():
        try:
            data = json.loads(daily_file.read_text())
            limit = get_setting("rate_limits.daily_limit")
            count = data.get("count", 0)
            console.print(f"\n  Today's API calls: [bold]{count}[/bold] / {limit}")
        except (json.JSONDecodeError, OSError):
            pass


@app.command("set")
def set_value(
    key: str = typer.Argument(help="Setting key (e.g. rate_limits.daily_limit)"),
    value: str = typer.Argument(help="New value"),
):
    """Set a CLI setting.

    Examples:
      config set rate_limits.daily_limit 100
      config set rate_limits.calls_per_minute 20
      config set browser.headless true
    """
    if key not in DEFAULTS:
        console.print(f"[red]Unknown setting:[/red] {key}")
        console.print(f"Valid settings: {', '.join(sorted(DEFAULTS.keys()))}")
        raise typer.Exit(1)

    # Parse value to correct type based on default
    default_val = DEFAULTS[key]
    if isinstance(default_val, bool):
        parsed = value.lower() in ("true", "1", "yes")
    elif isinstance(default_val, int):
        try:
            parsed = int(value)
        except ValueError:
            console.print(f"[red]Expected integer, got:[/red] {value}")
            raise typer.Exit(1)
    else:
        parsed = value

    if key == "rate_limits.daily_limit":
        try:
            set_daily_limit(parsed)
        except ValueError as error:
            console.print(f"[red]{error}[/red]")
            raise typer.Exit(1)
    else:
        set_setting(key, parsed)
    console.print(f"[green]{key}[/green] = {parsed}")


@app.command("reset")
def reset():
    """Reset all settings to defaults."""
    _save_config({})
    console.print("[green]All settings reset to defaults.[/green]")
