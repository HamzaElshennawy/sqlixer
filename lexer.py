"""
Lexer.py
This file aims to mimic the SQL tokenizer.
:Authers: Hamza Elshennawy - Ahmed Essam - Youssif Amr.
"""


class Token:
    def __init__(self, token_type, lexeme, line, column):
        self.type = token_type
        self.lexeme = lexeme
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token: {self.type}, Lexeme: {self.lexeme}"


class Symbol:
    def __init__(self, name, token_type, line, column):
        self.name = name
        self.type = token_type
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Symbol: {self.name}, Type: {self.type}"


class LexicalAnalyzer:
    def __init__(self, source_code):
        self.source = source_code
        self.position = 0
        self.line = 1
        self.column = 1
        self.tokens = []
        self.symbol_table = {}
        self.errors = []

        self.RESERVED_WORDS = {
            "SELECT",
            "FROM",
            "WHERE",
            "INSERT",
            "INTO",
            "VALUES",
            "UPDATE",
            "SET",
            "DELETE",
            "CREATE",
            "TABLE",
            "INT",
            "FLOAT",
            "TEXT",
            "AND",
            "OR",
            "NOT",
        }

    def peek(self, offset=0):
        """Look at character without consuming it"""
        pos = self.position + offset
        if pos < len(self.source):
            return self.source[pos]
        return None

    def advance(self):
        """
        Consume and return current character
        """
        if self.position >= len(self.source):
            return None

        ch = self.source[self.position]
        self.position += 1

        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

        return ch

    def skip_whitespace(self):
        """Skip whitespace characters"""
        while (ch := self.peek()) is not None and ch.isspace():
            self.advance()

    def skip_single_line_comment(self):
        """Skip single-line comment starting with --"""
        self.advance()  # skip first -
        self.advance()  # skip second -

        while self.peek() and self.peek() != "\n":
            self.advance()

    def skip_multi_line_comment(self):
        """Skip multi-line comment enclosed in ##"""
        start_line = self.line
        start_column = self.column

        self.advance()  # skip first #
        self.advance()  # skip second #

        while self.position < len(self.source):
            if self.peek() == "#" and self.peek(1) == "#":
                self.advance()
                self.advance()
                return True
            self.advance()

        # Unclosed comment
        self.errors.append(f"Error: unclosed comment starting at line {start_line}.")
        return False

    def read_string(self):
        """Read string literal enclosed in single quotes"""
        start_line = self.line
        start_column = self.column

        self.advance()  # skip opening quote
        string_value = ""

        while self.peek() and self.peek() != "'":
            if self.peek() == "\n":
                # Allow multi-line strings but track line numbers
                pass
            string_value += self.advance()  # type: ignore

        if self.peek() == "'":
            self.advance()  # skip closing quote
            return Token("STRING", f"'{string_value}'", start_line, start_column)
        else:
            # Unclosed string
            self.errors.append(f"Error: unclosed string starting at line {start_line}.")
            return None

    def read_number(self):
        """Read numeric literal (integer or float)"""
        start_line = self.line
        start_column = self.column
        number = ""
        is_float = False

        while self.peek() and (self.peek().isdigit() or self.peek() == "."):  # type: ignore
            if self.peek() == ".":
                if is_float:
                    break  # Second dot, stop
                is_float = True
            number += self.advance()  # type: ignore

        token_type = "FLOAT" if is_float else "NUMBER"
        return Token(token_type, number, start_line, start_column)

    def read_identifier_or_keyword(self):
        """Read identifier or reserved word"""
        start_line = self.line
        start_column = self.column
        identifier = ""

        # Must start with letter
        if not self.peek().isalpha():  # type: ignore
            return None

        # Read letters, digits, and underscores
        while self.peek() and (self.peek().isalnum() or self.peek() == "_"):  # type: ignore
            identifier += self.advance()  # type: ignore

        # Check if it's a reserved word (case-sensitive)
        if identifier in self.RESERVED_WORDS:
            return Token(identifier, identifier, start_line, start_column)

        # It's an identifier - add to symbol table
        if identifier not in self.symbol_table:
            self.symbol_table[identifier] = Symbol(
                identifier, "IDENTIFIER", start_line, start_column
            )

        return Token("IDENTIFIER", identifier, start_line, start_column)

    def read_operator_or_symbol(self):
        """Read operators and symbols"""
        start_line = self.line
        start_column = self.column
        ch = self.peek()

        # Two-character operators
        if ch == "=" and self.peek(1) == "=":
            self.advance()
            self.advance()
            return Token("EQUAL", "==", start_line, start_column)
        elif ch == "!" and self.peek(1) == "=":
            self.advance()
            self.advance()
            return Token("NOT_EQUAL", "!=", start_line, start_column)
        elif ch == "<" and self.peek(1) == "=":
            self.advance()
            self.advance()
            return Token("LESS_EQUAL", "<=", start_line, start_column)
        elif ch == ">" and self.peek(1) == "=":
            self.advance()
            self.advance()
            return Token("GREATER_EQUAL", ">=", start_line, start_column)

        # Single-character operators and symbols
        single_char_tokens = {
            "=": "EQUAL",
            "<": "LESS",
            ">": "GREATER",
            "+": "PLUS",
            "-": "MINUS",
            "*": "MULTIPLY",
            "/": "DIVIDE",
            "(": "LEFT_PAREN",
            ")": "RIGHT_PAREN",
            ",": "COMMA",
            ";": "SEMICOLON",
            ".": "DOT",
        }

        if ch in single_char_tokens:
            token_type = single_char_tokens[ch]
            lexeme = self.advance()
            return Token(token_type, lexeme, start_line, start_column)

        return None

    def tokenize(self):
        """Main tokenization method"""
        while self.position < len(self.source):
            self.skip_whitespace()

            if self.position >= len(self.source):
                break

            start_line = self.line
            start_column = self.column
            ch = self.peek()

            # Comments
            if ch == "-" and self.peek(1) == "-":
                self.skip_single_line_comment()
                continue

            if ch == "#" and self.peek(1) == "#":
                self.skip_multi_line_comment()
                continue

            # String literals
            if ch == "'":
                token = self.read_string()
                if token:
                    self.tokens.append(token)
                continue

            # Numbers
            if ch.isdigit():  # type: ignore
                token = self.read_number()
                self.tokens.append(token)
                continue

            # Identifiers and keywords
            if ch.isalpha():  # type: ignore
                token = self.read_identifier_or_keyword()
                if token:
                    self.tokens.append(token)
                continue

            # Operators and symbols
            token = self.read_operator_or_symbol()
            if token:
                self.tokens.append(token)
                continue

            # Invalid character
            self.errors.append(
                f"[ERROR] invalid character '{ch}' at line {start_line}, position {start_column}."
            )
            self.advance()

        return self.tokens, self.symbol_table, self.errors

    def print_results(self):
        """Print tokens, symbol table, and errors in formatted tables"""
        # Print Tokens Table
        print("\n" + "=" * 80)
        print("TOKENS")
        print("=" * 80)
        print(f"{'TYPE':<20} {'LEXEME':<25} {'LINE':<10} {'COLUMN':<10}")
        print("-" * 80)
        for token in self.tokens:
            print(
                f"{token.type:<20} {token.lexeme:<25} {token.line:<10} {token.column:<10}"
            )
        print("=" * 80)

        # Print Symbol Table
        if self.symbol_table:
            print("\n" + "=" * 80)
            print("SYMBOL TABLE")
            print("=" * 80)
            print(f"{'NAME':<25} {'TYPE':<20} {'LINE':<10} {'COLUMN':<10}")
            print("-" * 80)
            for symbol in self.symbol_table.values():
                print(
                    f"{symbol.name:<25} {symbol.type:<20} {symbol.line:<10} {symbol.column:<10}"
                )
            print("=" * 80)

        # Print Errors
        if self.errors:
            print("\n" + "=" * 80)
            print("ERRORS")
            print("=" * 80)
            for i, error in enumerate(self.errors, 1):
                print(f"{i}. {error}")
            print("=" * 80)


# Example usage
if __name__ == "__main__":
    import sys

    # Check if file argument is provided
    if len(sys.argv) < 2:
        print("Usage: python lexer.py <input_file>")

    else:
        # Read from file
        input_file = sys.argv[1]

        try:
            with open(input_file, "r") as f:
                sql_code = f.read()

            print(f"Analyzing file: {input_file}")
            print("=" * 60)
            print("Source Code:")
            print("=" * 60)
            print(sql_code)
            print()

            lexer = LexicalAnalyzer(sql_code)
            lexer.tokenize()
            lexer.print_results()

        except FileNotFoundError:
            print(f"Error: File '{input_file}' not found.")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file: {e}")
            sys.exit(1)
