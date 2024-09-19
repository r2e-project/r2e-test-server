import unittest

from r2e_test_server.testing.result import R2ETestResult
from r2e_test_server.testing.util import CaptureOutput


class R2ETestRunner(unittest.TextTestRunner):
    resultclass = R2ETestResult

    def run(self, test):  # type: ignore
        with CaptureOutput() as (stdout, stderr):
            result: R2ETestResult = super().run(test)  # type: ignore
            stats = {**result.get_stats(),
                     'stdout': stdout.getvalue().strip(),
                     'stderr': stderr.getvalue().strip()}
            return result, stats
