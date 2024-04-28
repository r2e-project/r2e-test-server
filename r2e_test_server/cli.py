import typer
import rpyc
import json
from r2e_test_server.server import R2EService
from r2e_test_server.server import start_server


app = typer.Typer(name="r2e-test-server")


@app.command()
def start(
    port: int = typer.Option(3006, help="Port number to start the R2E server on.")
):
    """
    Starts the R2E server on the specified port.
    """
    typer.echo(f"Starting R2E server on port {port}...")
    start_server(port)


@app.command()
def stop(host: str = typer.Option("localhost"), port: int = typer.Option(3006)):
    """
    Stops the R2E server.
    """
    typer.echo("Stopping R2E server...")
    conn = rpyc.connect(host, port)
    service = conn.root
    service.stop_server()
    conn.close()


if __name__ == "__main__":
    app()
