import ast


class ASTTransformer(ast.NodeTransformer):
    """Base class for AST transformer."""

    def __init__(self, tree: ast.Module):
        self.tree = tree

    def transform(self):
        return super().visit(self.tree)


class ImportAliasReplacer(ASTTransformer):
    """Replace aliases of imports with original name in the code.

    Args:
        tree (ast.Module): AST tree of the code.
        names (list[str]): list of original names to be used in the code.
    """

    def __init__(self, tree: ast.Module, names: list[str]):
        super().__init__(tree)
        self.aliases = self.get_all_aliases(names)

    def get_all_aliases(self, names: list[str]) -> dict:
        aliases = {}
        for node in self.tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:

                    # if alias is used and it is not same as name
                    if alias.asname and alias.asname not in names:

                        # replace alias with name itself
                        if alias.name in names:
                            aliases[alias.asname] = alias.name

        return aliases

    def visit_Name(self, node):
        if node.id in self.aliases:
            return ast.copy_location(
                ast.Name(id=self.aliases[node.id], ctx=node.ctx), node
            )
        return node


class RemoveFunctionTransformer(ASTTransformer):
    """Remove a function from the code.

    Args:
        tree (ast.Module): AST tree of the code.
        function_name (str): the name of the function to remove
    """

    def __init__(self, tree: ast.Module, function_name: str):
        super().__init__(tree)
        self.function_name = function_name

    def visit_FunctionDef(self, node):
        if node.name == self.function_name:
            # Remove the function by returning None
            return None
        return node


# import ast


class RemoveLastNodeTransformer(ASTTransformer):
    """Remove the last ast node from code.

    Args:
        tree (ast.Module): AST tree of the code.
    """

    def __init__(self, tree: ast.Module):
        super().__init__(tree)

    def visit_Module(self, node):

        if isinstance(node.body[-1], ast.ClassDef):
            if len(node.body[-1].body) == 1:
                node.body.pop()
            else:
                node.body[-1].body.pop()
        else:
            node.body.pop()

        return node
