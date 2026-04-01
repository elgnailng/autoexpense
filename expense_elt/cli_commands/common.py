from rich.console import Console
from rich.panel import Panel

console = Console()


def header(title: str) -> None:
    console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))


def success(message: str) -> None:
    console.print(f"[bold green]OK[/bold green] {message}")


def error(message: str) -> None:
    console.print(f"[bold red]ERR[/bold red] {message}")
