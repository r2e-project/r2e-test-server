import ast
import sys
import json
import importlib
import importlib.util
import coverage
from typing import Any
from copy import deepcopy
from types import ModuleType, FunctionType


from r2e_test_server.testing.loader import R2ETestLoader
from r2e_test_server.testing.runner import R2ETestRunner
from r2e_test_server.ast.transformer import NameReplacer
from r2e_test_server.testing.codecov import R2ECodeCoverage
from r2e_test_server.modules.explorer import ModuleExplorer

from r2e_test_server.instrument.arguments import CaptureArgsInstrumenter


class R2ETestProgram(object):
    """A program that runs tests in the R2E framework.

    Args:
        fid (str): identifier for function under test.
        codegen (bool): Whether the function under test is generated code.
    """

    def __init__(
        self,
        repo_name: str,
        repo_path: str,
        funclass_names: list[str],
        file_path: str,
        generated_tests: dict[str, str],
    ):
        self.repo_name = repo_name
        self.repo_path = repo_path
        self.funclass_names = funclass_names
        self.file_path = file_path
        self.generated_tests = generated_tests

        with open(file_path, "r") as file:
            self.orig_file_content = file.read()
        self.orig_file_ast = ast.parse(self.orig_file_content)

        # setup function under tes
        self.setupFuts()  # creates: fut_function(s), fut_module, and fut_module_deps

        # setup reference function
        self.setupRefs()  # creates: ref_function(s) inside self.fut_module

    def setupFuts(self):
        """Setup the function under test (FUT).
        Dynamically import the module containing the FUT.
        Store the FUT, its module, and its dependencies in test program class.
        """

        fut_module, fut_module_deps = self.get_fut_module()
        sys.modules["fut_module"] = fut_module

        self.fut_module = fut_module
        self.fut_module_deps = fut_module_deps

        # NOTE: for consistency between codegen and self-equivalence
        # we will recompile the orignal function in the namespace
        # for funclass_name in self.funclass_names:
        #     orig_ast = self.get_funclass_ast(funclass_name)
        #     orig_source = ast.unparse(orig_ast)

        #     self.compile_and_exec(orig_source)
        return

    def setupRefs(self):
        """Create a reference function from the function under test.
        The reference function is a deep copy of the FUT.
        Store the reference function in the FUT module and in the test program class.
        """
        for funclass_name in self.funclass_names:
            ref_name = f"reference_{funclass_name}"
            orig_ast = self.get_funclass_ast(funclass_name)

            temp = deepcopy(orig_ast)
            temp.name = ref_name
            new_ast = ast.Module(body=[temp], type_ignores=[])

            new_ast = NameReplacer(new_ast, funclass_name, ref_name).transform()
            new_source = ast.unparse(new_ast)

            self.compile_and_exec(new_source)

        return

    def submit(self):
        # instrument code
        instrumenter = CaptureArgsInstrumenter()
        for funclass_name in self.funclass_names:
            ## TODO: instrumenter only works for functions, not classes
            ## handle classes -- need to pass class-method information as well
            funclass_object = self.get_funclass_object(funclass_name)

            if isinstance(funclass_object, type):
                continue

            funclass_object = instrumenter.instrument(funclass_object)
            setattr(
                self.fut_module,
                funclass_name,
                funclass_object,
            )

        # build namespace
        nspace = self.buildNamespace()
        nspace.update(globals())

        # run tests
        ## TODO -- coverage doesn't work for classmethods yet (works for classes..)
        run_tests_logs, codecovs = self.runTests(nspace=nspace)
        captured_arg_logs = instrumenter.get_logs()
        coverage_logs = [codecov.report_coverage() for codecov in codecovs]

        result = {
            "run_tests_logs": run_tests_logs,
            "coverage_logs": coverage_logs,
            "captured_arg_logs": captured_arg_logs,
        }

        return json.dumps(result, indent=4)

    def buildNamespace(self) -> dict[str, Any]:
        """Build namespace for the test runner.

        Notes:
            - https://docs.python.org/3/reference/executionmodel.html
            - namespace = {`Name` ↦ `object`}

        Args:
            fut_name (str): name of the function under test.
            ref_name (str): name of the reference function.
            fut_module (ModuleType): module containing the function under test.
            fut_module_deps (dict): dependencies of the module.

        Returns:
            dict[str, Any]: namespace for the test runner.
        """
        nspace = {}

        ## NOTE : adding both nsoace and fut_module.__dict__  seems hacky?...
        nspace["fut_module"] = self.fut_module
        for funclass_name in self.funclass_names:
            nspace[funclass_name] = self.get_funclass_object(funclass_name)
            ref_name = f"reference_{funclass_name}"
            nspace[ref_name] = self.get_funclass_object(ref_name)

        ## NOTE : this might not be necessary? dir(fut_module) should be enough and already includes the module itself
        nspace.update(self.fut_module_deps)

        for name in dir(self.fut_module):
            if not name.startswith("__"):  # ignore built-ins
                nspace[name] = getattr(self.fut_module, name)

        return nspace

    def runTests(self, nspace: dict[str, Any]):
        """Run tests for the function under test.

        Args:
            FUT (FunctionUnderTest): function under test.
            nspace (dict): namespace to run tests in.

        """
        test_suites, nspace = R2ETestLoader.load_tests(
            self.generated_tests, self.funclass_names, nspace
        )

        cov = coverage.Coverage(include=[self.file_path], branch=True)
        cov.start()
        runner = R2ETestRunner()

        combined_stats = {}
        for test_idx, test_suite in test_suites.items():
            _, stats = runner.run(test_suite)
            combined_stats[test_idx] = stats

        cov.stop()
        cov.save()

        ## TODO -- we need classmethod name to get method level coverage
        ## already reason about assumption of what should coverage be measuring
        ## since in classes, we prolly care about other methods as well..
        codecovs = [
            R2ECodeCoverage(cov, self.fut_module, self.file_path, funclass_name)
            for funclass_name in self.funclass_names
        ]

        return combined_stats, codecovs

    # helpers

    def get_fut_module(self) -> tuple[ModuleType, dict[str, Any]]:
        """Dynamically import and retrieve the module containing the function under test.
        Also retrieve the dependencies of the module.

        Args:
            FUT (FunctionUnderTest): function under test.

        Returns:
            tuple[ModuleType, dict[str, Any]]: module and its dependencies.
        """

        try:
            if self.repo_path not in sys.path:
                sys.path.insert(0, self.repo_path)

            fut_module = self.import_module_dynamic("fut_module", self.file_path)
            fut_module_deps = ModuleExplorer.get_dependencies(self.file_path)

            sys.path.remove(self.repo_path)
        except ModuleNotFoundError as e:
            print(f"[ERROR] {str(e)}: Library not installed?")
            raise
        except Exception as e:
            print("[ERROR] Bug in the imported FUT module?")
            raise

        return fut_module, fut_module_deps

    def get_funclass_object(self, funclass_name: str) -> FunctionType | type:
        """Get the function or class object from the module by name."""
        return getattr(self.fut_module, funclass_name)

    def get_funclass_ast(self, funclass_name: str) -> ast.FunctionDef | ast.ClassDef:
        """Get the function or class AST node from the original file by name."""
        for node in self.orig_file_ast.body:
            if isinstance(node, ast.ClassDef) or isinstance(node, ast.FunctionDef):
                if node.name == funclass_name:
                    return node
        raise ValueError(f"Function or class {funclass_name} not found in the file.")

    def import_module_dynamic(self, module_name: str, module_path: str) -> ModuleType:
        """Dynamically import a module from a file path.

        Args:
            module_name (str): name of the module.
            module_path (str): path to the module.

        Returns:
            ModuleType: imported module.
        """

        spec = importlib.util.spec_from_file_location(module_name, module_path)

        if spec is None or spec.loader is None:
            raise ModuleNotFoundError(
                f"Module {module_name} not found at {module_path}"
            )

        module = importlib.util.module_from_spec(spec)
        module.__package__ = ModuleExplorer.get_package_name(module_path)
        spec.loader.exec_module(module)
        sys.modules[module_name] = module
        return module

    def compile_and_exec(self, code: str, nspace=None) -> Any:
        """Compile and execute code in a namespace."""
        compiled_code = compile(code, "<string>", "exec")
        if nspace is None:
            exec(compiled_code, self.fut_module.__dict__)
        else:
            exec(compiled_code, nspace)
