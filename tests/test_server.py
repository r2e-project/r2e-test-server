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

test = '''
import ast
import unittest
from fut_module import get_funclass_globals, ref_get_funclass_globals

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


class TestR2EService(unittest.TestCase):

    def test_self_equiv(self):
        service = R2EService()
        data = {"repo_name": "r2e-internal", "repo_path": "../r2e-internal"}
        data = json.dumps(data)
        service.setup_repo(data)

        data = {
            "function_name": "get_funclass_globals",
            "file_path": "../r2e-internal/r2e/pat/dependency_slicer/globals_finder/bytecode_globals.py",
            "function_code": function_code,
        }
        data = json.dumps(data)
        service.setup_function(data)

        data = {"generated_tests": {"test_1": test}}
        data = json.dumps(data)
        service.setup_test(data)

        out = service.setup()
        print(out)

        out = service.exposed_execute("submit")
        print(out)

    def test_gpt4_codegen(self):
        service = R2EService()
        data = {"repo_name": "r2e-internal", "repo_path": "../r2e-internal"}
        data = json.dumps(data)
        service.setup_repo(data)

        data = {
            "function_name": "get_funclass_globals",
            "file_path": "../r2e-internal/r2e/pat/dependency_slicer/globals_finder/bytecode_globals.py",
            "function_code": function_code,
        }
        data = json.dumps(data)
        service.setup_function(data)

        data = {"generated_tests": {"test_1": test}}
        data = json.dumps(data)
        service.setup_test(data)

        out = service.setup()
        print(out)

        out = service.exposed_execute(gpt4_codegen)
        print(out)

        out = service.exposed_execute("submit")
        print(out)

    def test_gpt4_agentic(self):
        service = R2EService()
        data = {"repo_name": "r2e-internal", "repo_path": "../r2e-internal"}
        data = json.dumps(data)
        service.setup_repo(data)

        data = {
            "function_name": "get_funclass_globals",
            "file_path": "../r2e-internal/r2e/pat/dependency_slicer/globals_finder/bytecode_globals.py",
            "function_code": function_code,
        }
        data = json.dumps(data)
        service.setup_function(data)

        data = {"generated_tests": {"test_1": test}}
        data = json.dumps(data)
        service.setup_test(data)

        out = service.setup()
        print(out)

        out = service.exposed_execute(f"code = 'def f(): return a+b'")
        print(out)

        out = service.exposed_execute(f"code_ast = ast.parse(code)")
        print(out)

        out = service.exposed_execute(
            f"code_obj = dis.Bytecode(compile(code, '<string>', 'exec'))"
        )
        print(out)

        out = service.exposed_execute(f"handle_const_code(code_ast, code_obj)")
        print(out)

        out = service.exposed_execute(gpt4_codegen)
        print(out)

        out = service.exposed_execute("submit")
        print(out)
