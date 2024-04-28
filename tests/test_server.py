import json
import unittest

from r2e_test_server.server import R2EService


function_code = '''def get_funclass_globals(
    func_class_ast: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> list[str]:
    """
    extract all the global variables accessed in the function
    uses the bytecode to extract the global variables
        - finds the LOAD_CONST instructions
        - finds the global variables in the constants using LOAD_GLOBAL
    :param func_class_ast: ast.FunctionDef
    :return: list[str] - list of global variables accessed
    """
    # we need ast.Module to compile and get this to work
    # so we will parse and unparse the function to get the module
    func_class_ast_str = ast.unparse(func_class_ast)
    module_ast = build_ast(func_class_ast_str, add_parents=False)
    module_ast = build_ast(ast.unparse(module_ast), add_parents=False)

    try:
        module_ast_compiled = compile(ast.unparse(module_ast), "<string>", "exec")
    except SyntaxError:
        print(f"Syntax error in {ast.unparse(module_ast)}")
        return []

    module_bytecode = dis.Bytecode(module_ast_compiled)

    global_access_symbols = []
    for instruction in module_bytecode:
        if instruction.opname == "LOAD_CONST":
            if isinstance(instruction.argval, types.CodeType):
                code = instruction.argval
                global_access_symbols.extend(handle_const_code(module_ast, code))

    function_name = func_class_ast.name
    global_access_symbols = [
        symbol for symbol in global_access_symbols if symbol != function_name
    ]
    return global_access_symbols
'''

test_bytecode_globals = '''
import ast
import unittest
from fut_module import get_funclass_globals, reference_get_funclass_globals

code = """def f():
    a = b

    class A(B):
        
        def __init__(self, a, b):
            super().__init__(a)
            self.a = a + temp
            self.b = b

        
        def x(self, value):
            print("setter of x called")
            self._x = value + temp

    return a + b + new_var"""

class TestByteCodeGlobalsFinder(unittest.TestCase):
    def test1(self):
        func_ast = ast.parse(code).body[0]
        global_vars = get_funclass_globals(func_ast)
        ref_global_vars = reference_get_funclass_globals(func_ast)
        self.assertEqual(global_vars, ref_global_vars)

'''

test_topsort = """
import unittest
from r2e.models.file import File
from r2e.models.repo import Repo
from r2e.models.module import Module
from r2e.models.identifier import Identifier

class TestDependencyGraphEquivalence(unittest.TestCase):
    def setUp(self):
        # Setup a mock repository and file structure
        self.repo = Repo(repo_org="/fake/repo", repo_name="fake_repo", repo_id="fake_repo", local_repo_path="/fake/repo")
        
        # Create files with mock content
        self.file1 = File(file_module=Module(module_id=Identifier(identifier="module1"), repo=self.repo))
        self.file2 = File(file_module=Module(module_id=Identifier(identifier="module2"), repo=self.repo))
        self.file3 = File(file_module=Module(module_id=Identifier(identifier="module3"), repo=self.repo))

        # Create AstStatements for each file
        self.stmt1 = AstStatement(stmt=None, idx=0, file=self.file1, orig_stmt=None, orig_stmt_idx=0)
        self.stmt2 = AstStatement(stmt=None, idx=1, file=self.file2, orig_stmt=None, orig_stmt_idx=1)
        self.stmt3 = AstStatement(stmt=None, idx=2, file=self.file3, orig_stmt=None, orig_stmt_idx=2)

    def test_topological_file_sort_equivalence(self):
        # Create DependencyGraph and ReferenceDependencyGraph instances
        dg = DependencyGraph(inputstmts=[self.stmt1])
        rdg = reference_DependencyGraph(inputstmts=[self.stmt1])

        # Add edges to simulate dependencies
        dg.add_edge(self.stmt1, self.stmt2, "uses")
        dg.add_edge(self.stmt2, self.stmt3, "calls")
        rdg.add_edge(self.stmt1, self.stmt2, "uses")
        rdg.add_edge(self.stmt2, self.stmt3, "calls")

        # Get topological sorts from both graphs
        result_dg = dg.topological_file_sort()
        result_rdg = rdg.topological_file_sort()

        # Check if the outputs are equivalent
        self.assertEqual(result_dg, result_rdg)

if __name__ == '__main__':
    unittest.main()
"""

