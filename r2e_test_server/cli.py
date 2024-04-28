import typer
import rpyc
import json
from r2e_test_server.server import R2EService
from r2e_test_server.server import start_server


app = typer.Typer(name="r2e-test-server")


def send_command_to_service(
    method_name: str, args: list = [], host: str = "localhost", port: int = 3006
):
    conn = rpyc.connect(host, port)
    service = conn.root
    method = getattr(service, method_name)
    response = method(*args)
    print(response)
    conn.close()


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


@app.command()
def setup_repo(
    repo_name: str,
    repo_path: str,
    host: str = typer.Option("localhost"),
    port: int = typer.Option(3006),
):
    """
    Setup repository configuration.
    """
    data = json.dumps({"repo_name": repo_name, "repo_path": repo_path})
    send_command_to_service("setup_repo", [data], host, port)


@app.command()
def setup_function(
    funclass_names: str,
    file_path: str,
    host: str = typer.Option("localhost"),
    port: int = typer.Option(3006),
):
    """
    Setup function/class names and file path.
    """
    data = json.dumps(
        {"funclass_names": funclass_names.split(","), "file_path": file_path}
    )
    send_command_to_service("setup_function", [data], host, port)


@app.command()
def setup_tests(
    generated_tests: str,
    host: str = typer.Option("localhost"),
    port: int = typer.Option(3006),
):
    """
    Setup generated tests.
    """
    data = json.dumps({"generated_tests": json.loads(generated_tests)})
    send_command_to_service("setup_test", [data], host, port)


@app.command()
def init(host: str = typer.Option("localhost"), port: int = typer.Option(3006)):
    """
    Initialize the test program.
    """
    send_command_to_service("init", [], host, port)


@app.command()
def execute(
    code: str, host: str = typer.Option("localhost"), port: int = typer.Option(3006)
):
    """
    Execute arbitrary <python code>.
    """
    send_command_to_service("execute", [code], host, port)


@app.command()
def submit(host: str = typer.Option("localhost"), port: int = typer.Option(3006)):
    """
    Submit the function/class to be tested.
    """
    send_command_to_service("submit", [], host, port)


if __name__ == "__main__":
    app()
