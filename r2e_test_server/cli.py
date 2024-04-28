import typer
from r2e_test_server.server import R2EService
from r2e_test_server.server import main as start_server


app = typer.Typer()


@app.command()
def start(
    port: int = typer.Option(3006, help="Port number to start the R2E server on.")
):
    """
    Starts the R2E server on the specified port.
    """
    typer.echo(f"Starting R2E server on port {port}...")
    start_server(port)


if __name__ == "__main__":
    app()
