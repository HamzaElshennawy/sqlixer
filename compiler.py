import sys
import argparse
from lexer import LexicalAnalyzer
from parser import Parser, pprint_ast
from semantic_analyzer import SemanticAnalyzer


def main():
    parser_arg = argparse.ArgumentParser(
        description="Compiler for SQL-like language (Phase 1-3)"
    )
    parser_arg.add_argument("path", help="Input SQL file path")
    args = parser_arg.parse_args()

    # Read Source Code
    try:
        with open(args.path, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Phase 1: Lexical Analysis
    lexer = LexicalAnalyzer(src)
    tokens, _, lex_errors = lexer.tokenize()

    if lex_errors:
        print("\n" + "=" * 80)
        print("LEXICAL ERRORS")
        print("=" * 80)
        for e in lex_errors:
            print(e)
        return

    # Phase 2: Syntax Analysis
    parser = Parser(tokens)
    tree = parser.parse()

    if parser.errors:
        print("\n" + "=" * 80)
        print("SYNTAX ERRORS")
        print("=" * 80)
        for e in parser.errors:
            print(e)
        return

    # Phase 3: Semantic Analysis
    analyzer = SemanticAnalyzer()
    symtab, sem_errors = analyzer.analyze(tree)

    if sem_errors:
        print("\n" + "=" * 80)
        print("SEMANTIC ERRORS")
        print("=" * 80)
        for e in sem_errors:
            print(e)
        return

    # Success Output
    print("Semantic Analysis Successful. Query is valid.")

    # 1. Symbol Table Dump
    print("\n" + str(symtab))

    # 2. Annotated Parse Tree
    print("\n" + "=" * 60)
    print("ANNOTATED PARSE TREE")
    print("=" * 60)
    pprint_ast(tree)
    print("=" * 60)


if __name__ == "__main__":
    main()
