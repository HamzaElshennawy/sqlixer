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
    pass


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
        return CreateNode(name_tok.lexeme if name_tok else None, cols)

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
        self.match("INSERT")
        self.match("INTO")
        table = self.match("IDENTIFIER")
        self.match("VALUES")
        self.match("LEFT_PAREN")
        vals = self.parse_value_list()
        self.match("RIGHT_PAREN")
        return InsertNode(table.lexeme if table else None, vals)

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
        self.match("SELECT")
        select_list = self.parse_select_list()
        self.match("FROM")
        table = self.match("IDENTIFIER")
        where = None
        if self.current().type == "WHERE":
            where = self.parse_where()
        return SelectNode(select_list, table.lexeme if table else None, where)

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
        self.match("UPDATE")
        table = self.match("IDENTIFIER")
        self.match("SET")
        assignments = self.parse_assignment_list()
        where = None
        if self.current().type == "WHERE":
            where = self.parse_where()
        return UpdateNode(table.lexeme if table else None, assignments, where)

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
        self.match("DELETE")
        self.match("FROM")
        table = self.match("IDENTIFIER")
        where = None
        if self.current().type == "WHERE":
            where = self.parse_where()
        return DeleteNode(table.lexeme if table else None, where)

    def parse_where(self):
        self.match("WHERE")
        return self.parse_condition()

    # Condition parsing with precedence
    def parse_condition(self):
        return self.parse_disjunction()

    def parse_disjunction(self):
        left = self.parse_conjunction()
        while self.current().type == "OR":
            op = self.current().lexeme
            self.advance()
            right = self.parse_conjunction()
            left = BinaryOpNode(op, left, right)
        return left

    def parse_conjunction(self):
        left = self.parse_negation()
        while self.current().type == "AND":
            op = self.current().lexeme
            self.advance()
            right = self.parse_negation()
            left = BinaryOpNode(op, left, right)
        return left

    def parse_negation(self):
        if self.current().type == "NOT":
            self.advance()
            operand = self.parse_comparison()
            return NotNode(operand)
        return self.parse_comparison()

    def parse_comparison(self):
        if self.current().type == "LEFT_PAREN":
            self.advance()
            node = self.parse_condition()
            self.match("RIGHT_PAREN")
            return node
        left = self.parse_primary()
        if self.current().type in {
            "EQUAL",
            "NOT_EQUAL",
            "LESS",
            "GREATER",
            "LESS_EQUAL",
            "GREATER_EQUAL",
        }:
            op = self.current().lexeme
            self.advance()
            right = self.parse_primary()
            return BinaryOpNode(op, left, right)
        return left

    def parse_primary(self):
        t = self.current()
        if t.type == "IDENTIFIER":
            self.advance()
            return ColumnNode(t.lexeme)
        if t.type in {"NUMBER", "FLOAT", "STRING"}:
            self.advance()
            return LiteralNode(t.lexeme)
        self._error("Expected identifier, number or string in condition", t)
        # return a literal placeholder to continue
        self.advance()
        return LiteralNode(None)


def pprint_ast(node, indent=0):
    pad = "  " * indent
    if isinstance(node, QueryNode):
        print(pad + "Query")
        for s in node.statements:
            pprint_ast(s, indent + 1)
    elif isinstance(node, CreateNode):
        print(pad + f"Create table={node.table_name}")
        for c in node.columns:
            print(pad + f"  Column: {c[0]} {c[1]}")
    elif isinstance(node, InsertNode):
        print(pad + f"Insert into={node.table_name} values={node.values}")
    elif isinstance(node, SelectNode):
        print(pad + f"Select from={node.table_name} columns={node.select_list}")
        if node.where:
            print(pad + "  Where:")
            pprint_ast(node.where, indent + 2)
    elif isinstance(node, UpdateNode):
        print(pad + f"Update {node.table_name} set={node.assignments}")
        if node.where:
            pprint_ast(node.where, indent + 1)
    elif isinstance(node, DeleteNode):
        print(pad + f"Delete from={node.table_name}")
        if node.where:
            pprint_ast(node.where, indent + 1)
    elif isinstance(node, BinaryOpNode):
        print(pad + f"BinOp {node.op}")
        pprint_ast(node.left, indent + 1)
        pprint_ast(node.right, indent + 1)
    elif isinstance(node, NotNode):
        print(pad + "NOT")
        pprint_ast(node.operand, indent + 1)
    elif isinstance(node, ColumnNode):
        print(pad + f"Col {node.name}")
    elif isinstance(node, LiteralNode):
        print(pad + f"Lit {node.value}")
    else:
        print(pad + f"{type(node).__name__}")


def main(path: str, args: argparse.Namespace):
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
    else:
        print("\nParsed successfully.")


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
