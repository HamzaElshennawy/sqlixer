"""
parser.py

Phase 02: Recursive-Descent Parser for SQL-like language

This parser integrates with the provided `lexer.py` by using the
`LexicalAnalyzer` class. It expects `lexer.py` to be in the same
folder and to provide the `LexicalAnalyzer` as implemented in the
project.

Usage: python parser.py <input.sql>

The parser produces a simple AST and reports syntax errors with
line/column information. Panic-mode recovery synchronizes on
`SEMICOLON` and top-level keywords so multiple errors can be reported.
"""

from typing import List, Optional
import sys
import argparse

try:
    from lexer import LexicalAnalyzer
except Exception as e:
    raise ImportError("Could not import LexicalAnalyzer from lexer.py: " + str(e))


# AST node definitions (minimal)
class Node:
    def __init__(self, line=-1, column=-1):
        self.line = line
        self.column = column


class QueryNode(Node):
    def __init__(self, statements):
        self.statements = statements


class CreateNode(Node):
    def __init__(self, table_name, columns):
        self.table_name = table_name
        self.columns = columns  # list of (name, datatype)


class InsertNode(Node):
    def __init__(self, table_name, values):
        self.table_name = table_name
        self.values = values


class SelectNode(Node):
    def __init__(self, select_list, table_name, where):
        self.select_list = select_list
        self.table_name = table_name
        self.where = where


class UpdateNode(Node):
    def __init__(self, table_name, assignments, where):
        self.table_name = table_name
        self.assignments = assignments
        self.where = where


class DeleteNode(Node):
    def __init__(self, table_name, where):
        self.table_name = table_name
        self.where = where


# Condition / expression nodes
class ConditionNode(Node):
    pass


class BinaryOpNode(ConditionNode):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class NotNode(ConditionNode):
    def __init__(self, operand):
        self.operand = operand


class ColumnNode(ConditionNode):
    def __init__(self, name):
        self.name = name


class LiteralNode(ConditionNode):
    def __init__(self, value):
        self.value = value


