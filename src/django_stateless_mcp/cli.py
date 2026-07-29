"""Console script for django_stateless_mcp."""

import typer
from rich.console import Console

from django_stateless_mcp import utils

app = typer.Typer()
console = Console()


@app.command()
def main() -> None:
    """Console script for django_stateless_mcp."""
    console.print("Replace this message by putting your code into django_stateless_mcp.cli.main")
    console.print("See Typer documentation at https://typer.tiangolo.com/")
    utils.do_something_useful()


if __name__ == "__main__":
    app()
