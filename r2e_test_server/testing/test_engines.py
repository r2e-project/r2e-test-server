from enum import Enum, auto
import os, ast, sys, coverage, importlib, importlib.util
from copy import deepcopy
from typing import Any, Union, List, Dict, Optional, Tuple, cast
from types import ModuleType, FunctionType
from pathlib import Path


from r2e_test_server.testing.loader import R2ETestLoader
from r2e_test_server.testing.runner import R2ETestRunner
from r2e_test_server.ast.transformer import NameReplacer
from r2e_test_server.testing.codecov import R2ECodeCoverage
from r2e_test_server.modules.explorer import ModuleExplorer
from r2e_test_server.instrument import Instrumenter, CaptureArgsInstrumenter
from r2e_test_server.testing.util import ensure


if sys.version_info < (3, 9):
    import astor

    ast.unparse = lambda node: astor.to_source(node)

class PerfTypes(Enum):
    LATENCY=auto(),
    MEMORY=auto()

class R2ETestEngine(object):
    """Execution engine capable of running multiple tests for one FUT in R2E framework."""

    repo_path: Path
    '''Path to the repo'''
    
    funclass_names: List[str]

    orig_file_content: str
    '''original content of the file '''

    orig_file_ast: ast.AST
    '''parsed ast of the original file'''

    repo_dir: Path
    result_dir: Path
    file_path: str
    '''path to the FUT module, also controlls how the all other deps are 
    imported (for different version of FUT)'''

    loaded_fut_version: str = 'original'
    instrumenter: Optional[CaptureArgsInstrumenter] = None
    nspace: Optional[dict] = None

    verbose: bool

    restored: bool = True

    def __init__(
        self,
        repo_path: Path,
        funclass_names: List[str],
        file_path: str,
        result_dir: Path,
        verbose: bool = False
    ):
        self.verbose = verbose
        ## file_path should be relative to repo_path
        self.repo_path = Path(repo_path)
        if not self.repo_path.exists() or not self.repo_path.is_dir():
            raise ValueError("The directory should exist!" + " Not just a path." if self.repo_path.exists() else "")
        self.funclass_names = funclass_names
        self.file_path = str((self.repo_path / file_path).absolute())
        self.result_dir = result_dir

        with open(self.file_path, "r") as file:
            self.orig_file_content = file.read()
            self.orig_file_ast = ast.parse(self.orig_file_content)

        if self.verbose:
            print('setting up test engine environment')

        # setup the env for testing
        # creates: fut_module and fut_module_deps
        self.setup_env()

        # setup reference function
        # creates: ref_function(s) in fut_module
        self.setup_ref()

    def setup_env(self):
        """Setup the environment for testing.

        Dynamically import the module containing the FUT.
        Save the module and its dependencies.
        """

        fut_module, fut_module_deps = self.get_fut_module(self.file_path)
        sys.modules["fut_module"] = fut_module
        self.fut_module = fut_module
        self.fut_module_deps = fut_module_deps

    cached_refs: Optional[List[str]] = None
    def setup_ref(self):
        """Creates a reference/oracle for testing.

        reference is a deep copy of the code under test.
        exec()s to load reference function into the environment.
        """
        # TODO: should be cached
        if self.cached_refs is None:
            self.cached_refs = []
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
                self.cached_refs.append(ast.unparse(new_ast))
            
        for new_source in self.cached_refs:
            self.compile_and_exec(new_source)

    def env_cleanup(self):
        """remove the original FUT imported through module to cleanup for later eval"""
        for funclass_name in self.funclass_names:
            if "." in funclass_name:
                class_name, _ = funclass_name.split(".")
                class_obj = self.get_funclass_object(class_name)
                if class_obj:
                    delattr(self.fut_module, class_name)
            else:
                funclass_object = self.get_funclass_object(funclass_name)
                if funclass_object and not isinstance(funclass_object, type):
                    delattr(self.fut_module, funclass_name)

    def eval_tests(self, tests: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """evaluate on a dictionary from test id to tests"""
        return self(tests)[0]

    def eval_patch(self, tests: Dict[str, str],
                   patch_version: str = "original", 
                   patch: str = "", 
                   patch_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        return self(tests, patch_version=patch_version, 
                    patch=patch,
                    patch_path=patch_path)[0]

    def __call__(self, tests: Dict[str, str] = {}, 
               perfs: Dict[str, Tuple[PerfTypes, str]] = {},
               patch_version: str = "original", 
               patch: str = "",
               patch_path: Optional[str] = None) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """evaluate patch on the tests specified"""

        if patch_path is not None:
            with open(patch_path) as f:
                patch = f.read()

        # import the file in fut_path to fut_module, refer to setup_env
        # also consider hashing to avoid reloading multiple times
        if patch_version != self.loaded_fut_version:
            if patch_version != 'original':
                self.restored = False
            # setup the file, 'original' use original file content
            with open(self.file_path, 'w') as f:
                f.write(self.orig_file_content if patch_version == "original" else patch)

            if patch_version == 'original':
                self.restored = True
            # WARNING: do not use cleanup here since there could be very nasty problems (like missing dep, new func with the same name, etc.)
            self.setup_env()
            self.setup_ref()

        # instrument code and build namespace
        # again, hashing to avoid reloading multiple times
        if patch_version != self.loaded_fut_version or self.instrumenter is None:
            self.instrumenter = cast(CaptureArgsInstrumenter, self.inst_code(CaptureArgsInstrumenter()))

        # build namespace
        if patch_version != self.loaded_fut_version or self.nspace is None:
            self.nspace = self.build_nspace()
        self.loaded_fut_version = patch_version

        # run tests
        results: Dict[str, Dict[str, Any]] = {}
        for test_id, result in self.run_tests(tests, self.nspace).items():
            errors, stats, cov, arg_log = result

            cov_path = ensure(self.result_dir / self.loaded_fut_version / test_id / 'cov_detail.json')
            cov.dump_to(cov_path)

            # WARNING: the coverage returned is only the summary, the full cov should be stored in result dir
            results[test_id] = {
                    'general_logs': stats,
                    'cov_logs': cov.report_coverage(),
                    'error_logs': errors,
                    'captured_arg_logs': arg_log
                }

        perf_results = {}
        for perf_id, result in self.run_perfs(perfs, self.nspace).items():
            errors, stats, cov, arg_log = result

            cov_path = ensure(self.result_dir / self.loaded_fut_version / perf_id / 'cov_detail.json')
            cov.dump_to(cov_path)

            # WARNING: the coverage returned is only the summary, the full cov should be stored in result dir
            perf_results[perf_id] = {
                    'general_logs': stats,
                    'cov_logs': cov.report_coverage(),
                    'error_logs': errors,
                    'captured_arg_logs': arg_log
                }

        return results, perf_results

    def restore(self):
        with open(self.file_path, 'w') as f:
            f.write(self.orig_file_content)

    def inst_code(self, instrumenter: Instrumenter) -> Instrumenter:
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

        return instrumenter

    def build_nspace(self) -> Dict[str, Any]:
        """Build namespace for the test runner.

        Notes:
            - https://docs.python.org/3/reference/executionmodel.html
            - namespace = {`Name` ↦ `object`}
        """
        nspace = {}
        nspace["fut_module"] = self.fut_module
        nspace.update(self.fut_module.__dict__)
        return nspace

    def run_tests(self, tests: Dict[str, str], nspace: Dict[str, Any]):
        """Run tests for the function under test."""
        instrumenter = self.instrumenter
        assert instrumenter is not None
        test_suites, nspace = R2ETestLoader.load_tests(
            tests, self.funclass_names, nspace
        )

        runner = R2ETestRunner()

        def _run_with_cov(test_suite):
            instrumenter.clear()
            cov = coverage.Coverage(include=[self.file_path], branch=True)
            cov.start()
            errors, stats = runner.run(test_suite)
            cov.stop()
            cov.save()
            return errors, stats, cov, instrumenter.get_logs()

        return {test_id: (errors, stats, R2ECodeCoverage(cov, self.fut_module, self.file_path, self.funclass_names[0]), arg_log) 
                for test_id, (errors, stats, cov, arg_log) in map(lambda x: (x[0], _run_with_cov(x[1])), test_suites.items())}

    def run_perfs(self, tests: Dict[str, Tuple[PerfTypes, str]], nspace: Dict[str, Any]):
        """Run perf tests for the function under test."""
        if len(tests) == 0:
            return {}
        raise NotImplementedError
        instrumenter = self.instrumenter
        assert instrumenter is not None
        test_suites, nspace = R2ETestLoader.load_tests(
            tests, self.funclass_names, nspace
        )

        runner = R2ETestRunner()

        def _run_with_cov(test_suite):
            instrumenter.clear()
            cov = coverage.Coverage(include=[self.file_path], branch=True)
            cov.start()
            errors, stats = runner.run(test_suite)
            cov.stop()
            cov.save()
            return errors, stats, cov, instrumenter.get_logs()

        return {test_id: (errors.get_error_list(), stats, R2ECodeCoverage(cov, self.fut_module, self.file_path, self.funclass_names[0]), arg_log) 
                for test_id, (errors, stats, cov, arg_log) in map(lambda x: (x[0], _run_with_cov(x[1])), test_suites.items())}


    # helpers

    def get_fut_module(self, fut_path: str) -> Tuple[ModuleType, Dict[str, Any]]:
        """Dynamically import and retrieve the module containing the function under test.
        Also retrieve the dependencies of the module.

        Args:
            FUT (FunctionUnderTest): function under test.

        Returns:
            Tuple[ModuleType, Dict[str, Any]]: module and its dependencies.
        """

        try:
            return self.import_fut_module_with_paths(fut_path, [str(self.repo_path)])
        except ModuleNotFoundError as e:
            print(f"[WARNING] Module not found: {str(e)}. Trying with extended paths.")
            try:
                # WARNING: prolly remember to modify this stuff if want to apply multi-file patch
                extended_paths = self.get_paths_to_submodules()
                return self.import_fut_module_with_paths(fut_path, extended_paths)
            except ModuleNotFoundError as e:
                print(f"[ERROR] Module still not found: {str(e)}")
                raise
        except Exception as e:
            print("[ERROR] Bug in the imported FUT module?")
            raise

    def import_fut_module_with_paths(
            self, fut_path: str, paths: List[str]
    ) -> Tuple[ModuleType, Dict[str, Any]]:
        """Attempt to dynamically import the fut_module with the given paths in sys.path.

        Args:
            paths (List[str]): paths to add to sys.path.

        Returns:
            Tuple[ModuleType, Dict[str, Any]]: module and its dependencies.

        Note: if module is not found, the paths are removed from sys.path.
        the exception raised should be handled by the caller.
        """

        for path in paths:
            if path not in sys.path:
                sys.path.insert(0, path)

        try:
            fut_module = self.import_module_dynamic("fut_module", fut_path)
            # WARNING: prolly also modify this if multi-patch
            fut_module_deps = ModuleExplorer.get_dependencies(fut_path)
        finally:
            for path in paths:
                sys.path.remove(path)

        return fut_module, fut_module_deps

    def get_paths_to_submodules(self) -> List[str]:
        """Build extended paths to the submodules that fut_module can import.

        Returns:
            List[str]: extended paths.

        Note: used in case of a non-standard/non-flat directory structure.
        """
        submodule_paths: List[str] = [str(self.repo_path)]
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

    def compile_and_exec(self, code: str, namespace=None) -> Any:
        """Compile and execute code in a namespace."""
        exec(compile(code, '<string>', "exec"), namespace or self.fut_module.__dict__)