gpt4_codegen = '''def get_funclass_globals(
    func_class_ast: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> list[str]:
    """
    Extract all the global variables accessed in the function or class.
    It uses the bytecode to extract the global variables by:
        - Finding the LOAD_CONST instructions.
        - Finding the global variables in the constants using LOAD_GLOBAL.
    :param func_class_ast: Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef]
    :return: list[str] - list of global variables accessed
    """
    module_ast = build_ast(ast.unparse(func_class_ast))
    code_obj = func_class_ast.body[0].body[0].value.code if isinstance(func_class_ast, ast.ClassDef) else func_class_ast.body[0].value.code
    return handle_const_code(module_ast, code_obj)
'''

test_handle_const_node = '''
import ast
import dis
import unittest
from fut_module import handle_const_code, reference_handle_const_code

code = """def f():
    a = b

    class A(B):
        
        def __init__(self, a, b):
            super().__init__(a)
            self.a = a + temp
            self.b = b

        
        def x(self, value):
            print("setter of x called")
            self._x = value + temp

    return a + b + new_var"""

class TestHandleConstant(unittest.TestCase):
    def test_handle_const(self):
        func_ast = ast.parse(code)
        func_ast_compiled = compile(func_ast, "<string>", "exec")

        bytecode = dis.Bytecode(func_ast_compiled)

        for instr in bytecode:
            if instr.opname == "LOAD_CONST":
                if isinstance(instr.argval, types.CodeType):
                    const_code = instr.argval
                    global_vars = handle_const_code(func_ast, const_code)
                    ref_global_vars = reference_handle_const_code(func_ast, const_code)
                    self.assertEqual(global_vars, ref_global_vars)

'''


