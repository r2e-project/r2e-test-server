import os
import ast
import sys
import json
import coverage
import importlib
import importlib.util
from copy import deepcopy
from typing import Any, Union, List, Dict, Optional, Tuple
from types import ModuleType, FunctionType


from r2e_test_server.testing.loader import R2ETestLoader
from r2e_test_server.testing.runner import R2ETestRunner
from r2e_test_server.ast.transformer import NameReplacer
from r2e_test_server.testing.codecov import R2ECodeCoverage
from r2e_test_server.modules.explorer import ModuleExplorer
from r2e_test_server.instrument import Instrumenter, CaptureArgsInstrumenter


if sys.version_info < (3, 9):
    import astor

    ast.unparse = lambda node: astor.to_source(node)


class R2ETestProgram(object):
    """A program that runs tests in the R2E framework.

    Args:
        fid (str): identifier for function under test.
        codegen (bool): Whether the function under test is generated code.
    """

    def __init__(
        self,
        repo_id: Optional[str],
        repo_path: str,
        funclass_names: List[str],
        file_path: str,
        generated_tests: Dict[str, str],
        codegen_mode: bool = False,
    ):
        ## file_path should be relative to repo_path
        self.repo_id = repo_id
        if repo_id is None:
            self.repo_path = os.path.abspath(repo_path)
        else:
            self.repo_path = f"/repos/{repo_id}"
        self.funclass_names = funclass_names
        self.file_path = os.path.join(self.repo_path, file_path)
        self.generated_tests = generated_tests
        self.codegen_mode = codegen_mode

        with open(self.file_path, "r") as file:
            self.orig_file_content = file.read()
            self.orig_file_ast = ast.parse(self.orig_file_content)

        # setup the env for testing
        # creates: fut_module and fut_module_deps
        self.setupEnv()

        # setup reference function
        # creates: ref_function(s) in fut_module
        self.setupRefs()

        # removes the funclasses from fut_module if codegen_mode
        self.setup_codegen_mode()

    def setupEnv(self):
        """Setup the environment for testing.

        Dynamically import the module containing the FUT.
        Save the module and its dependencies.
        """

        fut_module, fut_module_deps = self.get_fut_module()
        sys.modules["fut_module"] = fut_module

        self.fut_module = fut_module
        self.fut_module_deps = fut_module_deps

        return

    def setupRefs(self):
        """Creates a reference/oracle for testing.

        reference is a deep copy of the code under test.
        exec()s to load reference function into the environment.
        """
        for funclass_name in self.funclass_names:

            # for a method, use the enclosing class as the reference object
            if "." in funclass_name:
                class_name, _ = funclass_name.split(".")
                funclass_name = class_name

            ref_name = f"reference_{funclass_name}"
            orig_ast = self.get_funclass_ast(funclass_name)

            temp = deepcopy(orig_ast)
            temp.name = ref_name
            new_ast = ast.Module(body=[temp], type_ignores=[])

            new_ast = NameReplacer(new_ast, funclass_name, ref_name).transform()
            new_source = ast.unparse(new_ast)

            self.compile_and_exec(new_source)

        return

    def setup_codegen_mode(self):
        if self.codegen_mode:
            for funclass_name in self.funclass_names:
                if "." in funclass_name:
                    class_name, method_name = funclass_name.split(".")
                    class_obj = self.get_funclass_object(class_name)
                    if class_obj:
                        delattr(self.fut_module, class_name)
                else:
                    funclass_object = self.get_funclass_object(funclass_name)
                    if funclass_object and not isinstance(funclass_object, type):
                        delattr(self.fut_module, funclass_name)

    def submit(self) -> str:
        """Submit the function/method under test to the R2E test framework.

        Returns:
            str: JSON string containing the test results.
        """
        # instrument code and build namespace
        instrumenter = CaptureArgsInstrumenter()
        self.instrumentCode(instrumenter)

        # build namespace
        nspace = self.buildNamespace()

        # run tests
        run_tests_logs, codecovs = self.runTests(nspace=nspace)
        captured_arg_logs = instrumenter.get_logs()
        coverage_logs = [codecov.report_coverage() for codecov in codecovs]

        result = {
            "run_tests_logs": run_tests_logs,
            "coverage_logs": coverage_logs,
            "captured_arg_logs": captured_arg_logs,
        }

        return json.dumps(result, indent=4)

    def instrumentCode(self, instrumenter: Instrumenter):
        """Instrument the code under test.

        Args:
            instrumenter (Instrumenter): Instrumenter object.
        """
        for funclass_name in self.funclass_names:
            if "." in funclass_name:
                class_name, method_name = funclass_name.split(".")
                class_obj = self.get_funclass_object(class_name)

                if class_obj:
                    class_obj = instrumenter.instrument_method(class_obj, method_name)
                    setattr(self.fut_module, class_name, class_obj)

            else:
                funclass_object = self.get_funclass_object(funclass_name)

                if funclass_object and not isinstance(funclass_object, type):
                    funclass_object = instrumenter.instrument(funclass_object)
                    setattr(self.fut_module, funclass_name, funclass_object)

    def buildNamespace(self) -> Dict[str, Any]:
        """Build namespace for the test runner.

        Notes:
            - https://docs.python.org/3/reference/executionmodel.html
            - namespace = {`Name` ↦ `object`}
        """
        nspace = {}
        nspace["fut_module"] = self.fut_module
        nspace.update(self.fut_module.__dict__)
        return nspace

    def runTests(self, nspace: Dict[str, Any]):
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

        codecovs = [
            R2ECodeCoverage(cov, self.fut_module, self.file_path, funclass_name)
            for funclass_name in self.funclass_names
        ]

        return combined_stats, codecovs

    # helpers

    def get_fut_module(self) -> Tuple[ModuleType, Dict[str, Any]]:
        """Dynamically import and retrieve the module containing the function under test.
        Also retrieve the dependencies of the module.

        Args:
            FUT (FunctionUnderTest): function under test.

        Returns:
            Tuple[ModuleType, Dict[str, Any]]: module and its dependencies.
        """

        try:
            return self.import_fut_module_with_paths([self.repo_path])
        except ModuleNotFoundError as e:
            print(f"[WARNING] Module not found: {str(e)}. Trying with extended paths.")
            try:
                extended_paths = self.get_paths_to_submodules()
                return self.import_fut_module_with_paths(extended_paths)
            except ModuleNotFoundError as e:
                print(f"[ERROR] Module still not found: {str(e)}")
                raise
        except Exception as e:
            print("[ERROR] Bug in the imported FUT module?")
            raise

        return fut_module, fut_module_deps

    def import_fut_module_with_paths(
        self, paths: list[str]
    ) -> Tuple[ModuleType, dict[str, Any]]:
        """Attempt to dynamically import the fut_module with the given paths in sys.path.

        Args:
            paths (list[str]): paths to add to sys.path.

        Returns:
            Tuple[ModuleType, dict[str, Any]]: module and its dependencies.

        Note: if module is not found, the paths are removed from sys.path.
        the exception raised should be handled by the caller.
        """

        for path in paths:
            if path not in sys.path:
                sys.path.insert(0, path)

        try:
            fut_module = self.import_module_dynamic("fut_module", self.file_path)
            fut_module_deps = ModuleExplorer.get_dependencies(self.file_path)
        finally:
            for path in paths:
                sys.path.remove(path)

        return fut_module, fut_module_deps

    def get_paths_to_submodules(self) -> list[str]:
        """Build extended paths to the submodules that fut_module can import.

        Returns:
            list[str]: extended paths.

        Note: used in case of a non-standard/non-flat directory structure.
        """
        submodule_paths: list[str] = [self.repo_path]
        curr_path = os.path.dirname(self.file_path)
        while curr_path != self.repo_path:
            submodule_paths.append(curr_path)
            curr_path = os.path.dirname(curr_path)

        return submodule_paths

    def get_funclass_object(self, name: str) -> Union[FunctionType, type]:
        """Get the function or class object from the module by name."""
        return getattr(self.fut_module, name)

    def get_funclass_ast(
        self, funclass_name: str
    ) -> Union[ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef]:
        """Get the function or class AST node from the original file by name."""
        for node in self.orig_file_ast.body:
            if (
                isinstance(node, ast.ClassDef)
                or isinstance(node, ast.FunctionDef)
                or isinstance(node, ast.AsyncFunctionDef)
            ):
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
