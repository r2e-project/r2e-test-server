import sys
import json
import traceback
from threading import Thread, Event
from io import StringIO

import rpyc
from rpyc.utils.server import ThreadPoolServer

from r2e_test_server.testing.r2e_testprogram import R2ETestProgram


class CaptureOutput:
    def __init__(self, stdout=None, stderr=None):
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    def __enter__(self):
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.old_stdout.flush()
        self.old_stderr.flush()
        sys.stdout, sys.stderr = self._stdout, self._stderr

    def __exit__(self, exc_type, exc_value, traceback):
        self._stdout.flush()
        self._stderr.flush()
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr


@rpyc.service
class R2EService(rpyc.Service):
    def __init__(self):
        self.codegen_mode: bool = False

    def on_connect(self, conn):
        pass

    def on_disconnect(self, conn):
        pass

    @rpyc.exposed
    def stop_server(self):
        server_stop_event.set()

    @rpyc.exposed
    def setup_repo(self, data: str):
        data_dict = json.loads(data)
        self.repo_id: str = data_dict["repo_id"]
        self.repo_path: str = data_dict["repo_path"]

    @rpyc.exposed
    def setup_function(self, data: str):
        data_dict = json.loads(data)
        self.funclass_names: list[str] = data_dict["funclass_names"]
        self.file_path = data_dict["file_path"]

    @rpyc.exposed
    def setup_test(self, data: str):
        data_dict = json.loads(data)
        self.generated_tests: dict[str, str] = data_dict["generated_tests"]

    @rpyc.exposed
    def setup_codegen_mode(self):
        self.codegen_mode = True

    @rpyc.exposed
    def init(self):
        try:
            stdout_buffer = StringIO()
            stderr_buffer = StringIO()
            with CaptureOutput(stdout=stdout_buffer, stderr=stderr_buffer):
                self.r2e_test_program = R2ETestProgram(
                    self.repo_id,
                    self.repo_path,
                    self.funclass_names,
                    self.file_path,
                    self.generated_tests,
                    self.codegen_mode,
                )

            output = stdout_buffer.getvalue().strip()
            error = stderr_buffer.getvalue().strip()

            return {"output": output, "error": error}

        except Exception as e:
            traceback_message = traceback.format_exc()
            return {"error": f"Error: {traceback_message}\n\nSmall Error: {repr(e)}"}

    @rpyc.exposed
    def submit(self):
        stdout_buffer = StringIO()
        stderr_buffer = StringIO()
        try:
            with CaptureOutput(stdout=stdout_buffer, stderr=stderr_buffer):
                logs = self.r2e_test_program.submit()
                output = stdout_buffer.getvalue().strip()
                error = stderr_buffer.getvalue().strip()

                return {"output": output, "error": error, "logs": logs}

        except Exception as e:
            traceback_message = traceback.format_exc()
            return {"error": f"Error: {traceback_message}\n\nSmall Error: {repr(e)}"}

    @rpyc.exposed
    def execute(self, command: str):
        stdout_buffer = StringIO()
        stderr_buffer = StringIO()
        try:
            with CaptureOutput(stdout=stdout_buffer, stderr=stderr_buffer):
                self.r2e_test_program.compile_and_exec(command.strip())
                output = stdout_buffer.getvalue().strip()
                error = stderr_buffer.getvalue().strip()

                return {"output": output, "error": error}

        except Exception as e:
            traceback_message = traceback.format_exc()
            return {"error": f"Error: {traceback_message}\n\nSmall Error: {repr(e)}"}


server_stop_event = Event()


def start_server(port: int):
    server = ThreadPoolServer(R2EService(), port=port)

    # Run the server and wait for a stop event
    server_thread = Thread(target=server.start)
    server_thread.start()
    server_stop_event.wait()

    # Once received, close the server and join the thread
    server.close()
    server_thread.join()
    print("Server stopped")


if __name__ == "__main__":
    start_server(3006)