class TestR2EService(unittest.TestCase):

    def test_self_equiv(self):
        service = R2EService()
        data = {"repo_name": "r2e-internal", "repo_path": "../r2e-internal"}
        data = json.dumps(data)
        service.setup_repo(data)

        data = {
            "funclass_names": ["get_funclass_globals"],
            "file_path": "../r2e-internal/r2e/pat/dependency_slicer/globals_finder/bytecode_globals.py",
        }
        data = json.dumps(data)
        service.setup_function(data)

        data = {"generated_tests": {"test_1": test_bytecode_globals}}
        data = json.dumps(data)
        service.setup_test(data)

        out = service.setup()
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute("submit")
        self.assertEqual(out["output"], "")
        logs = json.loads(out["logs"])
        self.assertTrue(logs["run_tests_logs"]["test_1"]["valid"])

    def test_gpt4_codegen(self):
        service = R2EService()
        data = {"repo_name": "r2e-internal", "repo_path": "../r2e-internal"}
        data = json.dumps(data)
        service.setup_repo(data)

        data = {
            "funclass_names": ["get_funclass_globals"],
            "file_path": "../r2e-internal/r2e/pat/dependency_slicer/globals_finder/bytecode_globals.py",
        }
        data = json.dumps(data)
        service.setup_function(data)

        data = {"generated_tests": {"test_1": test_bytecode_globals}}
        data = json.dumps(data)
        service.setup_test(data)

        out = service.setup()
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute(gpt4_codegen)
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute("submit")
        self.assertEqual(out["output"], "")
        logs = json.loads(out["logs"])
        self.assertFalse(logs["run_tests_logs"]["test_1"]["valid"])

    def test_gpt4_agentic(self):
        service = R2EService()
        data = {"repo_name": "r2e-internal", "repo_path": "../r2e-internal"}
        data = json.dumps(data)
        service.setup_repo(data)

        data = {
            "funclass_names": ["get_funclass_globals"],
            "file_path": "../r2e-internal/r2e/pat/dependency_slicer/globals_finder/bytecode_globals.py",
        }
        data = json.dumps(data)
        service.setup_function(data)

        data = {"generated_tests": {"test_1": test_bytecode_globals}}
        data = json.dumps(data)
        service.setup_test(data)

        out = service.setup()
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute(f"code = 'def f(): return a+b'")
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute(f"code_ast = ast.parse(code)")
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute(
            f"code_obj = dis.Bytecode(compile(code, '<string>', 'exec'))"
        )
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute("symbols = []")
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute(
            """for instr in code_obj: 
                    if instr.opname == "LOAD_CONST":
                        if isinstance(instr.argval, types.CodeType):
                            const_code = instr.argval
                            symbols.extend(handle_const_code(code_ast, const_code))"""
        )
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute("print(symbols)")
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "['a', 'b']")

        fixed_gpt_code = function_code  # simulating: new attempt to fix the code
        out = service.exposed_execute(fixed_gpt_code)
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute("submit")
        self.assertEqual(out["output"], "")
        logs = json.loads(out["logs"])
        self.assertTrue(logs["run_tests_logs"]["test_1"]["valid"])

    def test_gpt4_repair_codegen(self):
        service = R2EService()
        data = {"repo_name": "r2e-internal", "repo_path": "../r2e-internal"}
        data = json.dumps(data)
        service.setup_repo(data)

        data = {
            "funclass_names": ["get_funclass_globals"],
            "file_path": "../r2e-internal/r2e/pat/dependency_slicer/globals_finder/bytecode_globals.py",
            "function_code": function_code,
        }
        data = json.dumps(data)
        service.setup_function(data)

        data = {"generated_tests": {"test_1": test_bytecode_globals}}
        data = json.dumps(data)
        service.setup_test(data)

        out = service.setup()
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute(gpt4_codegen)
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute("submit")
        self.assertEqual(out["output"], "")
        logs = json.loads(out["logs"])
        self.assertFalse(logs["run_tests_logs"]["test_1"]["valid"])

        out = service.exposed_execute(function_code)
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute("submit")
        self.assertEqual(out["output"], "")
        logs = json.loads(out["logs"])
        self.assertTrue(logs["run_tests_logs"]["test_1"]["valid"])

    def test_classmethod_selfequiv(self):
        service = R2EService()
        data = {"repo_name": "r2e-internal", "repo_path": "../r2e-internal"}
        data = json.dumps(data)
        service.setup_repo(data)

        data = {
            "funclass_names": ["DependencyGraph"],
            "file_path": "../r2e-internal/r2e/pat/dependency_slicer/dependency_graph.py",
        }
        data = json.dumps(data)
        service.setup_function(data)

        data = {"generated_tests": {"test_1": test_topsort}}
        data = json.dumps(data)
        service.setup_test(data)

        out = service.setup()
        # self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute("submit")
        self.assertEqual(out["output"], "")
        logs = json.loads(out["logs"])
        self.assertTrue(logs["run_tests_logs"]["test_1"]["valid"])

    def test_multifunction(self):
        service = R2EService()
        data = {"repo_name": "r2e-internal", "repo_path": "../r2e-internal"}
        data = json.dumps(data)
        service.setup_repo(data)

        data = {
            "funclass_names": [
                "compare_locations",
                "build_id_to_nodes",
                "get_argument_names",
                "handle_const_code",
            ],
            "file_path": "../r2e-internal/r2e/pat/dependency_slicer/globals_finder/bytecode_globals.py",
        }
        data = json.dumps(data)
        service.setup_function(data)

        data = {"generated_tests": {"test_1": test_handle_const_node}}
        data = json.dumps(data)
        service.setup_test(data)

        out = service.setup()
        self.assertEqual(out["error"], "")
        self.assertEqual(out["output"], "")

        out = service.exposed_execute("submit")
        self.assertEqual(out["output"], "")
        logs = json.loads(out["logs"])
        json.dump(logs, open("logs.json", "w"), indent=4)
        self.assertTrue(logs["run_tests_logs"]["test_1"]["valid"])
