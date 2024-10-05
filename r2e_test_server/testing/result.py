import unittest


class R2ETestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed_tests = []
        self.failed_tests = []
        self.errored_tests = []
        self.skipped_tests = []
        self.expected_failure_tests = []
        self.unexpected_success_tests = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed_tests.append(test)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.failed_tests.append(test)

    def addError(self, test, err):
        super().addError(test, err)
        self.errored_tests.append(test)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.skipped_tests.append((test, reason))

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.expected_failure_tests.append(test)

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.unexpected_success_tests.append(test)

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None and err[0] is not None:
            if issubclass(err[0], test.failureException):
                self.failed_tests.append(subtest)
            else:
                self.errored_tests.append(subtest)

    def get_stats(self):
        test_name = lambda t: (
            t._testMethodName
            if t._testMethodName != "runTest"
            else f"{t.test_case._testMethodName}.subTest"
        )

        return {
            # "tests_count": self.testsRun,
            "valid": len(self.failed_tests) == 0 and len(self.errored_tests) == 0,
            "passed_count": len(self.passed_tests),
            "passed_names": [test_name(test) for test in self.passed_tests],
            "failed_count": len(self.failed_tests),
            "failed_names": [test_name(test) for test in self.failed_tests],
            "errored_count": len(self.errored_tests),
            "errored_names": [test_name(test) for test in self.errored_tests],
            "skipped_count": len(self.skipped_tests),
            "expected_failures": len(self.expected_failure_tests),
            "unexpected_successes": len(self.unexpected_success_tests),
        }

    def get_error_list(self):
        def _init_error_entry(etype: str, test, err):
            return {
                "type": etype,
                "test": self.getDescription(test),
                "message": str(err),
            }

        all_errors = [_init_error_entry("ERROR", *err) for err in self.errors]
        all_failures = [_init_error_entry("FAIL", *fail) for fail in self.failures]
        return all_errors + all_failures


def merge_test_suite_stats(stats_per_suite):
    # NOTE: don't use this unless you are sure
    # about merging stats from different test suites
    merged_stats = {
        "passed_count": 0,
        "passed_names": [],
        "failed_count": 0,
        "failed_names": [],
        "errored_count": 0,
        "errored_names": [],
        "skipped_count": 0,
        "expected_failures": 0,
        "unexpected_successes": 0,
    }

    for stats in stats_per_suite:
        for stat_name in merged_stats:
            merged_stats[stat_name] += stats[stat_name]

    return merged_stats
