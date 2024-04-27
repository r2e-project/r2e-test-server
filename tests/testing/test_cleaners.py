import unittest

from r2e_test_server.testing.cleaner import R2ETestCleaner


class TestR2ETestCleaner(unittest.TestCase):

    def test_clean_with_aliasing(self):
        test_case = """
import unittest
from fut_module import replace_most_similar_chunk as aliased_fut
from fut_module import reference_replace_most_similar_chunk as aliased_ref_fut

class TestReplaceMostSimilarChunk(unittest.TestCase):
    def test_perfect_match(self):
        whole = "This is a test.\\nThis is only a test.\\n"
        part = "This is only a test.\\n"
        replace = "This is a real thing.\\n"
        expected = aliased_ref_fut(whole, part, replace)
        result = aliased_fut(whole, part, replace)
        self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()
"""
        fut_name = "replace_most_similar_chunk"
        ref_fut_name = "reference_replace_most_similar_chunk"
        cleaned_test_case = R2ETestCleaner.clean_test_case(
            test_case, fut_name, ref_fut_name
        )
        self.assertNotIn("unittest.main()", cleaned_test_case)
        self.assertNotIn("from fut_module import", cleaned_test_case)
        self.assertNotIn("= aliased_fut(", cleaned_test_case)
        self.assertNotIn("= aliased_ref_fut(", cleaned_test_case)
        self.assertIn(" = replace_most_similar_chunk(", cleaned_test_case)
        self.assertIn(" = reference_replace_most_similar_chunk(", cleaned_test_case)

    def test_clean_bad_reference_import(self):
        test_case = """
import unittest
from fut_module import diff_partial_update as reference_diff_partial_update
from fut_module import diff_partial_update as diff_partial_update
"""
        fut_name = "diff_partial_update"
        ref_fut_name = "reference_diff_partial_update"
        cleaned_test_case = R2ETestCleaner.clean_test_case(
            test_case, fut_name, ref_fut_name
        )
        self.assertNotIn("from fut_module import", cleaned_test_case)
        self.assertEqual(cleaned_test_case, "import unittest")

    def test_clean_reimplementation(self):
        test_case = """
import unittest
def foo(): pass
def reference_foo(): pass
    
class TestFoo(unittest.TestCase):
    def test_foo(self):
        self.assertEqual(foo(), reference_foo())
"""
        fut_name = "foo"
        ref_fut_name = "reference_foo"
        cleaned_test_case = R2ETestCleaner.clean_test_case(
            test_case, fut_name, ref_fut_name
        )
        self.assertNotIn("def foo(): pass", cleaned_test_case)
        self.assertNotIn("def reference_foo(): pass", cleaned_test_case)

    def test_no_clean_call_with_fut_module(self):
        test_case = """
class TestTimestampConversion(unittest.TestCase):

    def test_nanoseconds_timestamp_conversion(self):
        test_cases = [...]
        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                expected = fut_module.reference_timestamp_conversion(test_case)
                result = fut_module.timestamp_conversion(test_case)
                self.assertEqual(result, expected)
"""
        fut_name = "timestamp_conversion"
        ref_fut_name = "reference_timestamp_conversion"
        cleaned_test_case = R2ETestCleaner.clean_test_case(
            test_case, fut_name, ref_fut_name
        )

        self.assertIn("fut_module.reference_timestamp_conversion", cleaned_test_case)
        self.assertIn("fut_module.timestamp_conversion", cleaned_test_case)
        self.assertEqual(test_case.strip(), cleaned_test_case.strip())


if __name__ == "__main__":
    unittest.main()
