import typer, rpyc, fire
from r2e_test_server.server import start_server

def retrieve_conn(host, port):
    return rpyc.connect(host, port)

class R2EServer:
    def start(self,
              repo_id: str,
              port: int = 3006, 
              repo_dir: str = '/repos',
              result_dir: str = '/results',
              verbose: bool = False):
        typer.echo(f"Starting R2E server on port {port}...")
        start_server(port=port, 
                     repo_id=repo_id,
                     repo_dir=repo_dir, 
                     result_dir=result_dir,
                     verbose=verbose)

    def stop(self,
             host: str = 'localhost',
             port: int = 3006):
        conn = retrieve_conn(host, port)
        conn.root.stop_server()
        conn.close()

def CLI():
    fire.Fire(R2EServer)

if __name__ == '__main__':
    CLI()
