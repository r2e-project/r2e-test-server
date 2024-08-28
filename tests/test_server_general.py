import json
import unittest

from r2e_test_server.server import R2EService


test_serialize_default = """
import datetime
from decimal import Decimal
from collections.abc import Iterable
import unittest
import json

class TestSerializers(unittest.TestCase):

    def test_serialize_datetime(self):
        dt = datetime.datetime(2023, 10, 1, 12, 0, 0)
        self.assertEqual(Serializers.serialize_default(dt), dt.isoformat())

    def test_serialize_date(self):
        d = datetime.date(2023, 10, 1)
        self.assertEqual(Serializers.serialize_default(d), d.isoformat())

    def test_serialize_decimal(self):
        dec = Decimal('10.5')
        self.assertEqual(Serializers.serialize_default(dec), float(dec))

    def test_serialize_iterable(self):
        iterable = [1, 2, 3]
        self.assertEqual(Serializers.serialize_default(iterable), json.dumps(iterable))

"""

gpt4_codegen1 = """class Serializers:

    @staticmethod
    def serialize_default(obj):
        # Handle datetime and date objects
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()

        # Handle Decimal objects
        elif isinstance(obj, Decimal):
            return float(obj)

        # Handle objects with a __dict__ attribute
        elif hasattr(obj, "__dict__"):
            return {k: Serializers.serialize_default(v) for k, v in obj.__dict__.items()}

        # Handle iterables, but not strings or bytes
        elif isinstance(obj, Iterable) and not isinstance(obj, (str, bytes)):
            return [Serializers.serialize_default(item) for item in obj]

        # Try to serialize using the object's custom methods
        for method_name in ("to_json", "to_string", "to_str", "__str__", "__repr__"):
            if hasattr(obj, method_name):
                method = getattr(obj, method_name)
                if callable(method):
                    try:
                        return method()
                    except Exception:
                        pass

        # If all else fails, return the object's type name
        return f"<unserializable: {type(obj).__name__}>"
"""

gpt4_codegen2 = """class Serializers:

    @staticmethod
    def serialize_default(obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()

        elif isinstance(obj, Decimal):
            return float(obj)

        try:
            return repr(obj)
        except Exception as e:
            pass

        # Handle objects with a __dict__ attribute
        if hasattr(obj, "__dict__"):
            return {
                k: Serializers.serialize_default(v) for k, v in obj.__dict__.items()
            }

        # Handle iterables, but not strings or bytes
        elif isinstance(obj, Iterable) and not isinstance(obj, (str, bytes)):
            return [Serializers.serialize_default(item) for item in obj]

        # Try to serialize using the object's custom methods
        for method_name in ("to_json", "to_string", "to_str", "__str__", "__repr__"):
            if hasattr(obj, method_name):
                try:
                    method = getattr(obj, method_name)
                    if callable(method):
                        return method()
                except Exception as e:
                    pass

        # If all else fails, return the object's type name
        return f"<unserializable: {type(obj).__name__}>"
"""


class TestR2EService(unittest.TestCase):

    def check_coverage_exists(self, coverage_logs):
        for coverage_log in coverage_logs:
            self.assertTrue(len(coverage_log) > 0)

    def is_empty_output(self, out):
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

    def test_self_equiv(self):
        service = R2EService()
        data = {"repo_id": None, "repo_path": ""}
        data = json.dumps(data)
        service.setup_repo(data)

        data = {
            "funclass_names": ["Serializers.serialize_default"],
            "file_path": "r2e_test_server/instrument/arguments.py",
        }
        data = json.dumps(data)
        service.setup_function(data)

        data = {"generated_tests": {"test_1": test_serialize_default}}
        data = json.dumps(data)
        service.setup_test(data)

        out = service.init()
        self.is_empty_output(out)

        out = service.submit()
        self.assertEqual(out["output"], "")
        logs = json.loads(out["logs"])
        self.assertTrue(logs["run_tests_logs"]["test_1"]["valid"])
        self.check_coverage_exists(logs["coverage_logs"])

    def test_gpt4_codegen(self):

        service = R2EService()
        data = {"repo_id": None, "repo_path": ""}
        data = json.dumps(data)
        service.setup_repo(data)

        data = {
            "funclass_names": ["Serializers.serialize_default"],
            "file_path": "r2e_test_server/instrument/arguments.py",
        }
        data = json.dumps(data)
        service.setup_function(data)

        data = {"generated_tests": {"test_1": test_serialize_default}}
        data = json.dumps(data)
        service.setup_test(data)

        service.setup_codegen_mode()

        out = service.init()
        self.is_empty_output(out)

        out = service.execute(gpt4_codegen1)
        self.is_empty_output(out)

        out = service.submit()
        self.assertEqual(out["output"], "")
        logs = json.loads(out["logs"])
        self.assertFalse(logs["run_tests_logs"]["test_1"]["valid"])

    def test_gpt4_agentic(self):
        service = R2EService()
        data = {"repo_id": None, "repo_path": ""}
        data = json.dumps(data)
        service.setup_repo(data)

        data = {
            "funclass_names": ["Serializers.serialize_default"],
            "file_path": "r2e_test_server/instrument/arguments.py",
        }
        data = json.dumps(data)
        service.setup_function(data)

        data = {"generated_tests": {"test_1": test_serialize_default}}
        data = json.dumps(data)
        service.setup_test(data)

        service.setup_codegen_mode()

        out = service.init()
        self.is_empty_output(out)

        out = service.execute(f"code = 'def f(): return a+b'")
        self.is_empty_output(out)

        out = service.execute(f"import ast, dis")
        self.is_empty_output(out)

        out = service.execute(f"code_ast = ast.parse(code)")
        self.is_empty_output(out)

        out = service.execute(
            f"code_obj = dis.Bytecode(compile(code, '<string>', 'exec'))"
        )
        self.is_empty_output(out)

        out = service.execute("symbols = ['a', 'b']")
        self.is_empty_output(out)

        out = service.execute("print(symbols)")
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "['a', 'b']")

        out = service.execute(gpt4_codegen1)
        self.is_empty_output(out)

        out = service.submit()
        self.assertEqual(out["output"], "")
        logs = json.loads(out["logs"])
        self.assertFalse(logs["run_tests_logs"]["test_1"]["valid"])

        out = service.execute(gpt4_codegen2)
        self.is_empty_output(out)

        out = service.submit()
        self.assertEqual(out["output"], "")
        logs = json.loads(out["logs"])
        self.assertTrue(logs["run_tests_logs"]["test_1"]["valid"])