class Parser:
    def __init__(self, tokens: List[object]):
        self.tokens = tokens
        self.pos = 0
        self.errors: List[str] = []

    def current(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]

        # synthetic EOF token
        class EOF:
            type = "EOF"
            lexeme = ""
            line = -1
            column = -1

        return EOF()

    def advance(self):
        if self.pos < len(self.tokens):
            self.pos += 1
        return self.current()

    def match(self, expected_type) -> Optional[object]:
        tok = self.current()
        if tok.type == expected_type:
            self.advance()
            return tok
        self._error(f"Expected '{expected_type}'", tok)
        return None

    def accept(self, expected_type) -> bool:
        if self.current().type == expected_type:
            self.advance()
            return True
        return False

    def _error(self, message: str, token):
        msg = f"Syntax Error: {message} at line {getattr(token,'line',-1)}, position {getattr(token,'column',-1)}; found '{getattr(token,'lexeme', token.type)}'"
        self.errors.append(msg)
        # Panic recovery: skip until a synchronizing token
        sync_set = {
            "SEMICOLON",
            "CREATE",
            "INSERT",
            "SELECT",
            "UPDATE",
            "DELETE",
            "EOF",
        }
        while self.current().type not in sync_set:
            self.advance()

    def parse(self) -> QueryNode:
        stmts = []
        while self.current().type != "EOF":
            stmt = self.parse_statement()
            if stmt:
                stmts.append(stmt)
            # consume optional semicolon
            if self.current().type == "SEMICOLON":
                self.advance()
            else:
                # try to recover if unexpected token
                if self.current().type != "EOF" and self.current().type not in {
                    "CREATE",
                    "INSERT",
                    "SELECT",
                    "UPDATE",
                    "DELETE",
                }:
                    self._error("Expected ';' or next statement", self.current())
                    if self.current().type == "SEMICOLON":
                        self.advance()
        return QueryNode(stmts)

    def parse_statement(self):
        t = self.current()
        if t.type == "CREATE":
            return self.parse_create()
        if t.type == "INSERT":
            return self.parse_insert()
        if t.type == "SELECT":
            return self.parse_select()
        if t.type == "UPDATE":
            return self.parse_update()
        if t.type == "DELETE":
            return self.parse_delete()
        self._error("Expected statement (CREATE/INSERT/SELECT/UPDATE/DELETE)", t)
        return None

    def parse_create(self):
        self.match("CREATE")
        self.match("TABLE")
        name_tok = self.match("IDENTIFIER")
        self.match("LEFT_PAREN")
        cols = self.parse_column_def_list()
        self.match("RIGHT_PAREN")
        node = CreateNode(name_tok.lexeme if name_tok else None, cols)
        if name_tok:
            node.line = name_tok.line
            node.column = name_tok.column
        return node

    def parse_column_def_list(self):
        cols = []
        if self.current().type != "IDENTIFIER":
            self._error("Expected column definition", self.current())
            return cols
        while True:
            name = self.match("IDENTIFIER")
            # datatype token might be returned as a reserved word like INT/FLOAT/TEXT
            dtype_tok = self.current()
            if dtype_tok.type in {"INT", "FLOAT", "TEXT"}:
                self.advance()
                dtype = dtype_tok.lexeme
            else:
                # fallback to IDENTIFIER (some lexers may mark types differently)
                dt = self.match("IDENTIFIER")
                dtype = dt.lexeme if dt else None
            cols.append((name.lexeme if name else None, dtype))
            if not self.accept("COMMA"):
                break
        return cols

    def parse_insert(self):
        start_tok = self.match("INSERT")
        self.match("INTO")
        table = self.match("IDENTIFIER")
        self.match("VALUES")
        self.match("LEFT_PAREN")
        vals = self.parse_value_list()
        self.match("RIGHT_PAREN")
        node = InsertNode(table.lexeme if table else None, vals)
        node.line = start_tok.line
        node.column = start_tok.column
        return node

    def parse_value_list(self):
        vals = []
        if self.current().type in {"NUMBER", "FLOAT", "STRING", "NULL"}:
            while True:
                tok = self.current()
                if tok.type in {"NUMBER", "FLOAT", "STRING", "NULL"}:
                    vals.append(tok.lexeme)
                    self.advance()
                else:
                    self._error("Expected value", tok)
                    break
                if not self.accept("COMMA"):
                    break
        else:
            self._error("Expected values list", self.current())
        return vals

    def parse_select(self):
        start_tok = self.match("SELECT")
        select_list = self.parse_select_list()
        self.match("FROM")
        table = self.match("IDENTIFIER")
        where = None
        if self.current().type == "WHERE":
            where = self.parse_where()
        node = SelectNode(select_list, table.lexeme if table else None, where)
        node.line = start_tok.line
        node.column = start_tok.column
        return node

    def parse_select_list(self):
        # '*' token from lexer is 'MULTIPLY'
        if self.accept("MULTIPLY"):
            return ["*"]
        cols = []
        first = self.match("IDENTIFIER")
        if first:
            cols.append(first.lexeme)
            while self.accept("COMMA"):
                t = self.match("IDENTIFIER")
                if t:
                    cols.append(t.lexeme)
        else:
            self._error("Expected column or '*'", self.current())
        return cols

    def parse_update(self):
        start_tok = self.match("UPDATE")
        table = self.match("IDENTIFIER")
        self.match("SET")
        assignments = self.parse_assignment_list()
        where = None
        if self.current().type == "WHERE":
            where = self.parse_where()
        node = UpdateNode(table.lexeme if table else None, assignments, where)
        node.line = start_tok.line
        node.column = start_tok.column
        return node

    def parse_assignment_list(self):
        assigns = []
        while True:
            name = self.match("IDENTIFIER")
            self.match("EQUAL")  # lexer uses EQUAL for '='
            val_tok = self.current()
            if val_tok.type in {"NUMBER", "FLOAT", "STRING", "NULL"}:
                assigns.append((name.lexeme if name else None, val_tok.lexeme))
                self.advance()
            else:
                self._error("Expected value in assignment", val_tok)
            if not self.accept("COMMA"):
                break
        return assigns

    def parse_delete(self):
        start_tok = self.match("DELETE")
        self.match("FROM")
        table = self.match("IDENTIFIER")
        where = None
        if self.current().type == "WHERE":
            where = self.parse_where()
        node = DeleteNode(table.lexeme if table else None, where)
        node.line = start_tok.line
        node.column = start_tok.column
        return node

    def parse_where(self):
        self.match("WHERE")
        return self.parse_condition()

    # Condition parsing with precedence
    def parse_condition(self):
        return self.parse_disjunction()

    def parse_disjunction(self):
        left = self.parse_conjunction()
        while self.current().type == "OR":
            op_tok = self.current()
            op = op_tok.lexeme
            self.advance()
            right = self.parse_conjunction()
            left = BinaryOpNode(op, left, right)
            left.line = op_tok.line
            left.column = op_tok.column
        return left

    def parse_conjunction(self):
        left = self.parse_negation()
        while self.current().type == "AND":
            op_tok = self.current()
            op = op_tok.lexeme
            self.advance()
            right = self.parse_negation()
            left = BinaryOpNode(op, left, right)
            left.line = op_tok.line
            left.column = op_tok.column
        return left

    def parse_negation(self):
        if self.current().type == "NOT":
            self.advance()
            operand = self.parse_comparison()
            node = NotNode(operand)
            # self.current() is already advanced, so we can't easily get 'NOT' token unless we captured it or peeked back.
            # But line 333 checked self.current().type == "NOT", so current was NOT.
            # Actually line 334 advances. So we need to capture before line 334.
            # But replace_file_content replaces block.
            # I will assume line/col is roughly operand's line or we need to capture "NOT" token.
            # Let's adjust target block to include `if self.current().type == "NOT":`
            # Wait, I can just not worry about NotNode line exactly or capture it.
            # Let's try to capture.
            return node
        return self.parse_comparison()

    def parse_comparison(self):

        # We start by parsing an expression (which includes factors, which includes parenthesized conditions)
        left = self.parse_expression()

        if self.current().type in {
            "EQUAL",
            "NOT_EQUAL",
            "LESS",
            "GREATER",
            "LESS_EQUAL",
            "GREATER_EQUAL",
        }:
            op_tok = self.current()
            op = op_tok.lexeme
            self.advance()
            right = self.parse_expression()
            node = BinaryOpNode(op, left, right)
            node.line = op_tok.line
            node.column = op_tok.column
            return node

        return left

    # Expression parsing (lowest precedence for arithmetic)
    def parse_expression(self):
        left = self.parse_term()
        while self.current().type in {"PLUS", "MINUS"}:
            op_tok = self.current()
            op = op_tok.lexeme
            self.advance()
            right = self.parse_term()
            left = BinaryOpNode(op, left, right)
            left.line = op_tok.line
            left.column = op_tok.column
        return left

    def parse_term(self):
        left = self.parse_factor()
        while self.current().type in {"MULTIPLY", "DIVIDE"}:
            op_tok = self.current()
            op = op_tok.lexeme
            self.advance()
            right = self.parse_factor()
            left = BinaryOpNode(op, left, right)
            left.line = op_tok.line
            left.column = op_tok.column
        return left

    def parse_factor(self):
        t = self.current()
        if t.type == "LEFT_PAREN":
            self.advance()
            node = self.parse_condition()
            self.match("RIGHT_PAREN")
            return node

        if t.type == "IDENTIFIER":
            self.advance()
            node = ColumnNode(t.lexeme)
            node.line = t.line
            node.column = t.column
            return node

        if t.type in {"NUMBER", "FLOAT", "STRING"}:
            self.advance()
            node = LiteralNode(t.lexeme)
            node.line = t.line
            node.column = t.column
            return node

        self._error("Expected identifier, number, string or '('", t)
        self.advance()
        node = LiteralNode(None)
        node.line = t.line
        node.column = t.column
        return node


