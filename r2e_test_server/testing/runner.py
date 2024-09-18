import unittest

from r2e_test_server.testing.result import R2ETestResult


class R2ETestRunner(unittest.TextTestRunner):
    resultclass = R2ETestResult

    def run(self, test):  # type: ignore
        result: R2ETestResult = super().run(test)  # type: ignore
        stats = result.get_stats()
        return result, stats

class LatencyTestRunner(unittest.TextTestRunner):
    resultclass = R2ETestResult

    def run(self, test):  # type: ignore
        result: R2ETestResult = super().run(test)  # type: ignore
        stats = result.get_stats()
        return result, stats

class MemoryTestRunner(unittest.TextTestRunner):
    resultclass = R2ETestResult

    def run(self, test):  # type: ignore
        result: R2ETestResult = super().run(test)  # type: ignore
        stats = result.get_stats()
        return result, stats
