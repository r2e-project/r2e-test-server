import sys, traceback
from pathlib import Path
from threading import Thread, Event
from typing import Any, Dict, List, Optional, Tuple
from io import StringIO

import rpyc
from rpyc.utils.server import ThreadPoolServer

from r2e_test_server.testing.test_engines import PerfTypes, R2ETestEngine


class CaptureOutput:

    def __enter__(self):
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.old_stdout.flush()
        self.old_stderr.flush()
        stdout, stderr = StringIO(), StringIO()
        sys.stdout, sys.stderr = stdout, stderr
        return stdout, stderr

    def __exit__(self, _, __, ___):
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr


@rpyc.service
class R2EService(rpyc.Service):
    result_dir: Path
    repo_path: Path
    verbose: bool = False

    engine: Optional[R2ETestEngine] = None
    # TODO: Consider update this for a multi-file version or for a diff-reference version
    fut_versions: Dict[str, str] = {}
    fut_paths: Dict[str, str] = {}

    test_versions: Dict[str, str] = {}
    perf_versions: Dict[str, Tuple[PerfTypes, str]] = {}
    registered: bool = False # WARNING: remove later, only for 1-fut version
    
    def __init__(self, repo_id: str, repo_dir: Path, result_dir: Path, verbose: bool=False):
        self.result_dir = result_dir
        self.repo_path = repo_dir / repo_id
        self.verbose = verbose
        self.test_versions = {}
        self.fut_versions = {}
        
    @rpyc.exposed
    def get_tests(self):
        return self.test_versions

    @rpyc.exposed
    def register_fut(self, 
                     fut_id: str, # INFO: name of the funclass or name for the optimization batch
                     module_path: str): # WARNING: should be relative path
        # WARNING: only do registration, not in fut_versions
        if self.registered:
            raise ValueError("current version only supports single fut registration")

        reg_result = {}
        # TODO: do this async in the future
        # TODO: allow for multiple fut in the future
        # INFO: start up a new engine for this fut and setup the fut_versions `original`
        with CaptureOutput() as (stdout, stderr):
            try:
                if self.verbose:
                    print('creating test engine...')
                self.engine = R2ETestEngine(
                        repo_path=self.repo_path,
                        funclass_names=[fut_id],
                        file_path=module_path,
                        result_dir=self.result_dir,
                        verbose=self.verbose
                    )

                reg_result = {"output": stdout.getvalue().strip(), 
                              "error": stderr.getvalue().strip()}
                self.registered = True
                if self.verbose:
                    print('registration successful')
            except Exception:
                reg_result = {
                    "error": f"Error: {traceback.format_exc()}\n\nSTDERR: {stderr.getvalue().strip()}",
                    "output": stdout.getvalue().strip()
                }

        return reg_result

    @rpyc.exposed
    def get_futs(self):
        return self.fut_versions

    @rpyc.exposed
    def register_test(self,
                      test_content: str,
                      test_id: Optional[str] = None,
                      imm_eval: bool = False) -> Tuple[Tuple[bool, str], Optional[Dict[str, str]]]:
        try:
            def _get_test_id(self) -> str:
                return f"test_{len(self.test_versions)}"
            test_id = test_id or _get_test_id(self)
            self.test_versions[test_id] = test_content
            # TODO: should run the test on ref to get a initial eval result
            if imm_eval:
                return self.eval_test(test_id)
            return (True, ''), None
        except:
            return (False, traceback.format_exc()), None

    @rpyc.exposed
    def submit_patch(self, patch_id: str,  patch_path: str, imm_eval: bool = False):
        # TODO: use this function to submit different versions of the code
        try:
            with open(patch_path) as f:
                patch_content = f.read()
            self.fut_versions[patch_id] = patch_content
            self.fut_paths[patch_id] = patch_path
            # run the test on ref to get a initial eval result
            if imm_eval:
                return self.eval_patch(patch_id=patch_id,
                                       test_id=list(self.test_versions.keys())[0])
            return (True, ''), None
        except:
            return (False, traceback.format_exc()), None

    @rpyc.exposed
    def eval_test(self, test_id: str) -> Tuple[Tuple[bool, str], Optional[Dict[str, Any]]]:
        try:
            assert self.engine is not None, "should register FUT before test"
            test_content = self.test_versions[test_id]
            with CaptureOutput() as (stdout, stderr):
                try:
                    # WARNING: the coverage returned is only the summary, the full cov should be stored in result dir
                    logs = self.engine.eval_tests({test_id: test_content})[test_id]

                    return (True, ''), {"output": stdout.getvalue().strip(), 
                            "error": stderr.getvalue().strip(), 
                            "logs": logs}

                except Exception:
                    return (True, ''), {"error": f"Error: {traceback.format_exc()}\n\nSTDERR: {stderr.getvalue().strip()}",
                            "output": stdout.getvalue().strip()}
        except:
            return (False, traceback.format_exc()), None

    @rpyc.exposed
    def eval_patch(self, patch_id: str, test_id: str) -> Tuple[Tuple[bool, str], Optional[Dict[str, Any]]]:
        try:
            assert self.engine is not None, "should register FUT before test"
            with CaptureOutput() as (stdout, stderr):
                try:
                    # WARNING: the coverage returned is only the summary, the full cov should be stored in result dir
                    logs = self.engine.eval_patch({test_id: self.test_versions[test_id]}, 
                                                  patch_id, patch_path=self.fut_paths[patch_id])[test_id]

                    return (True, ''), {"output": stdout.getvalue().strip(), 
                            "error": stderr.getvalue().strip(), 
                            "logs": logs}

                except Exception:
                    return (True, ''), {"error": f"Error: {traceback.format_exc()}\n\nSTDERR: {stderr.getvalue().strip()}",
                            "output": stdout.getvalue().strip()}
        except:
            return (False, traceback.format_exc()), None

    @rpyc.exposed
    def register_perf(self,
                      perf_content: str,
                      _perf_type: str = 'latency',
                      perf_id: Optional[str] = None,
                      imm_eval: bool = False) -> Tuple[Tuple[bool, str], Optional[Dict[str, str]]]:
        try:
            def _get_perf_id(self) -> str:
                return f"perf_{len(self.test_versions)}"
            perf_type = PerfTypes[_perf_type.upper()]
            perf_id = perf_id or _get_perf_id(self)
            self.perf_versions[perf_id] = (perf_type, perf_content)
            # TODO: should run the test on ref to get a initial eval result
            if imm_eval:
                raise NotImplementedError
            return (True, ''), None
        except:
            return (False, traceback.format_exc()), None

    @rpyc.exposed
    def eval_perf(self, perf_id: str) -> Tuple[Tuple[bool, str], Optional[Dict[str, Any]]]:
        try:
            raise NotImplementedError
            assert self.engine is not None, "should register FUT before test"
            test_content = self.test_versions[test_id]
            with CaptureOutput() as (stdout, stderr):
                try:
                    # WARNING: the coverage returned is only the summary, the full cov should be stored in result dir
                    logs = self.engine.eval_tests({test_id: test_content})[test_id]

                    return (True, ''), {"output": stdout.getvalue().strip(), 
                            "error": stderr.getvalue().strip(), 
                            "logs": logs}

                except Exception:
                    return (True, ''), {"error": f"Error: {traceback.format_exc()}\n\nSTDERR: {stderr.getvalue().strip()}",
                            "output": stdout.getvalue().strip()}
        except:
            return (False, traceback.format_exc()), None


    @rpyc.exposed
    def execute(self, command: str) -> Tuple[Tuple[bool, str], Optional[Dict[str, Any]]]:
        """execute arbitrary code"""
        try:
            assert self.engine is not None, "should register FUT before test"
            with CaptureOutput() as (stdout, stderr):
                try:
                    self.engine.compile_and_exec(command.strip())
                    return (True, ''), {"output": stdout.getvalue().strip(), 
                            "error": stderr.getvalue().strip()} 

                except Exception:
                    return (True, ''), {"error": f"Error: {traceback.format_exc()}\n\nSTDERR: {stderr.getvalue().strip()}",
                            "output": stdout.getvalue().strip()}
        except:
            return (False, traceback.format_exc()), None

    @rpyc.exposed
    def stop_server(self):
        server_stop_event.set()

server_stop_event = Event()


def start_server(port: int, repo_id: str, repo_dir: str, result_dir: str, verbose: bool = False):
    server = ThreadPoolServer(R2EService(repo_id = repo_id,
                                         repo_dir=Path(repo_dir).absolute(), 
                                         result_dir=Path(result_dir).absolute(),
                                         verbose=verbose), port=port)
    if verbose:
        print(f"Server on {port} created!")

    # Run the server and wait for a stop event
    server_thread = Thread(target=server.start)
    server_thread.start()
    if verbose:
        print(f"Server on {port} started!")
    server_stop_event.wait()

    # Once received, close the server and join the thread
    server.close()
    server_thread.join()
    if verbose:
        print("Server stopped")


if __name__ == "__main__":
    start_server(3006, 'google___jax', '/repos', '/results')
