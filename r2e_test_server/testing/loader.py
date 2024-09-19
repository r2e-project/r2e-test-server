from typing import Any, Dict, List, Tuple
from unittest import TestLoader, TestSuite, TestCase

from r2e_test_server.testing.cleaner import R2ETestCleaner


class R2ETestLoader:

    @staticmethod
    def load_tests(
        test_classes: Dict[str, str], funclass_names: List[str], nspace: Dict[str, Any]
    ) -> Tuple[Dict[str, TestSuite], Dict[str, Any]]:
        """Load the test cases into test suites."""

        test_suites = {}

        for test_id, test_class in test_classes.items():
            test_suite = R2ETestLoader.load_test(test_class, funclass_names, nspace)
            test_suites[test_id] = test_suite

        return test_suites, nspace

    @staticmethod
    def load_test(
        test_class: str, funclass_names: List[str], nspace: Dict[str, Any]
    ) -> TestSuite:
        """Load a test case into a test suite and add it to the namespace."""

        for funclass_name in funclass_names:
            ref_name = f"reference_{funclass_name}"

            try:
                test_class= R2ETestCleaner.clean_test_case(
                    test_class, funclass_name, ref_name
                )
            except Exception as e:
                print("[ERROR] Could not load test case!")
                raise

        try:
            R2ETestLoader.add_test_to_namespace(test_class, nspace)

            test_suite, test_classes = R2ETestLoader.create_test_suite(nspace)
            R2ETestLoader.clean_namespace(nspace, test_classes)
        except Exception as e:
            print("[ERROR] Could not load test case!")
            raise
        return test_suite

    @staticmethod
    def add_test_to_namespace(test_class: str, nspace: Dict[str, Any]):
        """Add the test case to the namespace."""
        exec(test_class, nspace, nspace)

    @staticmethod
    def create_test_suite(nspace: Dict[str, Any]) -> Tuple[TestSuite, List[str]]:
        """Create a test suite from the test class."""
        loader, test_suite = TestLoader(), TestSuite()
        test_classes = []

        for name, obj in nspace.items():
            if isinstance(obj, type) and issubclass(obj, TestCase):
                test_suite.addTest(loader.loadTestsFromTestCase(obj))
                test_classes.append(name)

        return test_suite, test_classes

    @staticmethod
    def clean_namespace(nspace: Dict[str, Any], test_classes: List[str]):
        """Remove the test classes from the namespace."""
        for name in test_classes:
            nspace.pop(name, None)
