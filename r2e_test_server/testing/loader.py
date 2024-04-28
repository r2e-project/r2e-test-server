from typing import Any
from unittest import TestLoader, TestSuite, TestCase

from r2e_test_server.testing.cleaner import R2ETestCleaner


class R2ETestLoader:

    @staticmethod
    def load_tests(
        test_cases: dict[str, str], funclass_names: list[str], nspace: dict[str, Any]
    ) -> tuple[dict[str, TestSuite], dict[str, Any]]:
        test_suites = {}

        for test_id, test_case in test_cases.items():
            test_suite = R2ETestLoader.load_test(test_case, funclass_names, nspace)
            test_suites[test_id] = test_suite

        return test_suites, nspace

    @staticmethod
    def load_test(
        test_case: str, funclass_names: list[str], nspace: dict[str, Any]
    ) -> TestSuite:

        for funclass_name in funclass_names:
            ref_name = f"reference_{funclass_name}"

            try:
                test_case = R2ETestCleaner.clean_test_case(
                    test_case, funclass_name, ref_name
                )
            except Exception as e:
                print("[ERROR] Could not load test case!")
                raise

        try:
            R2ETestLoader.add_test_to_namespace(test_case, nspace)

            test_suite, test_classes = R2ETestLoader.create_test_suite(nspace)
            R2ETestLoader.clean_namespace(nspace, test_classes)
        except Exception as e:
            print("[ERROR] Could not load test case!")
            raise
        return test_suite

    @staticmethod
    def add_test_to_namespace(test_case: str, nspace: dict[str, Any]):
        exec(test_case, nspace, nspace)

    @staticmethod
    def create_test_suite(nspace: dict[str, Any]) -> tuple[TestSuite, list[str]]:
        loader, test_suite = TestLoader(), TestSuite()
        test_classes = []

        for name, obj in nspace.items():
            if isinstance(obj, type) and issubclass(obj, TestCase):
                test_suite.addTest(loader.loadTestsFromTestCase(obj))
                test_classes.append(name)

        return test_suite, test_classes

    @staticmethod
    def clean_namespace(nspace: dict[str, Any], test_classes: list[str]):
        for name in test_classes:
            nspace.pop(name, None)
