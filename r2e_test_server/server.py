import sys
import json
import traceback
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


class R2EService(rpyc.Service):
    def __init__(self):
        pass

    def on_connect(self, conn):
        pass

    def on_disconnect(self, conn):
        pass

    def setup_repo(self, data: str):
        data_dict = json.loads(data)
        self.repo_name: str = data_dict["repo_name"]
        self.repo_path: str = data_dict["repo_path"]

    def setup_function(self, data: str):
        data_dict = json.loads(data)
        self.function_name: str = data_dict["function_name"]
        self.file_path: str = data_dict["file_path"]
        self.function_code: str = data_dict["function_code"]

    def setup_test(self, data: str):
        data_dict = json.loads(data)
        self.generated_tests: dict[str, str] = data_dict["generated_tests"]

    def setup(self):
        try:
            stdout_buffer = StringIO()
            stderr_buffer = StringIO()
            with CaptureOutput(stdout=stdout_buffer, stderr=stderr_buffer):
                self.r2e_test_program = R2ETestProgram(
                    self.repo_name,
                    self.repo_path,
                    self.function_name,
                    self.file_path,
                    self.function_code,
                    self.generated_tests,
                )

            output = stdout_buffer.getvalue().strip()
            error = stderr_buffer.getvalue().strip()

            return {"output": output, "error": error}

        except Exception as e:
            traceback_message = traceback.format_exc()
            return {"error": f"Error: {traceback_message}\n\nSmall Error: {repr(e)}"}

    def exposed_execute(self, command: str):
        stdout_buffer = StringIO()
        stderr_buffer = StringIO()
        try:
            with CaptureOutput(stdout=stdout_buffer, stderr=stderr_buffer):
                command = command.strip()
                if command == "submit":
                    self.r2e_test_program.submit()
                    logs = self.r2e_test_program.submit()

                    output = stdout_buffer.getvalue().strip()
                    error = stderr_buffer.getvalue().strip()

                    return {"output": output, "error": error, "logs": logs}
                else:
                    self.r2e_test_program.compile_and_exec(command)

                    output = stdout_buffer.getvalue().strip()
                    error = stderr_buffer.getvalue().strip()

                    return {"output": output, "error": error}

        except Exception as e:
            traceback_message = traceback.format_exc()
            return {"error": f"Error: {traceback_message}\n\nSmall Error: {repr(e)}"}


def main(port: int):
    server = ThreadPoolServer(R2EService(), port=port)
    server.start()


if __name__ == "__main__":
    main(3006)
