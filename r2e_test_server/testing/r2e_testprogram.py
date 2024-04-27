import sys
import json
import importlib
import coverage
from typing import Any
from types import ModuleType, FunctionType


from r2e_test_server.modules.explorer import ModuleExplorer
from r2e_test_server.instrument.arguments import CaptureArgsInstrumenter
from r2e_test_server.testing.loader import R2ETestLoader
from r2e_test_server.testing.runner import R2ETestRunner


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
        function_name: str,
        file_path: str,
        function_code: str,
        generated_tests: dict[str, str],
    ):
        self.repo_name = repo_name
        self.repo_path = repo_path
        self.function_name = function_name
        self.fut_name = function_name
        self.file_path = file_path
        self.function_code = function_code
        self.generated_tests = generated_tests

        # setup function under test and stores
        #  -- self.fut_function
        #  -- self.fut_module
        #  -- self.fut_module_deps
        self.setupFut()

        # setup reference function and stores
        #  -- self.ref_function
        #  -- ref_function inside self.fut_module
        self.setupRef()

    def setupFut(self):
        """Setup the function under test (FUT).
        Dynamically import the module containing the FUT.
        Store the FUT, its module, and its dependencies in test program class.
        """

        fut_module, fut_module_deps = self.get_fut_module()
        sys.modules["fut_module"] = fut_module

        self.fut_module = fut_module
        self.fut_module_deps = fut_module_deps
        return

    def setupRef(self):
        """Create a reference function from the function under test.
        The reference function is a deep copy of the FUT.
        Store the reference function in the FUT module and in the test program class.
        """
        fut_function = self.get_fut_function()

        self.ref_name = f"reference_{self.fut_name}"
        ref_function = self.setupRef(
            self.fut_name, fut_function, self.fut_module, self.ref_name
        )

        ref_function = FunctionType(
            fut_function.__code__,
            fut_function.__globals__,
            self.ref_name,
            fut_function.__defaults__,
            fut_function.__closure__,
        )
        ref_function.__kwdefaults__ = fut_function.__kwdefaults__
        setattr(self.fut_module, self.ref_name, ref_function)

        self.ref_function = ref_function
        return

    def submit(self):
        # instrument code
        instrumenter = CaptureArgsInstrumenter()
        setattr(
            self.fut_module,
            self.fut_name,
            instrumenter.instrument(self.get_fut_function()),
        )

        # build namespace
        nspace = self.buildNamespace(
            self.fut_name, self.ref_name, self.fut_module, self.fut_module_deps
        )
        nspace.update(globals())

        # run tests
        self.runTests(nspace=globals().copy())
        instrumenter.dump_logs("logs.json")

    def buildNamespace(
        self,
        fut_name: str,
        ref_name: str,
        fut_module: ModuleType,
        fut_module_deps: dict[str, Any],
    ) -> dict[str, Any]:
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

        nspace["fut_module"] = fut_module
        nspace[fut_name] = getattr(fut_module, fut_name)
        nspace[ref_name] = getattr(fut_module, ref_name)

        nspace.update(fut_module_deps)

        for name in dir(fut_module):
            if not name.startswith("__"):  # ignore built-ins
                nspace[name] = getattr(fut_module, name)

        return nspace

    def runTests(self, nspace: dict[str, Any]):
        """Run tests for the function under test.

        Args:
            FUT (FunctionUnderTest): function under test.
            nspace (dict): namespace to run tests in.
        """
        test_suites, nspace = R2ETestLoader.load_tests(
            self.generated_tests, self.function_name, nspace
        )

        cov = coverage.Coverage(include=[self.file_path], branch=True)
        cov.start()
        runner = R2ETestRunner()

        combined_stats = {}
        for idx, test_suite in enumerate(test_suites):
            results, stats = runner.run(test_suite)
            combined_stats[idx] = stats

        cov.stop()
        cov.save()

        print(json.dumps(combined_stats, indent=4))

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

    def get_fut_function(self) -> FunctionType:
        return getattr(self.fut_module, self.fut_name)

    def import_module_dynamic(self, module_name: str, module_path: str) -> ModuleType:
        """Dynamically import a module from a file path.

        Args:
            module_name (str): name of the module.
            module_path (str): path to the module.

        Returns:
            ModuleType: imported module.
        """

        spec = importlib.util.spec_from_file_location(module_name, module_path)  # type: ignore
        module = importlib.util.module_from_spec(spec)  # type: ignore
        module.__package__ = ModuleExplorer.get_package_name(module_path)
        spec.loader.exec_module(module)
        sys.modules[module_name] = module
        return module

    def compile_and_exec(self, code: str, nspace) -> Any:
        """Compile and execute code in a namespace."""
        compiled_code = compile(code, "<string>", "exec")
        if nspace is None:
            exec(compiled_code, self.fut_module.__dict__)
        else:
            exec(compiled_code, nspace)
