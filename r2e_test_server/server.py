import sys
import json
import traceback
from io import StringIO

import rpyc
from rpyc.utils.server import ThreadPoolServer

from r2e_test_server.testing.r2e_testprogram import R2ETestProgram


class MyService(rpyc.Service):
    def __init__(self):
        pass

    def on_connect(self, conn):
        pass

    def on_disconnect(self, conn):
        pass

    def setup_repo(self, data: str):
        data = json.loads(data)
        self.repo_name: str = data["repo_name"]
        self.repo_path: str = data["repo_path"]

    def setup_function(self, data: str):
        data = json.loads(data)
        self.function_name: str = data["function_name"]
        self.file_path: str = data["file_path"]
        self.function_code: str = data["function_code"]

    def setup_test(self, data: str):
        data = json.loads(data)
        self.generated_tests: dict[str, str] = data["generated_tests"]

    def setup(self):
        try:
            # Capture the standard output and standard error
            output_buffer = StringIO()
            error_buffer = StringIO()
            sys.stdout = output_buffer
            sys.stderr = error_buffer

            # setup the test program
            self.r2e_test_program = R2ETestProgram(
                self.repo_name,
                self.repo_path,
                self.function_name,
                self.file_path,
                self.function_code,
            )

            # Restore the standard output and standard error and get the captured output
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
            output = output_buffer.getvalue().strip()
            error = error_buffer.getvalue().strip()

            return {"output": output, "error": error}

        except Exception as e:
            traceback_message = traceback.format_exc()
            return {"error": f"Error: {traceback_message}\n\nSmall Error: {repr(e)}"}

    def exposed_execute(self, command):
        command = command.strip()
        if command == "submit":
            pass
        else:
            pass


def main(port: int):
    server = ThreadPoolServer(MyService(), port=port)
    server.start()


if __name__ == "__main__":
    main(3006)
