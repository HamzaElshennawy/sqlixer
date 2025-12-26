import sys
from parser import (
    QueryNode,
    CreateNode,
    InsertNode,
    SelectNode,
    UpdateNode,
    DeleteNode,
    BinaryOpNode,
    NotNode,
    ColumnNode,
    LiteralNode,
)


class InternalSemanticError(Exception):
    def __init__(self, message, line=-1, column=-1):
        self.message = message
        self.line = line
        self.column = column


class SymbolTable:
    def __init__(self):
        # Dictionary to store tables: {table_name: {col_name: col_type}}
        self.tables = {}

    def create_table(self, table_name, columns, line, column):
        if table_name in self.tables:
            raise InternalSemanticError(
                f"Table '{table_name}' already exists.", line, column
            )

        self.tables[table_name] = {}
        for col_name, col_type in columns:
            if col_name in self.tables[table_name]:
                raise InternalSemanticError(
                    f"Duplicate column '{col_name}' in table '{table_name}'.",
                    line,
                    column,
                )
            self.tables[table_name][col_name] = col_type

    def get_table(self, table_name, line, column):
        if table_name not in self.tables:
            raise InternalSemanticError(
                f"Table '{table_name}' does not exist.", line, column
            )
        return self.tables[table_name]

    def get_column_type(self, table_name, col_name, line, column):
        table = self.get_table(table_name, line, column)
        if col_name not in table:
            raise InternalSemanticError(
                f"Column '{col_name}' does not exist in table '{table_name}'.",
                line,
                column,
            )
        return table[col_name]

    def __str__(self):
        output = []
        output.append("=" * 60)
        output.append("FINAL SYMBOL TABLE")
        output.append("=" * 60)
        output.append(f"{'TABLE':<20} {'COLUMN':<20} {'TYPE':<10}")
        output.append("-" * 60)
        for table_name, cols in self.tables.items():
            for col_name, col_type in cols.items():
                output.append(f"{table_name:<20} {col_name:<20} {col_type:<10}")
        output.append("=" * 60)
        return "\n".join(output)


class SemanticAnalyzer:
    def __init__(self):
        self.symtab = SymbolTable()
        self.errors = []
        # Context to track current table being operated on (for resolving column names)
        self.current_table = None

    def analyze(self, ast_root):
        try:
            self.visit(ast_root)
        except Exception as e:
            # Catch unexpected errors to prevent crash, though logic errors handled via error collection
            # But here we rely on visit methods appending to self.errors usually.
            # However, for fatal blockages we might just stop.
            pass
        return self.symtab, self.errors

    def error(self, msg, line=-1, column=-1):
        self.errors.append(f"Semantic Error: {msg} at line {line}, position {column}.")

    def visit(self, node):
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        raise Exception(f"No visit_{type(node).__name__} method")

    def visit_QueryNode(self, node):
        for stmt in node.statements:
            try:
                self.visit(stmt)
            except InternalSemanticError as e:
                self.error(e.message, e.line, e.column)
            self.current_table = None  # Reset context after each statement

    def visit_CreateNode(self, node):
        # Valid types check
        valid_types = {"INT", "FLOAT", "TEXT"}
        for col_name, col_type in node.columns:
            if col_type not in valid_types:
                raise InternalSemanticError(
                    f"Invalid column type '{col_type}'. Allowed: INT, FLOAT, TEXT",
                    node.line,
                    node.column,
                )

        self.symtab.create_table(node.table_name, node.columns, node.line, node.column)

    def visit_InsertNode(self, node):
        table_cols = self.symtab.get_table(node.table_name, node.line, node.column)
        expected_count = len(table_cols)
        provided_count = len(node.values)

        if provided_count != expected_count:
            raise InternalSemanticError(
                f"Column count mismatch. Table '{node.table_name}' has {expected_count} columns, but {provided_count} values were provided.",
                node.line,
                node.column,
            )

        # Type checking
        col_definitions = list(table_cols.items())  # ordered insertion
        for i, val in enumerate(node.values):
            col_name, col_type = col_definitions[i]
            # Val is a raw value from lexer (string). We need to guess type or check format.
            # Lexer returns strings for everything.
            # We need to infer type of literal `val`
            val_type = self._infer_type(val)
            if not self._is_compatible(col_type, val_type):
                raise InternalSemanticError(
                    f"Type mismatch for column '{col_name}'. Expected {col_type}, got {val_type} ('{val}')",
                    node.line,
                    node.column,
                )

    def visit_SelectNode(self, node):
        self.symtab.get_table(
            node.table_name, node.line, node.column
        )  # Check existence
        self.current_table = node.table_name

        # Check select list
        if node.select_list != ["*"]:
            for col in node.select_list:
                self.symtab.get_column_type(
                    node.table_name, col, node.line, node.column
                )

        if node.where:
            self.visit(node.where)

    def visit_UpdateNode(self, node):
        self.symtab.get_table(node.table_name, node.line, node.column)
        self.current_table = node.table_name

        for col_name, val in node.assignments:
            col_type = self.symtab.get_column_type(
                node.table_name, col_name, node.line, node.column
            )
            val_type = self._infer_type(val)
            if not self._is_compatible(col_type, val_type):
                raise InternalSemanticError(
                    f"Type mismatch in assignment for '{col_name}'. Expected {col_type}, got {val_type} ('{val}')",
                    node.line,
                    node.column,
                )

        if node.where:
            self.visit(node.where)

    def visit_DeleteNode(self, node):
        self.symtab.get_table(node.table_name, node.line, node.column)
        self.current_table = node.table_name
        if node.where:
            self.visit(node.where)

    def visit_BinaryOpNode(self, node):
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)

        if left_type != right_type and left_type is not None and right_type is not None:
            raise InternalSemanticError(
                f"Type mismatch in comparison/operation. Cannot compare {left_type} with {right_type}.",
                node.line,
                node.column,
            )
        return left_type  # Propagate type

    def visit_NotNode(self, node):
        return self.visit(node.operand)

    def visit_ColumnNode(self, node):
        if not self.current_table:
            raise InternalSemanticError(
                f"Column '{node.name}' used out of context (no table specified).",
                node.line,
                node.column,
            )
        # Annotate node with type
        node.inferred_type = self.symtab.get_column_type(
            self.current_table, node.name, node.line, node.column
        )
        return node.inferred_type

    def visit_LiteralNode(self, node):
        if node.value is None:
            return None
        node.inferred_type = self._infer_type(node.value)
        return node.inferred_type

    def _infer_type(self, value):
        if value.startswith("'") and value.endswith("'"):
            return "TEXT"
        try:
            int(value)
            return "INT"
        except ValueError:
            try:
                float(value)
                return "FLOAT"
            except ValueError:
                return "UNKNOWN"

    def _is_compatible(self, target_type, value_type):
        if target_type == value_type:
            return True
        if target_type == "FLOAT" and value_type == "INT":
            return True  # Allow int -> float distinction
        return False
