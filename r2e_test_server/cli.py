from typing import List, Optional, Set
import rpyc, fire
from r2e_test_server.server import R2EService, start_server

def retrieve_conn(host, port):
    return rpyc.connect(host, port)

class R2EServer:

    def start(self,
              repo_id: str = 'zeta',
              port: int = 3006, 
              repo_dir: str = '/repos',
              result_dir: str = '/results',
              verbose: bool = False):
        print(f"Starting R2E server on port {port}...")
        start_server(port=port, 
                     repo_id=repo_id,
                     repo_dir=repo_dir, 
                     result_dir=result_dir,
                     verbose=verbose)

    def register_fut(self, fut_id: str, module_path: str,
                     host: str = 'localhost',
                     port: int = 3006):
        service: R2EService = retrieve_conn(host, port).root
        R2EServer.Helper.print_result("eval_patch", R2EServer.Helper.ensure_success(
            service.register_fut(fut_id, module_path)))

    def tests(self, 
              host: str = 'localhost',
              port: int = 3006):
        service: R2EService = retrieve_conn(host, port).root
        R2EServer.Helper.print_result("tests", service.get_tests())

    def patchs(self, 
             host: str = 'localhost',
             port: int = 3006):
        service: R2EService = retrieve_conn(host, port).root
        R2EServer.Helper.print_result("patchs", service.get_futs())

    # NOTE: patch should be a whole new python file
    def submit_patch(self, 
             patch_id: str,
             patch_path: str,
             imm_eval: bool = False,
             host: str = 'localhost',
             port: int = 3006):
        service: R2EService = retrieve_conn(host, port).root
        result = service.submit_patch(patch_id=patch_id, patch_path=patch_path, imm_eval=imm_eval)

        if imm_eval:
            R2EServer.Helper.print_result("eval_patch", 
                  R2EServer.Helper.ensure_success(result))

    # NOTE: patch should be a whole new python file
    def eval_patch(self,
                   test_id: str,
                   patch_version: str,
                   host: str = 'localhost',
                   port: int = 3006):
        #assert eval_all or patch_version != None, "At least give one of the patchs to test"
        service: R2EService = retrieve_conn(host, port).root
        R2EServer.Helper.print_result("eval_patch", 
                                      R2EServer.Helper.ensure_success(
                                          service.eval_patch(test_id=test_id, 
                                                             patch_id=patch_version)))

    def register_test(self,
                      test_file: str,
                      test_id: Optional[str] = None,
                      test_type: Optional[str] = None,
                      imm_eval: bool = False,
                      host: str = 'localhost',
                      port: int = 3006):
        service: R2EService = retrieve_conn(host, port).root
        with open(test_file) as f:
            test_content = f.read()
        result = R2EServer.Helper.ensure_success(service.register_test(
                              test_content,
                              test_id=test_id,
                              test_type=test_type,
                              imm_eval=imm_eval))
        if imm_eval:
            R2EServer.Helper.print_result("eval_patch", result)

    def eval_test(self,
                  test_id: str,
                  inst_mask: Optional[Set[str]] = None,
                  host: str = 'localhost',
                  port: int = 3006):
        service: R2EService = retrieve_conn(host, port).root
        R2EServer.Helper.print_result("eval_test", 
                                      R2EServer.Helper.ensure_success(
                                          service.eval_test(test_id=test_id,
                                                            inst_mask=inst_mask)))

    def execute(self,
                code: str,
                host: str = 'localhost',
                port: int = 3006):
        service: R2EService = retrieve_conn(host, port).root
        R2EServer.Helper.print_result("execute", 
                                      R2EServer.Helper.ensure_success(service.execute(code)))

    def restore(self,
                host: str = 'localhost',
                port: int = 3006):
        service: R2EService = retrieve_conn(host, port).root
        service.restore()


    def stop(self,
             host: str = 'localhost',
             port: int = 3006):
        conn = retrieve_conn(host, port)
        server: R2EService = conn.root
        if not server.is_restored():
            server.restore()
        server.stop()
        #conn.close()

    class Helper:
        @staticmethod
        def print_result(op: str, result: dict):
            print('@'*20)
            print('   ' + op)
            print('@'*20)
            for result_id in result:
                print(result_id, "------------>")
                print(result[result_id])
        
        @staticmethod
        def ensure_success(res):
            assert res[0][0], res[0][1]
            return res[1]

def CLI():
    fire.Fire(R2EServer)

if __name__ == '__main__':
    CLI()