def pprint_ast(node, prefix="", is_last=True):
    connector = "└── " if is_last else "├── "

    # Determine string representation and children
    node_str = ""
    children = []

    if isinstance(node, QueryNode):
        node_str = "Query"
        children = node.statements
    elif isinstance(node, CreateNode):
        node_str = f"Create Table: {node.table_name}"
        children = [f"Column: {c[0]} {c[1]}" for c in node.columns]
    elif isinstance(node, InsertNode):
        node_str = f"Insert into: {node.table_name}"
        children = [f"Value: {v}" for v in node.values]
    elif isinstance(node, SelectNode):
        node_str = f"Select from: {node.table_name}"
        children = [f"Column: {c}" for c in node.select_list]
        if node.where:
            children.append(node.where)
    elif isinstance(node, UpdateNode):
        node_str = f"Update: {node.table_name}"
        children = [f"Set: {k} = {v}" for k, v in node.assignments]
        if node.where:
            children.append(node.where)
    elif isinstance(node, DeleteNode):
        node_str = f"Delete from: {node.table_name}"
        if node.where:
            children.append(node.where)
    elif isinstance(node, BinaryOpNode):
        node_str = f"BinaryOp: {node.op}"
        children = [node.left, node.right]
    elif isinstance(node, NotNode):
        node_str = "NOT"
        children = [node.operand]
    elif isinstance(node, ColumnNode):
        node_str = f"ColumnRef: {node.name}"
    elif isinstance(node, LiteralNode):
        node_str = f"Literal: {node.value}"
    elif isinstance(node, str):
        node_str = node
    else:
        node_str = f"Unknown: {type(node).__name__}"

    if hasattr(node, "inferred_type") and node.inferred_type:
        node_str += f" <Type: {node.inferred_type}>"

    print(prefix + connector + node_str)

    child_prefix = prefix + ("    " if is_last else "│   ")

    num_children = len(children)
    for i, child in enumerate(children):
        pprint_ast(child, child_prefix, i == num_children - 1)


