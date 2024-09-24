import sys
from io import StringIO
from pathlib import Path

class CaptureOutput:

    def __enter__(self):
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.old_stdout.flush()
        self.old_stderr.flush()
        stdout, stderr = StringIO(), StringIO()
        sys.stdout, sys.stderr = stdout, stderr
        return stdout, stderr

    def __exit__(self, _, __, ___):
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr

def ensure(file: str|Path):
    Path(file).parent.mkdir(exist_ok=True, parents=True)
    return file
