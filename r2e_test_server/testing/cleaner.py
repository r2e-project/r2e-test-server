import re
import ast

from r2e_test_server.ast.transformer import ImportAliasReplacer


class R2ETestCleaner:

    @staticmethod
    def clean_test_case(test_case: str, fut_name: str, ref_fut_name: str) -> str:
        """Clean the generated test case.

        Args:
            test_case (str): The generated test case.
            fut_name (str): The name of the function under test.
            ref_fut_name (str): The name of the reference function under test.

        Returns:
            str: The cleaned test case.
        """

        tree = ast.parse(test_case)
        cleaned_tree = ast.Module(body=[], type_ignores=[])
        tree = ImportAliasReplacer(tree, names=[fut_name, ref_fut_name]).transform()

        cleaned_tree.body = [
            node
            for node in tree.body
            if not R2ETestCleaner._should_skip_node(node, fut_name, ref_fut_name)
        ]

        cleaned_generated_test = ast.unparse(cleaned_tree)
        cleaned_generated_test = re.sub(
            r"unittest\.main\(\)", "pass", cleaned_generated_test
        )
        cleaned_generated_test = re.sub(
            r"(your_module\.|original_module\.)", "fut_module.", cleaned_generated_test
        )

        return cleaned_generated_test

    @staticmethod
    def _should_skip_node(node, fut_name, ref_fut_name):
        """helper: checks if a node in the generated test's AST should be skipped"""
        aliases_fut_or_reference = lambda node: any(
            alias.name in [fut_name, ref_fut_name] for alias in node.names
        )

        if isinstance(node, ast.Import) and aliases_fut_or_reference(node):
            return True

        if isinstance(node, ast.ImportFrom):

            if node.module is not None and "fut_module" in node.module:
                return True

            elif node.module in [fut_name, ref_fut_name]:
                return True

            elif aliases_fut_or_reference(node):
                return True

        if isinstance(node, ast.FunctionDef) and node.name in [fut_name, ref_fut_name]:
            return True

        return False