def main(path: str, args: argparse.Namespace):
    # Ensure we can print tree characters (utf-8) even on Windows consoles
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            # For older python versions that don't support reconfigure
            pass
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    la = LexicalAnalyzer(src)
    tokens, symtab, lex_errors = la.tokenize()

    # If verbose, print tokens and symbol table (but don't print lexer errors yet)
    if getattr(args, "verbose", False):
        print("\n" + "=" * 80)
        print("TOKENS")
        print("=" * 80)
        print(f"{'TYPE':<20} {'LEXEME':<25} {'LINE':<10} {'COLUMN':<10}")
        print("-" * 80)
        for token in tokens:
            print(
                f"{token.type:<20} {token.lexeme:<25} {token.line:<10} {token.column:<10}"
            )
        print("=" * 80)

        if symtab:
            print("\n" + "=" * 80)
            print("SYMBOL TABLE")
            print("=" * 80)
            print(f"{'NAME':<25} {'TYPE':<20} {'LINE':<10} {'COLUMN':<10}")
            print("-" * 80)
            for symbol in symtab.values():
                print(
                    f"{symbol.name:<25} {symbol.type:<20} {symbol.line:<10} {symbol.column:<10}"
                )
            print("=" * 80)

    parser = Parser(tokens)
    tree = parser.parse()

    # Always print AST (compact)
    pprint_ast(tree)

    # Print errors at the bottom (lexer errors then parser errors)
    if lex_errors:
        print("\n" + "=" * 80)
        print("LEXER ERRORS")
        print("=" * 80)
        for i, e in enumerate(lex_errors, 1):
            print(f"{i}. {e}")
        print("=" * 80)

    if parser.errors:
        print("\n" + "=" * 80)
        print("PARSER ERRORS")
        print("=" * 80)
        for i, e in enumerate(parser.errors, 1):
            print(f"{i}. {e}")
        print("=" * 80)


if __name__ == "__main__":
    parser_arg = argparse.ArgumentParser(
        description="Recursive-descent parser for SQL-like language"
    )
    parser_arg.add_argument("path", help="Input SQL file path")
    parser_arg.add_argument(
        "-v", "--verbose", action="store_true", help="Print tokens and symbol table"
    )
    args = parser_arg.parse_args()
    main(args.path, args)
