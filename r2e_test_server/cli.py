from typing import Optional
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
        print(service.register_fut(fut_id, module_path))

    def tests(self, 
              host: str = 'localhost',
              port: int = 3006):
        service: R2EService = retrieve_conn(host, port).root
        R2EServer.Helper.print_result("tests", service.get_tests())

    def register_test(self,
                      test_file: str,
                      test_id: Optional[str] = None,
                      imm_eval: bool = False,
                      host: str = 'localhost',
                      port: int = 3006):
        service: R2EService = retrieve_conn(host, port).root
        with open(test_file) as f:
            test_content = f.read()
        result = service.register_test(test_content,
                              test_id=test_id,
                              imm_eval=imm_eval)
        if imm_eval:
            print(result)

    def eval_test(self,
                 test_id: str,
                 host: str = 'localhost',
                 port: int = 3006):
        service: R2EService = retrieve_conn(host, port).root
        R2EServer.Helper.print_result("eval_test", service.eval_test(test_id))


    def stop(self,
             host: str = 'localhost',
             port: int = 3006):
        conn = retrieve_conn(host, port)
        conn.root.stop_server()
        conn.close()

    class Helper:
        @staticmethod
        def print_result(op: str, result: dict):
            print('@'*20)
            print('   ' + op)
            print('@'*20)
            for result_id in result:
                print(result_id, "------------>")
                print(result[result_id])

def CLI():
    fire.Fire(R2EServer)

if __name__ == '__main__':
    CLI()
